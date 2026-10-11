"""Durable owned clarification process; Task/audit publication stays in handlers."""
from contextlib import contextmanager
from hashlib import sha256

from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import LOCK_KEY,schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.definitions import canonical
from src.application.direct_creation import DirectCreationNormalizer,CreationProposal,UserInputBinding
from src.application.evidence_storage import EvidenceError
from src.application.migrations import MigrationError
from src.application.ports import PortResult,RequestContext
from src.application.task_resolution import (CourseLabel,ResolutionIntent,ResolutionSnapshot,admit_intent,admit_reply,admit_frame,
    begin_resolution,resume_resolution,refresh_resolution,resolution_handoff,current_scope,course_registry_hash,user)
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError,require

RESOLUTION_LOCK=LOCK_KEY+3


class PostgresResolutionService:
    def __init__(self,connection,codec,plan,*,application_version,clock,input_bindings=(),course_bindings=()):
        require(isinstance(input_bindings,tuple) and all(isinstance(b,UserInputBinding) for b in input_bindings),'RESOLUTION_INPUT_BINDINGS')
        require(isinstance(course_bindings,tuple) and all(isinstance(b,tuple) and len(b)==2 and isinstance(b[0],str) and isinstance(b[1],tuple)
            for b in course_bindings) and len({b[0] for b in course_bindings})==len(course_bindings),'RESOLUTION_COURSE_BINDINGS')
        for _,courses in course_bindings:course_registry_hash(courses)
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock
        self._input_bindings=input_bindings;self._courses=dict(course_bindings)
        self._normalizer=DirectCreationNormalizer(codec,clock=clock,bindings=input_bindings)
        self._reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)

    @contextmanager
    def _transaction(self,write=False):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=not write):
            yield
            if write:self._commit_phase=True
        if write:self._commit_phase=False

    def _snapshot(self,caller):
        rows=self.connection.execute('''SELECT h.task_id,h.revision FROM whattodo.task_head h
            JOIN whattodo.task_revision t ON (t.task_id,t.revision)=(h.task_id,h.revision)
            JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref
            WHERE a.principal_id=%s ORDER BY h.task_id LIMIT 1001''',(caller.principal_id,)).fetchall()
        require(len(rows)<=1000,'RESOLUTION_REFERENCES_TOO_BROAD')
        records=tuple(self._reader._get_in_transaction(*row) for row in rows)
        return ResolutionSnapshot(caller.principal_id,self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()[0],records,
            self._courses.get(caller.principal_id,()))

    def _source(self,ref,raw,caller):
        scopes=tuple(b.scope for b in self._input_bindings if b.principal_id==caller.principal_id)
        require(scopes,'RESOLUTION_INPUT_ACCOUNT_REQUIRED')
        evidence=PostgresEvidenceRepository(self.connection,self.codec,self.plan,application_version=self.application_version,clock=self.clock,scopes=scopes).get_source(ref)
        require(evidence is not None and evidence.source.source_type=='USER' and evidence.source.state=='PRESENT','RESOLUTION_USER_SOURCE_REQUIRED')
        require(evidence.source.content_hash==sha256(raw).hexdigest(),'RESOLUTION_EXACT_SOURCE_REQUIRED')
        require(evidence.source.captured_at<=self.clock.now(),'RESOLUTION_FUTURE_SOURCE');return evidence.source

    def _get(self,session_id,caller,revision=None):
        if revision is None:
            head=self.connection.execute('SELECT revision,principal_id FROM whattodo.command_resolution_head WHERE session_id=%s',(session_id,)).fetchone()
            if head is None:return None
            require(head[1]==caller.principal_id,'RESOLUTION_AUTHENTICATED_OWNER_REQUIRED');revision=head[0]
        row=self.connection.execute('''SELECT command_id,principal_id,state,query_source_ref,last_source_ref,frame_hash,frame_bytes,created_at,previous_revision
            FROM whattodo.command_resolution_revision WHERE session_id=%s AND revision=%s''',(session_id,revision)).fetchone()
        if row is None:return None
        require(row[1]==caller.principal_id,'RESOLUTION_AUTHENTICATED_OWNER_REQUIRED')
        frame=admit_frame(self.codec,bytes(row[6]));v=frame.as_record()
        from src.domain.task_aggregate import instant
        require((v['command_id'],v['principal_id'],v['state'],v['query_source_ref'],v['last_source_ref'],frame.fingerprint,instant(v['created_at']),v['previous_revision'])
            ==row[:6]+row[7:] and (frame.session_id,frame.revision)==(session_id,revision),'RESOLUTION_HISTORY_DRIFT')
        if revision>1:
            parent_row=self.connection.execute('SELECT frame_bytes,frame_hash FROM whattodo.command_resolution_revision WHERE session_id=%s AND revision=%s',
                (session_id,revision-1)).fetchone()
            require(parent_row is not None,'RESOLUTION_HISTORY_DRIFT')
            parent=admit_frame(self.codec,bytes(parent_row[0]));p=parent.as_record()
            require(parent.fingerprint==parent_row[1] and (parent.session_id,parent.revision)==(session_id,revision-1)
                and all(v[k]==p[k] for k in ('intent','principal_id','command_id','query_source_ref'))
                and p['state']!='RESOLVED' and instant(v['created_at'])>=instant(p['created_at'])
                and all(v['fields'].get(k)==value for k,value in p['fields'].items())
                and all(v['creation_facts'].get(k)==value for k,value in p['creation_facts'].items()),'RESOLUTION_HISTORY_DRIFT')
        return frame

    def _append(self,frame,caller):
        from src.domain.task_aggregate import instant
        v=frame.as_record()
        self.connection.execute('INSERT INTO whattodo.command_resolution_revision VALUES('+','.join(['%s']*11)+')',
            (v['session_id'],v['revision'],v['previous_revision'],v['command_id'],v['principal_id'],v['state'],v['query_source_ref'],v['last_source_ref'],frame.fingerprint,frame.raw_bytes,instant(v['created_at'])))
        if frame.revision==1:self.connection.execute('INSERT INTO whattodo.command_resolution_head VALUES(%s,%s,%s,%s)',(v['session_id'],1,v['principal_id'],v['command_id']))
        else:
            updated=self.connection.execute('UPDATE whattodo.command_resolution_head SET revision=%s WHERE session_id=%s AND revision=%s AND principal_id=%s',
                (frame.revision,frame.session_id,frame.revision-1,v['principal_id']))
            require(updated.rowcount==1,'RESOLUTION_STALE_SESSION')
        require(self._get(frame.session_id,caller,frame.revision)==frame,'RESOLUTION_ROUNDTRIP_FAILED')

    def _lock(self):
        require(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)',(RESOLUTION_LOCK,)).fetchone()==(True,),'RESOLUTION_BUSY')

    def _result(self,fn,correlation):
        self._commit_phase=False
        try:return fn()
        except (TransactionError,EvidenceError,TaskStorageError) as exc:
            code=str(exc);retry=code=='RESOLUTION_BUSY'
            conflict=code in ('RESOLUTION_STALE_SESSION','RESOLUTION_REPLY_SCOPE_CONFLICT','RESOLUTION_TASK_SNAPSHOT_CHANGED','RESOLUTION_COURSE_REGISTRY_CHANGED',
                'RESOLUTION_ALREADY_RESOLVED','RESOLUTION_CREATE_TARGET_ALREADY_EXISTS','RESOLUTION_COMMAND_CONTENT_CONFLICT','RESOLUTION_REPLY_ID_CONFLICT')
            return PortResult('RETRYABLE' if retry else 'CONFLICT' if conflict else 'PERMANENT',code,correlation)
        except MigrationError as exc:return PortResult('RETRYABLE' if str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else 'PERMANENT','RESOLUTION_SCHEMA_UNAVAILABLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except Exception as exc:
            import importlib.util
            if importlib.util.find_spec('psycopg') is not None:
                from psycopg import Error,OperationalError
                if isinstance(exc,Error):
                    if isinstance(exc,OperationalError) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                        if isinstance(exc,OperationalError) and self._commit_phase:return PortResult('UNKNOWN','RESOLUTION_ACKNOWLEDGEMENT_LOST',correlation)
                        return PortResult('RETRYABLE','RESOLUTION_DATABASE_UNAVAILABLE',correlation)
                    if getattr(exc,'sqlstate',None)=='23505':return PortResult('CONFLICT','RESOLUTION_IDENTITY_CONFLICT',correlation)
                    return PortResult('PERMANENT','RESOLUTION_DATABASE_REJECTED',correlation)
            return PortResult('PERMANENT','RESOLUTION_VALIDATION_FAILED',correlation)

    def _driver(self):from psycopg import Error

    def begin(self,raw,source_ref,context,*,caller):
        def run():
            user(caller);intent=admit_intent(self.codec,raw);v=intent.as_record();user(caller,v['principal_id']);self._driver()
            require(context.request_id==v['command_id'],'RESOLUTION_CONTEXT_MISMATCH')
            return self._begin(intent,source_ref,raw,context,caller)
        return self._result(run,context.correlation_ref)

    def begin_creation(self,proposal,context,*,session_id,desired_task_id,caller):
        def run():
            user(caller);require(isinstance(proposal,CreationProposal),'RESOLUTION_CREATION_PROPOSAL_REQUIRED');self._driver()
            handoff=self._normalizer.manual_handoff(proposal,command_id=context.request_id,task_id=desired_task_id,authority_ref='unregistered-resolution-reference',caller=caller)
            intent=admit_intent(self.codec,canonical(dict(schema_version='0.1.0-resolution-intent',session_id=session_id,command_id=context.request_id,principal_id=caller.principal_id,
                action='CREATE_TASK',target=None,creation_task_id=desired_task_id,fields=handoff.command.changes[0].fields,creation_facts=handoff.intent.facts)).encode())
            return self._begin(intent,proposal.source.record_id,proposal.statement_bytes,context,caller)
        return self._result(run,context.correlation_ref)

    def _begin(self,intent,source_ref,raw,context,caller):
        i=intent.as_record()
        with self._transaction():
            previous=self.connection.execute('SELECT session_id FROM whattodo.command_resolution_head WHERE principal_id=%s AND command_id=%s',(caller.principal_id,i['command_id'])).fetchone()
            if previous:
                first=self._get(previous[0],caller,1);require(first.as_record()['intent']==i and first.as_record()['query_source_ref']==source_ref,'RESOLUTION_COMMAND_CONTENT_CONFLICT')
                return PortResult('SUCCESS','RESOLUTION_REPLAY',context.correlation_ref,self._get(previous[0],caller))
        source=self._source(source_ref,raw,caller)
        with self._transaction(True):
            self._lock();require(self._get(i['session_id'],caller) is None,'RESOLUTION_COMMAND_CONTENT_CONFLICT')
            frame=begin_resolution(self.codec,intent,self._snapshot(caller),source_ref=source_ref,source_observed_at=source.captured_at,at=self.clock.now(),caller=caller)
            self._append(frame,caller)
        return PortResult('SUCCESS','RESOLVED' if frame.as_record()['state']=='RESOLVED' else 'NEEDS_CLARIFICATION',context.correlation_ref,frame)

    def get(self,session_id,context,*,caller,revision=None):
        def run():
            user(caller);self._driver()
            with self._transaction():frame=self._get(session_id,caller,revision)
            return PortResult('UNKNOWN','RESOLUTION_NOT_OBSERVED',context.correlation_ref) if frame is None else PortResult('SUCCESS','RESOLUTION_FOUND',context.correlation_ref,frame)
        return self._result(run,context.correlation_ref)

    def reply(self,raw,source_ref,context,*,caller):
        def run():
            user(caller);r=admit_reply(self.codec,raw);self._driver()
            require(isinstance(context,RequestContext) and context.request_id==r['reply_id'],'RESOLUTION_CONTEXT_MISMATCH')
            request_hash=sha256(canonical(dict(reply=r,source_ref=source_ref,principal_id=caller.principal_id)).encode()).hexdigest()
            with self._transaction():
                old=self.connection.execute('SELECT principal_id,session_id,before_revision,after_revision,request_hash,source_record_ref,reply_bytes,reply_hash FROM whattodo.command_resolution_reply WHERE reply_id=%s',
                    (r['reply_id'],)).fetchone()
                if old:
                    require(old[0]==caller.principal_id,'RESOLUTION_AUTHENTICATED_OWNER_REQUIRED')
                    require(old[4]==request_hash and old[5]==source_ref and bytes(old[6])==raw and sha256(raw).hexdigest()==old[7],'RESOLUTION_REPLY_ID_CONFLICT')
                    before=self._get(old[1],caller,old[2]);require(before is not None and before.fingerprint==r['scope_hash'],'RESOLUTION_HISTORY_DRIFT')
                    frame=self._get(old[1],caller,old[3]);require(frame is not None and frame.as_record()['last_source_ref']==source_ref,'RESOLUTION_HISTORY_DRIFT')
                    return PortResult('SUCCESS','CLARIFICATION_REPLAY',context.correlation_ref,frame)
            source=self._source(source_ref,raw,caller)
            with self._transaction(True):
                self._lock();frame=self._get(r['session_id'],caller);require(frame is not None,'RESOLUTION_NOT_AVAILABLE')
                require(frame.revision==r['expected_revision'],'RESOLUTION_STALE_SESSION')
                updated=resume_resolution(self.codec,frame,r,self._snapshot(caller),source_ref=source_ref,source_observed_at=source.captured_at,at=self.clock.now(),caller=caller)
                self._append(updated,caller)
                self.connection.execute('INSERT INTO whattodo.command_resolution_reply VALUES('+','.join(['%s']*9)+')',
                    (r['reply_id'],caller.principal_id,frame.session_id,frame.revision,updated.revision,request_hash,source_ref,raw,sha256(raw).hexdigest()))
            return PortResult('SUCCESS','RESOLVED' if updated.as_record()['state']=='RESOLVED' else 'NEEDS_CLARIFICATION',context.correlation_ref,updated)
        return self._result(run,context.correlation_ref)

    def refresh(self,session_id,expected_revision,scope_hash,context,*,caller):
        def run():
            user(caller);self._driver()
            with self._transaction(True):
                self._lock();frame=self._get(session_id,caller);require(frame is not None and frame.revision==expected_revision and frame.fingerprint==scope_hash,'RESOLUTION_STALE_SESSION')
                updated=refresh_resolution(self.codec,frame,self._snapshot(caller),at=self.clock.now(),caller=caller);self._append(updated,caller)
            return PortResult('SUCCESS','RESOLVED' if updated.as_record()['state']=='RESOLVED' else 'NEEDS_CLARIFICATION',context.correlation_ref,updated)
        return self._result(run,context.correlation_ref)

    def handoff(self,session_id,revision,scope_hash,authority_ref,context,*,caller):
        def run():
            user(caller);self._driver()
            with self._transaction():
                frame=self._get(session_id,caller);require(frame is not None and frame.revision==revision and frame.fingerprint==scope_hash,'RESOLUTION_STALE_SESSION')
                out=resolution_handoff(frame,authority_ref=authority_ref,caller=caller)
                coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,application_version=self.application_version,clock=self.clock)
                prior=coordinator._lookup_in_transaction(out.command.command_id,caller)
                if prior is not None:
                    annotation=self.connection.execute('''SELECT a.resolved_scope,e.source_record_ref FROM whattodo.command_transaction t JOIN whattodo.authority_record a
                        ON a.authority_ref=t.authority_ref JOIN whattodo.audit_entry e ON e.audit_id=t.audit_id WHERE t.request_id=%s''',(out.command.command_id,)).fetchone()
                    require(annotation is not None and annotation[0].get('authorization',{}).get('command_fingerprint')==out.command.fingerprint
                        and annotation[1]==frame.as_record()['last_source_ref'],'RESOLUTION_COMMAND_CONTENT_CONFLICT')
                    return PortResult('SUCCESS','HANDOFF_REPLAY',context.correlation_ref,out)
                snapshot=self._snapshot(caller);current_scope(frame,snapshot)
                from dataclasses import replace
                out=replace(out,expected_store_revision=snapshot.store_revision)
            return PortResult('SUCCESS','HANDOFF_READY',context.correlation_ref,out)
        return self._result(run,context.correlation_ref)
