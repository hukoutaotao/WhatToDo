"""Owned read projections over immutable version snapshots."""
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_resolution import PostgresResolutionService
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical,strict_json
from src.application.evidence_storage import EvidenceError,SourceScope
from src.application.migrations import MigrationError
from src.application.ports import PortResult,RequestContext
from src.application.read_models import CursorSigner,ReadSnapshot,admit_query,make_snapshot,make_page,task_view,semantic_changes,MAX_REFERENCES,MAX_PAGE_BYTES
from src.application.task_resolution import user,resolution_handoff
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError,require
from src.domain.task_aggregate import instant


class PostgresReadService:
    def __init__(self,connection,codec,plan,*,application_version,clock,cursor_key,scopes=(),snapshot_lifetime=timedelta(hours=24)):
        require(isinstance(scopes,tuple) and all(isinstance(s,SourceScope) for s in scopes) and len(set(scopes))==len(scopes),'READ_SOURCE_BINDINGS')
        require(isinstance(snapshot_lifetime,timedelta) and timedelta(seconds=1)<=snapshot_lifetime<=timedelta(days=7),'READ_SNAPSHOT_LIFETIME')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock;self._scopes=scopes;self._lifetime=snapshot_lifetime
        self._signer=CursorSigner(cursor_key);options=dict(application_version=application_version,clock=clock)
        self._reader=PostgresTaskRepository(connection,codec,plan,**options)
        self._evidence=PostgresEvidenceRepository(connection,codec,plan,**options,scopes=scopes)
        self._resolution=PostgresResolutionService(connection,codec,plan,**options)
    def _transaction(self,write=False):return schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=not write)
    def _scope_hash(self,query):
        scope=[dict(provider=s.provider,scope_ref=s.scope_ref,account_ref=s.account_ref) for s in sorted(self._scopes,key=lambda s:(s.provider,s.scope_ref,s.account_ref))]
        if query.view!='PENDING' or query.as_record()['pending_kind'] not in (None,'EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT'):scope=[]
        return sha256(canonical(scope).encode()).hexdigest()
    def _source_state(self,query):
        if query.view!='PENDING' or query.as_record()['pending_kind'] not in (None,'EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT'):return 'NOT_APPLICABLE'
        return 'CONFIGURED' if self._scopes else 'UNCONFIGURED'
    def _reference(self,kind,key,rev,state,actual=0,transaction=None,store=None,pending=None,pending_revision=None):
        return dict(kind=kind,id=key,revision=rev,state=state,actual_seconds=int(actual),transaction_ref=transaction,store_revision=store,pending_id=pending,pending_revision=pending_revision)
    def _rows(self,cursor):
        rows=[]
        while True:
            batch=cursor.fetchmany(500)
            if not batch:break
            rows.extend(batch);require(len(rows)<=MAX_REFERENCES,'READ_SNAPSHOT_REFERENCES_TOO_BROAD')
        return rows
    def _total(self,key,store):
        return int(self.connection.execute("SELECT COALESCE(sum(o.seconds),0) FROM whattodo.effort_observation o JOIN whattodo.command_transaction t ON t.request_id=o.transaction_ref WHERE o.task_id=%s AND o.kind='ACTUAL_WORK' AND t.committed_store_revision<=%s",(key,store)).fetchone()[0])
    def _references(self,query,caller):
        v=query.as_record();refs=[]
        if query.view in ('TASKS','HISTORY'):
            if query.view=='HISTORY':
                owned=self.connection.execute('''SELECT 1 FROM whattodo.task_head h JOIN whattodo.task_revision t ON (t.task_id,t.revision)=(h.task_id,h.revision)
                    JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref WHERE h.task_id=%s AND a.principal_id=%s''',(v['task_id'],caller.principal_id)).fetchone()
                require(owned is not None,'READ_TASK_NOT_AVAILABLE')
            params=[caller.principal_id];f=v['filters'];ctx=f['context']
            sql='SELECT t.task_id,t.revision,t.transaction_ref,c.committed_store_revision FROM whattodo.task_revision t JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref JOIN whattodo.command_transaction c ON c.request_id=t.transaction_ref'
            if query.view=='TASKS':sql+=' JOIN whattodo.task_head h ON (h.task_id,h.revision)=(t.task_id,t.revision)'
            sql+=' WHERE a.principal_id=%s'
            if query.view=='HISTORY':sql+=' AND t.task_id=%s';params.append(v['task_id'])
            else:
                for name,column in (('completion','t.completion'),('disposition','t.disposition'),('trust',"t.metadata->>'trust'"),('domain','t.domain')):
                    if f[name] is not None:sql+=' AND '+column+'=%s';params.append(f[name])
                if ctx is not None:sql+=' AND t.context_kind=%s AND t.context_id=%s';params.extend((ctx['kind'],ctx['id']))
            for key,rev,tx,store in self._rows(self.connection.execute(sql+' ORDER BY t.task_id,t.revision',tuple(params))):
                refs.append(self._reference('TASK' if query.view=='TASKS' else 'HISTORY',key,rev,'CURRENT' if query.view=='TASKS' else 'HISTORICAL',self._total(key,store),tx,store))
            return refs
        kind=v['pending_kind'];closed=v['include_closed']
        if kind in (None,'MANUAL_CREATION'):
            for key,cmd,desired in self._rows(self.connection.execute('SELECT pending_id,command_id,desired_task_id FROM whattodo.manual_creation_pending WHERE principal_id=%s ORDER BY pending_id',(caller.principal_id,))):
                commit=self.connection.execute('SELECT committed_store_revision FROM whattodo.command_transaction WHERE request_id=%s AND principal_id=%s',(cmd,caller.principal_id)).fetchone();state='OPEN'
                if commit:
                    match=self.connection.execute("SELECT 1 FROM whattodo.audit_change WHERE request_id=%s AND aggregate_kind='TASK' AND aggregate_id=%s AND before_revision IS NULL AND after_revision=1",(cmd,desired)).fetchone();state='RESOLVED' if match else 'SUPERSEDED'
                if state=='OPEN' or closed:refs.append(self._reference('MANUAL_CREATION',key,1,state,transaction=cmd if commit else None,store=commit[0] if commit else None))
        if kind in (None,'CLARIFICATION'):
            for key,rev,cmd in self._rows(self.connection.execute('SELECT session_id,revision,command_id FROM whattodo.command_resolution_head WHERE principal_id=%s ORDER BY session_id',(caller.principal_id,))):
                frame=self._resolution._get(key,caller,rev);require(frame is not None,'READ_PENDING_FRAME_UNAVAILABLE')
                commit=self.connection.execute('''SELECT c.committed_store_revision,a.resolved_scope,e.source_record_ref FROM whattodo.command_transaction c JOIN whattodo.authority_record a ON a.authority_ref=c.authority_ref JOIN whattodo.audit_entry e ON e.audit_id=c.audit_id WHERE c.request_id=%s AND c.principal_id=%s''',(cmd,caller.principal_id)).fetchone();state='OPEN'
                if commit:
                    state='SUPERSEDED';annotation=commit[1].get('authorization',{})
                    if frame.as_record()['state']=='RESOLVED' and annotation.get('grant_ref'):
                        out=resolution_handoff(frame,authority_ref=annotation['grant_ref'],caller=caller)
                        if out.command.fingerprint==annotation.get('command_fingerprint') and commit[2]==frame.as_record()['last_source_ref']:state='RESOLVED'
                if state=='OPEN' or closed:refs.append(self._reference('CLARIFICATION',key,rev,state,transaction=cmd if commit else None,store=commit[0] if commit else None))
        if kind in (None,'EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT') and self._scopes:
            for scope in self._scopes:self._evidence._scope(scope.provider,scope.scope_ref)
            predicate=' OR '.join('(s.provider=%s AND s.scope_ref=%s)' for _ in self._scopes)
            sql='''SELECT p.kind,p.candidate_id,p.conflict_id,r.state,coalesce(ch.revision,1),r.transaction_ref,c.committed_store_revision,p.pending_id,r.revision
                FROM whattodo.pending_evidence_identity p JOIN whattodo.pending_evidence_head h USING(pending_id) JOIN whattodo.pending_evidence_revision r USING(pending_id,revision)
                LEFT JOIN whattodo.evidence_conflict f ON f.conflict_id=p.conflict_id LEFT JOIN whattodo.candidate_identity i ON i.candidate_id=coalesce(p.candidate_id,f.candidate_id)
                LEFT JOIN (SELECT candidate_id,max(revision) revision FROM whattodo.candidate_revision GROUP BY candidate_id) ch ON ch.candidate_id=i.candidate_id
                JOIN whattodo.source_record sr ON sr.record_id=coalesce(i.source_record_ref,f.source_record_ref) JOIN whattodo.source_identity s ON s.source_id=sr.source_id
                LEFT JOIN whattodo.command_transaction c ON c.request_id=r.transaction_ref WHERE ('''+predicate+') ORDER BY p.pending_id'
            for pk,candidate,conflict,state,rev,tx,store,pid,prev in self._rows(self.connection.execute(sql,tuple(x for s in self._scopes for x in (s.provider,s.scope_ref)))):
                chosen='EVIDENCE_CANDIDATE' if pk=='CANDIDATE' else 'EVIDENCE_CONFLICT'
                if kind not in (None,chosen) or not closed and state!='OPEN':continue
                refs.append(self._reference(chosen,candidate if pk=='CANDIDATE' else conflict,rev if pk=='CANDIDATE' else 1,state,transaction=tx,store=store,pending=pid,pending_revision=prev))
        require(len(refs)<=MAX_REFERENCES,'READ_SNAPSHOT_REFERENCES_TOO_BROAD');return refs
    def _snapshot(self,query,caller):
        epoch=self.connection.execute('SELECT revision,last_transaction_ref FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone();require(epoch is not None,'READ_EPOCH_UNAVAILABLE');now=self.clock.now()
        snap=make_snapshot(query,snapshot_id='read-'+uuid4().hex,principal_id=caller.principal_id,scope_hash=self._scope_hash(query),store_revision=epoch[0],last_transaction_ref=epoch[1],observed_at=now,expires_at=now+self._lifetime,references=self._references(query,caller),source_scope_state=self._source_state(query));v=snap.as_record()
        self.connection.execute('INSERT INTO whattodo.read_snapshot VALUES('+','.join(['%s']*10)+')',(v['snapshot_id'],v['principal_id'],v['query_hash'],v['scope_hash'],v['store_revision'],v['last_transaction_ref'],instant(v['observed_at']),instant(v['expires_at']),snap.fingerprint,snap.raw_bytes));return snap
    def _get_snapshot(self,key,query,caller):
        row=self.connection.execute('SELECT principal_id,query_hash,scope_hash,store_revision,last_transaction_ref,observed_at,expires_at,payload_hash,payload_bytes FROM whattodo.read_snapshot WHERE snapshot_id=%s',(key,)).fetchone()
        require(row is not None and row[0]==caller.principal_id,'READ_SNAPSHOT_NOT_AVAILABLE');snap=ReadSnapshot(bytes(row[8]),canonical(strict_json(bytes(row[8]))));v=snap.as_record()
        require(v['snapshot_id']==key and (v['principal_id'],v['query_hash'],v['scope_hash'],v['store_revision'],v['last_transaction_ref'],instant(v['observed_at']),instant(v['expires_at']),snap.fingerprint)==row[:8],'READ_SNAPSHOT_PROJECTION_DRIFT')
        admit_query(self.codec,canonical(v['query']).encode());require(v['query_hash']==query.fingerprint,'READ_CURSOR_SCOPE_CONFLICT');require(v['scope_hash']==self._scope_hash(query),'READ_SOURCE_SCOPE_CHANGED')
        require(self.clock.now()<instant(v['expires_at']),'READ_SNAPSHOT_EXPIRED');return snap
    def _task(self,ref,caller):
        row=self.connection.execute('SELECT a.principal_id FROM whattodo.task_revision t JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref WHERE t.task_id=%s AND t.revision=%s',(ref['id'],ref['revision'])).fetchone()
        require(row==(caller.principal_id,),'READ_TASK_NOT_AVAILABLE');record=self._reader._get_in_transaction(ref['id'],ref['revision']);require(record is not None,'READ_TASK_VERSION_UNAVAILABLE');return record
    def _item(self,ref,snapshot,caller):
        kind=ref['kind'];data=None
        if kind in ('TASK','HISTORY'):
            record=self._task(ref,caller);data=task_view(record,ref['actual_seconds'])
            if kind=='HISTORY':
                row=self.connection.execute('''SELECT a.change_id,a.audit_id,a.request_id,a.before_revision,a.before_value,a.after_value,c.origin,c.committed_store_revision,c.committed_at,e.source_record_ref
                    FROM whattodo.task_revision t JOIN whattodo.audit_change a ON a.change_id=t.audit_change_ref JOIN whattodo.command_transaction c ON c.request_id=t.transaction_ref JOIN whattodo.audit_entry e ON e.audit_id=c.audit_id
                    WHERE t.task_id=%s AND t.revision=%s AND a.aggregate_kind='TASK' AND a.aggregate_id=t.task_id AND a.after_revision=t.revision AND a.request_id=c.request_id AND a.audit_id=c.audit_id''',(ref['id'],ref['revision'])).fetchone()
                require(row is not None and row[2]==ref['transaction_ref'] and row[7]==ref['store_revision'] and row[5]==record.aggregate.as_record(),'READ_HISTORY_AUDIT_DRIFT');before=None
                if row[3] is not None:
                    previous=next((r for r in snapshot.as_record()['references'] if r['kind']=='HISTORY' and r['id']==ref['id'] and r['revision']==row[3]),None)
                    require(previous is not None,'READ_HISTORY_LINEAGE_UNAVAILABLE');old=self._task(previous,caller);require(row[4]==old.aggregate.as_record() and row[3]==ref['revision']-1,'READ_HISTORY_AUDIT_DRIFT');before=task_view(old,previous['actual_seconds'])
                else:require(row[4] is None and ref['revision']==1,'READ_HISTORY_AUDIT_DRIFT')
                data=dict(task=data,event=dict(command_id=row[2],audit_id=row[1],change_id=row[0],origin=row[6],store_revision=row[7],committed_at=row[8].isoformat(),source_ref=row[9],changed_fields=semantic_changes(before,data)))
        elif kind=='MANUAL_CREATION':
            row=self.connection.execute('SELECT command_id,principal_id,desired_task_id,source_record_ref,proposal_hash,proposal_bytes,created_at FROM whattodo.manual_creation_pending WHERE pending_id=%s',(ref['id'],)).fetchone()
            require(row is not None and row[1]==caller.principal_id and sha256(bytes(row[5])).hexdigest()==row[4],'READ_PENDING_PROJECTION_DRIFT');v=strict_json(bytes(row[5]));c=v['command']
            require((c['command_id'],c['principal_id'],c['changes'][0]['task_id'])==row[:3] and v['resolved_creation']['source_ref']==row[3],'READ_PENDING_PROJECTION_DRIFT')
            data=dict(command_id=row[0],desired_task_id=row[2],title=c['changes'][0]['fields'].get('title'),missing_fields=v['missing_fields'],source_ref=row[3],created_at=row[6].isoformat())
        elif kind=='CLARIFICATION':
            frame=self._resolution._get(ref['id'],caller,ref['revision']);require(frame is not None,'READ_PENDING_FRAME_UNAVAILABLE');v=frame.as_record();data={k:v[k] for k in ('command_id','question','missing_fields','choices')}
        elif kind=='EVIDENCE_CANDIDATE':
            found=self._evidence._candidate(ref['id'],ref['revision']);require(found is not None,'READ_CANDIDATE_VERSION_UNAVAILABLE');evidence,rev=found;c=evidence.candidate
            require(rev==ref['revision'],'READ_CANDIDATE_VERSION_UNAVAILABLE');title=c.proposed_fields.get('title');title=title if isinstance(title,str) and 0<len(title)<=500 and title.strip() else None;data=dict(candidate_id=c.candidate_id,parser_version=c.parser_version,action=c.action,title=title,source_ref=c.source_record_id,target_ref=dict(task_id=c.target_task_id,revision=c.target_revision) if c.target_task_id else None)
        else:
            row=self.connection.execute('SELECT kind,source_record_ref,candidate_id,wire_hash,observed_wire,detected_at FROM whattodo.evidence_conflict WHERE conflict_id=%s',(ref['id'],)).fetchone()
            require(row is not None and sha256(bytes(row[4])).hexdigest()==row[3],'READ_CONFLICT_PROJECTION_DRIFT')
            if row[0]=='SOURCE':self._evidence._source(row[1])
            else:self._evidence._candidate(row[2])
            data=dict(conflict_kind=row[0],source_ref=row[1],candidate_id=row[2],detected_at=row[5].isoformat())
        if kind in ('EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT'):
            row=self.connection.execute('SELECT state,transaction_ref FROM whattodo.pending_evidence_revision WHERE pending_id=%s AND revision=%s',(ref['pending_id'],ref['pending_revision'])).fetchone()
            require(row==(ref['state'],ref['transaction_ref']),'READ_PENDING_STATE_DRIFT')
            data['pending_ref']=dict(pending_id=ref['pending_id'],revision=ref['pending_revision'])
        return dict(kind=kind,id=ref['id'],revision=ref['revision'],state=ref['state'],data=data)
    def _page(self,snapshot,query,index,caller):
        refs=snapshot.as_record()['references'];require(0<=index<=len(refs),'READ_CURSOR_POSITION');items=[];size=0
        for ref in refs[index:index+query.as_record()['page_size']]:
            item=self._item(ref,snapshot,caller);needed=len(canonical(item).encode());require(needed<MAX_PAGE_BYTES,'READ_ITEM_SIZE_LIMIT')
            if size+needed>MAX_PAGE_BYTES and items:break
            items.append(item);size+=needed
        return make_page(self.codec,snapshot,items,start_index=index,signer=self._signer,caller=caller)
    def query(self,raw,context,*,caller):
        require(isinstance(context,RequestContext),'READ_CONTEXT_REQUIRED')
        try:
            user(caller);query=admit_query(self.codec,raw)
            from psycopg import Error,OperationalError
            if query.cursor:
                key,index=self._signer.decode(query.cursor,principal_id=caller.principal_id,query_hash=query.fingerprint)
                with self._transaction():page=self._page(self._get_snapshot(key,query,caller),query,index,caller)
            else:
                with self._transaction(True):page=self._page(self._snapshot(query,caller),query,0,caller)
            return PortResult('SUCCESS','READ_PAGE',context.correlation_ref,page)
        except (TransactionError,TaskStorageError,EvidenceError) as exc:return PortResult('CONFLICT' if str(exc) in ('READ_SOURCE_SCOPE_CHANGED','READ_SNAPSHOT_EXPIRED','READ_CURSOR_SCOPE_CONFLICT') else 'PERMANENT',str(exc),context.correlation_ref)
        except MigrationError as exc:return PortResult('RETRYABLE' if str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else 'PERMANENT','READ_SCHEMA_UNAVAILABLE',context.correlation_ref)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',context.correlation_ref)
        except Exception as exc:
            import importlib.util
            if importlib.util.find_spec('psycopg') is not None:
                from psycopg import Error,OperationalError
                if isinstance(exc,Error):return PortResult('RETRYABLE' if isinstance(exc,OperationalError) or getattr(exc,'sqlstate',None) in ('40001','40P01','55P03') else 'PERMANENT','READ_DATABASE_UNAVAILABLE',context.correlation_ref)
            return PortResult('PERMANENT','READ_INTEGRITY_FAILED',context.correlation_ref)