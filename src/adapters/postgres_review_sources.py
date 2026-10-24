"""Complete admitted review-source enumeration inside one owned SQL snapshot.

No producer here mutates Tasks or acknowledges answers. Existing read-only
admission helpers verify immutable source/Task/journal/receipt provenance; none
of their command entrypoints is called. Unsupported legacy producers are visible
coverage gaps, never an apparently complete empty result.
"""
from hashlib import sha256

from src.adapters.postgres_read_models import PostgresReadService
from src.adapters.postgres_stage_commands import PostgresStageCommandHandler
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.application.definitions import DefinitionKey,canonical,strict_json
from src.application.generation_runtime import GenerationPolicy
from src.application.evidence_storage import EvidenceError
from src.application.review_queue import ReviewQueueItem,MAX_ITEMS
from src.application.relationship_validation import GraphLimits
from src.application.task_resolution import user,resolution_handoff
from src.application.transactions import TransactionError,require

SOURCE_VERSION='0.1.1-review-sources'
# This is immutable history admission, not a fresh generation request. A
# previously accepted deep lineage must not become unreadable merely because
# the execution policy's default depth is smaller than its original policy.
RECEIPT_LIMITS=GraphLimits(max_generation_depth=100000)


class PostgresReviewSources:
    def __init__(self,connection,codec,plan,*,application_version,clock,source_scopes,cursor_key,definitions=None):
        self.connection=connection;self.codec=codec;self.plan=plan;self.clock=clock
        self.application_version=application_version;self.scopes=source_scopes;self.definitions=definitions
        self.owners=PostgresStageCommandHandler(connection,codec,plan,application_version=application_version,
            clock=clock,source_scopes=source_scopes,definitions=definitions,limits=RECEIPT_LIMITS)
        self.read=PostgresReadService(connection,codec,plan,application_version=application_version,
            clock=clock,cursor_key=cursor_key,scopes=source_scopes)

    @property
    def scope_hash(self):
        return sha256(canonical(dict(source_version=SOURCE_VERSION,scopes=[dict(provider=s.provider,scope_ref=s.scope_ref,
            account_ref=s.account_ref) for s in sorted(self.scopes,key=lambda s:(s.provider,s.scope_ref,s.account_ref))])).encode()).hexdigest()

    def validate_scope(self):
        for scope in self.scopes:self.owners.evidence._scope(scope.provider,scope.scope_ref)

    def _scope_sql(self,alias='si'):
        # Values, including account identities, are exclusively trusted bindings.
        return ('('+' OR '.join(f'({alias}.provider=%s AND {alias}.scope_ref=%s)' for _ in self.scopes)+')',
            tuple(v for s in self.scopes for v in (s.provider,s.scope_ref)))

    def _rows(self,sql,params=()):
        cursor=self.connection.execute(sql,params);count=0
        while True:
            rows=cursor.fetchmany(500)
            if not rows:break
            for row in rows:
                count+=1;require(count<=MAX_ITEMS,'REVIEW_QUEUE_SOURCE_LIMIT')
                yield row

    def _add(self,item):
        self.items.append(item)
        require(len(self.items)<=MAX_ITEMS,'REVIEW_QUEUE_SOURCE_LIMIT')

    def _block(self,code,*,source_id='review-source-coverage',revision=1,source_kind='UNADMITTED'):
        self.blockers.add(code)
        self._add(ReviewQueueItem('SOURCE_BLOCKER',source_id,revision,code,None,0,None,'review-source-coverage',
            details_json=canonical(dict(source_kind=source_kind))))

    def _group(self,record):
        core=record.aggregate.as_record()['core'];ctx=core['context']
        return ctx['id'] if ctx is not None else 'domain-'+core['domain']

    def _record(self,task_id,caller,revision=None):
        return self.owners._owned_task(task_id,caller.principal_id,revision=revision)

    def _tasks(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT h.task_id,h.revision,c.origin FROM whattodo.task_head h
            JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(h.task_id,h.revision)
            JOIN whattodo.task_identity i ON i.task_id=h.task_id
            JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref
            JOIN whattodo.authority_record a ON a.authority_ref=c.authority_ref
            JOIN whattodo.source_record sr ON sr.record_id=a.source_record_ref
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id
            WHERE c.principal_id=%s AND t.completion='INCOMPLETE' AND t.disposition='ACTIVE' AND '''+scope+' ORDER BY h.task_id'
        for task_id,revision,origin in self._rows(sql,(caller.principal_id,*params)):
            if origin=='RELATIONSHIP_RULE' and self.definitions is None:
                self._block('TASK_GENERATION_DEFINITIONS_UNAVAILABLE',source_id=task_id,revision=revision,source_kind='TASK')
                continue
            record=self._record(task_id,caller,revision);value=record.aggregate.as_record();core=value['core']
            require((core['completion'],core['disposition'])==('INCOMPLETE','ACTIVE'),'REVIEW_QUEUE_TASK_STATE_DRIFT')
            estimate=value['effort']['user_remaining']
            # There is no admitted explicit untouched-since-verification evidence
            # yet. No records (or zero actual seconds) is not such a statement.
            details=dict(completion=core['completion'],disposition=core['disposition'],requiredness=core['requiredness'],
                work_status='UNKNOWN',estimate_status='MISSING' if estimate is None else 'UNCERTAIN',user_remaining=estimate)
            self._add(ReviewQueueItem('TASK_ESTIMATE',task_id,revision,'ESTIMATE_MISSING' if estimate is None else 'ESTIMATE_VERIFICATION',
                core['title'],3 if estimate is None else 5,core['importance'],self._group(record),(),task_id,revision,canonical(details)))

    def _manual(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT p.pending_id,p.command_id,p.desired_task_id,p.source_record_ref,p.proposal_bytes
            FROM whattodo.manual_creation_pending p JOIN whattodo.source_record sr ON sr.record_id=p.source_record_ref
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id WHERE p.principal_id=%s AND '''+scope+' ORDER BY p.pending_id'
        for key,command,desired,source,raw in self._rows(sql,(caller.principal_id,*params)):
            self.owners._source(source)
            data=self.read._item(self.read._reference('MANUAL_CREATION',key,1,'OPEN'),None,caller)['data']
            commit=self.connection.execute('SELECT 1 FROM whattodo.command_transaction WHERE request_id=%s AND principal_id=%s',
                (command,caller.principal_id)).fetchone()
            if commit is not None:
                match=self.connection.execute("SELECT 1 FROM whattodo.audit_change WHERE request_id=%s AND aggregate_kind='TASK' AND aggregate_id=%s AND before_revision IS NULL AND after_revision=1",
                    (command,desired)).fetchone()
                if match is not None:
                    self._record(desired,caller,1)
                    continue
            proposal=strict_json(bytes(raw));data['proposal']=proposal
            self._add(ReviewQueueItem('MANUAL_CREATION',key,1,'COMMIT_SCOPE_CONFLICT' if commit else 'MISSING_CREATION_DETAILS',
                data['title'],1,None,'pending-creation',(source,),details_json=canonical(data)))

    def _clarifications(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT h.session_id,h.revision FROM whattodo.command_resolution_head h
            JOIN whattodo.command_resolution_revision r USING(session_id,revision)
            JOIN whattodo.source_record sr ON sr.record_id=r.last_source_ref
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id WHERE h.principal_id=%s AND '''+scope+' ORDER BY h.session_id'
        for key,revision in self._rows(sql,(caller.principal_id,*params)):
            frame=self.read._resolution._get(key,caller,revision);require(frame is not None,'REVIEW_QUEUE_CLARIFICATION_UNAVAILABLE')
            v=frame.as_record()
            try:
                for ref in set((v['query_source_ref'],v['last_source_ref'])):self.owners._source(ref)
                # All displayed candidates also need current account ownership.
                for choice in v['choices']:
                    if choice['kind']=='TASK':self._record(choice['id'],caller,choice['revision'])
                if v['selected_task_ref'] is not None:
                    target=v['selected_task_ref'];self._record(target['task_id'],caller,target['revision'])
            except (TransactionError,EvidenceError) as exc:
                if str(exc) not in ('STAGE_GENERATED_DEFINITIONS_REQUIRED','STAGE_PARENT_NOT_OWNED',
                    'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED'):raise
                self._block('CLARIFICATION_TARGET_SCOPE_UNAVAILABLE',source_id=key,revision=revision,source_kind='CLARIFICATION')
                continue
            commit=self.connection.execute('''SELECT a.resolved_scope,e.source_record_ref FROM whattodo.command_transaction c
                JOIN whattodo.authority_record a ON a.authority_ref=c.authority_ref
                JOIN whattodo.audit_entry e ON e.audit_id=c.audit_id WHERE c.request_id=%s AND c.principal_id=%s''',
                (v['command_id'],caller.principal_id)).fetchone()
            if commit is not None and v['state']=='RESOLVED':
                annotation=commit[0].get('authorization',{});grant=annotation.get('grant_ref')
                if grant is not None and commit[1]==v['last_source_ref']:
                    handoff=resolution_handoff(frame,authority_ref=grant,caller=caller)
                    if handoff.command.fingerprint==annotation.get('command_fingerprint'):continue
            reason='COMMIT_SCOPE_CONFLICT' if commit else ('AWAITING_EXECUTION' if v['state']=='RESOLVED' else 'CLARIFICATION_REQUIRED')
            # Retain the original intent/known fields. A resolved intent is an
            # execution item, not a request to confirm the same facts again.
            self._add(ReviewQueueItem('CLARIFICATION',key,revision,reason,v['fields'].get('title'),1,None,'pending-clarification',
                tuple(sorted(set((v['query_source_ref'],v['last_source_ref'])))),details_json=canonical(v)))

    def _evidence(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT p.kind,p.candidate_id,p.conflict_id,h.revision,r.transaction_ref,p.pending_id,
            coalesce(ch.revision,1) FROM whattodo.pending_evidence_identity p
            JOIN whattodo.pending_evidence_head h USING(pending_id) JOIN whattodo.pending_evidence_revision r USING(pending_id,revision)
            LEFT JOIN whattodo.evidence_conflict f ON f.conflict_id=p.conflict_id
            LEFT JOIN whattodo.candidate_identity i ON i.candidate_id=coalesce(p.candidate_id,f.candidate_id)
            LEFT JOIN(SELECT candidate_id,max(revision) revision FROM whattodo.candidate_revision GROUP BY candidate_id) ch ON ch.candidate_id=i.candidate_id
            JOIN whattodo.source_record sr ON sr.record_id=coalesce(i.source_record_ref,f.source_record_ref)
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id WHERE r.state='OPEN' AND '''+scope+' ORDER BY p.pending_id'
        for kind,candidate,conflict,pending_revision,tx,pid,revision in self._rows(sql,params):
            chosen='EVIDENCE_CANDIDATE' if kind=='CANDIDATE' else 'EVIDENCE_CONFLICT';key=candidate if candidate else conflict
            ref=self.read._reference(chosen,key,revision if candidate else 1,'OPEN',transaction=tx,pending=pid,pending_revision=pending_revision)
            data=self.read._item(ref,None,caller)['data'];source=data['source_ref']
            if candidate:
                evidence,_=self.owners.evidence._candidate(candidate,revision);c=evidence.candidate
                data.update(proposed_fields=strict_json(c.proposed_fields_json),confidence_decimal=str(c.confidence),proposal_hash=evidence.proposal_hash)
                # This is a proposal from an admitted external source. Its
                # target identity is data, not permission to read that Task.
                data['target_admission']='NOT_CONFIRMED'
            elif data.get('candidate_id') is not None:
                source=self.owners.evidence._candidate(data['candidate_id'])[0].candidate.source_record_id
            self._add(ReviewQueueItem(chosen,key,revision if candidate else 1,'EXTERNAL_CONFIRMATION' if candidate else 'EVIDENCE_CONFLICT',
                data.get('title'),2 if candidate else 0,None,'pending-evidence',tuple([source]) if source is not None else (),details_json=canonical(data)))

    def _generation(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT g.generation_key,g.revision,g.runtime_payload,g.rule_id,g.rule_version
            FROM whattodo.generation_occurrence g JOIN whattodo.task_identity i ON i.task_id=g.source_task_id
            JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref
            JOIN whattodo.authority_record a ON a.authority_ref=c.authority_ref
            JOIN whattodo.source_record sr ON sr.record_id=a.source_record_ref
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id
            WHERE c.principal_id=%s AND g.state IN('PENDING','FAILED') AND '''+scope+' ORDER BY g.generation_key'
        for key,revision,payload,rule_id,version in self._rows(sql,(caller.principal_id,*params)):
            if payload is None:
                self._block('LEGACY_GENERATION_SOURCE_UNADMITTED',source_id=key,revision=revision,source_kind='GENERATION')
                continue
            if self.definitions is None:
                self._block('GENERATION_DEFINITIONS_UNAVAILABLE',source_id=key,revision=revision,source_kind='GENERATION')
                continue
            policy=GenerationPolicy(caller.principal_id,(DefinitionKey('RELATIONSHIP_RULE',rule_id,version),),self.scopes,RECEIPT_LIMITS)
            handler=PostgresGenerationHandler(self.connection,self.codec,self.plan,application_version=self.application_version,
                clock=self.clock,policy=policy,definitions=self.definitions)
            found=handler._occurrence(key,revision);require(found is not None,'REVIEW_QUEUE_GENERATION_UNAVAILABLE')
            record,tx,_=found
            current=handler._occurrence(key);require(current==found,'REVIEW_QUEUE_GENERATION_HEAD_DRIFT')
            receipt,annotation,source=handler._receipt(tx)
            require(annotation.get('generation')==record.payload,'REVIEW_QUEUE_GENERATION_RECEIPT_DRIFT')
            parent=self._record(record.scope.source_task_id,caller)
            details=dict(state=record.state,rule_ref=dict(id=rule_id,version=version),source_event_ref=record.scope.creation_event_ref,
                obligation_kind=record.obligation_kind,missing_fields=list(record.missing_fields),failure_code=record.failure_code,
                receipt_ref=receipt.request_id)
            self._add(ReviewQueueItem('GENERATION_'+record.state,key,revision,
                'GENERATION_MISSING_DETAILS' if record.state=='PENDING' else record.failure_code,
                parent.aggregate.as_record()['core']['title'],1,None,self._group(parent),(source,),parent.task_id,parent.revision,canonical(details)))

    def _stages(self,caller):
        scope,params=self._scope_sql()
        sql='''SELECT j.record_id FROM whattodo.stage_command_journal j
            JOIN whattodo.source_record sr ON sr.record_id=j.source_ref
            JOIN whattodo.source_identity si ON si.source_id=sr.source_id
            WHERE j.state='PENDING' AND j.runtime_payload#>>'{command,principal_id}'=%s
             AND NOT EXISTS(SELECT 1 FROM whattodo.stage_pending_resolution r WHERE r.pending_ref=j.record_id)
             AND '''+scope+' ORDER BY j.record_id'
        for key, in self._rows(sql,(caller.principal_id,*params)):
            journal,tx,_=self.owners._journal(key);c=journal.command
            self.owners._source(journal.source_ref)
            before=self._record(c.task_id,caller,c.expected_revision)
            require(before.content_hash==journal.before_task_hash,'REVIEW_QUEUE_STAGE_PARENT_DRIFT')
            parent=self._record(c.task_id,caller)
            # Retained pending correction/new-obligation intents remain visible
            # even if the parent later completed or changed disposition.
            self._add(ReviewQueueItem('STAGE_PENDING',key,1,journal.code,parent.aggregate.as_record()['core']['title'],1,
                parent.aggregate.as_record()['core']['importance'],self._group(parent),(journal.source_ref,),c.task_id,parent.revision,
                canonical(dict(command=c.as_record(),missing_fields=list(journal.missing_fields),receipt_ref=tx))))

    def collect_in_transaction(self,caller):
        from psycopg.pq import TransactionStatus
        user(caller);require(self.connection.info.transaction_status==TransactionStatus.INTRANS,'REVIEW_QUEUE_OPEN_TRANSACTION')
        self.items=[];self.blockers=set();self.owners._owners=set();self.validate_scope()
        if not self.scopes:self._block('SOURCE_SCOPE_UNCONFIGURED')
        else:
            for producer in (self._tasks,self._manual,self._clarifications,self._evidence,self._generation,self._stages):producer(caller)
        # Legacy tables have no trusted principal/account admission. Reveal no
        # row content or counts; explicitly acknowledge unavailable coverage.
        for table,code in (('behavior_candidate','BEHAVIOR_REVIEW_SOURCE_UNADMITTED'),('review_frame','LEGACY_REVIEW_SOURCE_UNADMITTED')):
            if self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.'+table+')').fetchone()[0]:self._block(code)
        return tuple(self.items),tuple(sorted(self.blockers))
