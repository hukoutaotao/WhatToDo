"""Fenced finite outbox processing with durable rule/chain checkpoints."""
from dataclasses import replace,asdict

from src.adapters.postgres_creation_outbox import PostgresCreationOutbox
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.adapters.postgres_migrations import schema_checked_transaction
from src.application.creation_outbox import DeliveryOutcome,DeliveryLease,OutboxError
from src.application.definitions import canonical,identity,DefinitionKey
from src.application.generation_commit import prepare_generation_commit,generation_scope,digest
from src.application.generation_evaluator import require
from src.application.generation_processing import ProcessingLimits,ProcessingCheckpoint,ProcessingBatch
from src.application.generation_runtime import GenerationPolicy
from src.application.ports import PortResult
from src.domain.authorization import CallerIdentity


class PostgresGenerationWorker:
    def __init__(self,connection,codec,plan,*,application_version,clock,policy,worker_id,definitions,limits=ProcessingLimits()):
        require(isinstance(policy,GenerationPolicy) and isinstance(limits,ProcessingLimits) and identity(worker_id)
            and len(policy.source_scopes)<=100,'PROCESSING_TRUSTED_WORKER_CONFIG')
        self.connection=connection;self.plan=plan;self.version=application_version;self.clock=clock
        self.policy=policy;self.worker_id=worker_id;self.limits=limits
        self.caller=CallerIdentity(policy.principal_id,'RELATIONSHIP_RULE',True)
        self.generator=PostgresGenerationHandler(connection,codec,plan,application_version=application_version,
            clock=clock,policy=policy,definitions=definitions)
        self.outbox=PostgresCreationOutbox(connection,plan,application_version=application_version,
            clock=clock,caller=self.caller,worker_id=worker_id,source_scopes=policy.source_scopes)

    def _transaction(self,*,write=False):
        return schema_checked_transaction(self.connection,self.plan,application_version=self.version,read_only=not write)

    def _fence(self,lease):
        row=self.outbox._owned(lease);self.outbox._live(row,lease,self.clock.now())
        return row

    def _lineage(self,event_id,depth=0):
        require(depth<=self.policy.limits.max_generation_depth,'PROCESSING_DEPTH_LIMIT')
        self.generator._source(event_id)
        row=self.connection.execute('SELECT root_event_id,parent_event_id,depth FROM whattodo.generation_chain_event WHERE event_id=%s',(event_id,)).fetchone()
        if row is not None:return row[0],row[2]
        parent=self.connection.execute('''SELECT g.source_event_ref FROM whattodo.canonical_creation_event e JOIN whattodo.generation_occurrence_revision g
            ON g.target_task_ref=e.task_id AND g.transaction_ref=e.creation_transaction_ref WHERE e.event_id=%s AND g.state='CREATED' ''',(event_id,)).fetchall()
        require(len(parent)<=1,'PROCESSING_AMBIGUOUS_LINEAGE')
        if parent:
            root,parent_depth=self._lineage(parent[0][0],depth+1);level=parent_depth+1
        else:root=event_id;level=0
        require(level<=self.policy.limits.max_generation_depth,'PROCESSING_DEPTH_LIMIT')
        self.connection.execute('INSERT INTO whattodo.generation_chain_event VALUES(%s,%s,%s,%s)',(event_id,root,parent[0][0] if parent else None,level))
        return root,level

    def _inputs(self,lease):
        self.generator._receipts={};source=self.generator._source(lease.event.event_id)
        current=self.generator.reader._get_in_transaction(source.event.task_id)
        require(current is not None,'PROCESSING_CURRENT_SOURCE_REQUIRED')
        keys=[];pins=[]
        for key in sorted(self.policy.rule_keys):
            use=self.generator._rule(key)
            if not use.record.rule.active or source.task.aggregate.as_record()['core']['task_type_ref']!={'id':use.record.source_type.id,'version':use.record.source_type.version}:
                continue
            keys.append(key)
            prior=self.generator._occurrence(generation_scope(source,use).generation_key)
            proposal=prepare_generation_commit(self.generator.codec,source,use,self.generator.definitions,expected_store_revision=1,
                previous=prior[0] if prior else None,current_source=current,current_bindings=self.generator._bindings(current),correlation_ref='processing-inputs')
            pins.append(dict(key=asdict(key),rule_hash=use.record.content_hash,manifest=proposal.plan.draft.manifest if proposal.plan else proposal.recorded.payload['manifest'] if proposal.recorded else {},
                state=proposal.plan.draft.state if proposal.plan else proposal.state,missing=list(proposal.plan.draft.missing_fields) if proposal.plan else []))
        stamp=digest(dict(policy=asdict(self.policy),source_hash=source.task.content_hash,current_hash=current.content_hash,rules=pins))
        return stamp,tuple(keys),source,current

    def _get(self,event_id):
        row=self.connection.execute('''SELECT r.revision,r.progress,r.lease_token FROM whattodo.generation_processing_head h
            JOIN whattodo.generation_processing_revision r USING(event_id,revision) WHERE event_id=%s''',(event_id,)).fetchone()
        return (row[0],ProcessingCheckpoint.from_payload(row[1]),row[2]) if row else None

    def _append(self,lease,checkpoint):
        from psycopg.types.json import Jsonb
        old=self._get(lease.event.event_id);revision=old[0]+1 if old else 1
        self.connection.execute('INSERT INTO whattodo.generation_processing_revision VALUES(%s,%s,%s,%s,%s,%s,%s)',
            (lease.event.event_id,revision,lease.revision,self.worker_id,lease.token,self.clock.now(),Jsonb(checkpoint.payload)))
        if old:
            require(self.connection.execute('UPDATE whattodo.generation_processing_head SET revision=%s WHERE event_id=%s AND revision=%s',
                (revision,lease.event.event_id,old[0])).rowcount==1,'PROCESSING_STALE_CHECKPOINT')
        else:self.connection.execute('INSERT INTO whattodo.generation_processing_head VALUES(%s,%s)',(lease.event.event_id,revision))
        return checkpoint

    def _slot(self,key):
        return self.connection.execute('''SELECT r.revision,r.root_event_id,r.source_event_id,r.rule_id,r.rule_version,r.target_role,r.state,r.worker_id,r.lease_token,r.occurrence_revision
            FROM whattodo.generation_chain_slot_head h JOIN whattodo.generation_chain_slot_revision r USING(generation_key,revision) WHERE generation_key=%s''',(key,)).fetchone()

    def _append_slot(self,lease,use,root,state,occurrence=None):
        scope=generation_scope(self.generator._source(lease.event.event_id),use);key=scope.generation_key;old=self._slot(key);revision=old[0]+1 if old else 1
        if old:
            require(old[1:4]+(old[5],)==(root,lease.event.event_id,use.record.rule.rule_id,use.record.rule.target_role),'PROCESSING_SLOT_SCOPE')
            require(old[6]!='CREATED' or state=='CREATED','PROCESSING_CREATED_SLOT_TERMINAL')
        self.connection.execute('INSERT INTO whattodo.generation_chain_slot_revision VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (key,revision,root,lease.event.event_id,use.record.rule.rule_id,use.record.rule.version,use.record.rule.target_role,state,
                self.worker_id,lease.token,lease.revision,occurrence.revision if occurrence is not None and state=='CREATED' else None,self.clock.now()))
        if old:
            require(self.connection.execute('UPDATE whattodo.generation_chain_slot_head SET revision=%s WHERE generation_key=%s AND revision=%s',
                (revision,key,old[0])).rowcount==1,'PROCESSING_STALE_SLOT')
        else:self.connection.execute('INSERT INTO whattodo.generation_chain_slot_head VALUES(%s,%s)',(key,revision))

    def _usage(self,root):
        # Actual canonical counterparts, including those created before this
        # worker, plus live reservations not yet represented by CREATED rows.
        cap=self.policy.limits.max_generated_instances;depth=self.policy.limits.max_generation_depth
        rows=self.connection.execute('''WITH RECURSIVE events(event_id,depth) AS (
            SELECT %s::text,0 UNION ALL SELECT e.event_id::text,p.depth+1 FROM events p
            JOIN whattodo.generation_occurrence g ON g.source_event_ref=p.event_id AND g.state='CREATED'
            JOIN whattodo.canonical_creation_event e ON e.task_id=g.target_task_ref AND e.creation_transaction_ref=g.transaction_ref
            WHERE p.depth<=%s)
            SELECT g.generation_key FROM events p JOIN whattodo.generation_occurrence g ON g.source_event_ref=p.event_id
            WHERE g.state='CREATED' LIMIT %s''',(root,depth,cap+1)).fetchall()
        require(len(rows)<=cap,'PROCESSING_INSTANCE_LIMIT')
        reserved=self.connection.execute('''SELECT r.generation_key FROM whattodo.generation_chain_slot_head h
            JOIN whattodo.generation_chain_slot_revision r USING(generation_key,revision) WHERE r.root_event_id=%s AND r.state='RESERVED'
            AND NOT EXISTS(SELECT 1 FROM whattodo.generation_occurrence g WHERE g.generation_key=r.generation_key AND g.state='CREATED') LIMIT %s''',(root,cap+1)).fetchall()
        return len(rows)+len(reserved)

    def _start(self,lease):
        with self._transaction(write=True):
            self._fence(lease);stamp,keys,_,_=self._inputs(lease);self._lineage(lease.event.event_id)
            old=self._get(lease.event.event_id)
            if old is not None and old[1].input_hash!=stamp:self._release_slots(lease,old[1].rule_keys)
            checkpoint=ProcessingCheckpoint(stamp,keys) if old is None or old[1].input_hash!=stamp else replace(old[1],
                attempts=old[1].attempts+(old[2]!=lease.token and old[1].code!='GENERATION_BATCH_CONTINUES'),state='RUNNING',code=None)
            return self._append(lease,checkpoint)

    def _release_slots(self,lease,keys):
        source=self.generator._source(lease.event.event_id);root,_=self._lineage(source.event.event_id)
        candidates=[]
        for key in keys:
            use=self.generator._rule(key);slot=self._slot(generation_scope(source,use).generation_key)
            if slot is not None and slot[6]=='RESERVED':candidates.append(use)
        if not candidates:return
        self.connection.execute('SELECT event_id FROM whattodo.generation_chain_event WHERE event_id=%s FOR UPDATE NOWAIT',(root,)).fetchone()
        for use in candidates:
            actual=self.generator._occurrence(generation_scope(source,use).generation_key)
            if actual is not None and actual[0].state=='CREATED':
                self.generator._receipt(actual[1]);self._append_slot(lease,use,root,'CREATED',actual[0])
            else:self._append_slot(lease,use,root,'RELEASED')

    def _reserve(self,lease,key):
        with self._transaction(write=True):
            self._fence(lease);self.generator._receipts={}
            source=self.generator._source(lease.event.event_id);use=self.generator._rule(key,at=self.clock.now())
            root,level=self._lineage(source.event.event_id)
            self.connection.execute('SELECT event_id FROM whattodo.generation_chain_event WHERE event_id=%s FOR UPDATE NOWAIT',(root,)).fetchone()
            current=self.generator.reader._get_in_transaction(source.event.task_id)
            old=self.generator._occurrence(generation_scope(source,use).generation_key)
            if old and old[0].state=='CREATED':return
            proposal=prepare_generation_commit(self.generator.codec,source,use,self.generator.definitions,expected_store_revision=1,
                previous=old[0] if old else None,current_source=current,current_bindings=self.generator._bindings(current),correlation_ref='processing-reserve')
            if proposal.plan is None or not proposal.plan.draft.ready:return
            require(level<self.policy.limits.max_generation_depth,'PROCESSING_DEPTH_LIMIT')
            slot=self._slot(generation_scope(source,use).generation_key)
            used=self._usage(root)
            require(used<self.policy.limits.max_generated_instances or slot is not None and slot[6]=='RESERVED','PROCESSING_INSTANCE_LIMIT')
            self._append_slot(lease,use,root,'RESERVED')

    def _record(self,lease,checkpoint,key,outcome):
        with self._transaction(write=True):
            self._fence(lease);self.generator._receipts={}
            source=self.generator._source(lease.event.event_id);use=self.generator._rule(key)
            root,_=self._lineage(source.event.event_id);self.connection.execute('SELECT event_id FROM whattodo.generation_chain_event WHERE event_id=%s FOR UPDATE NOWAIT',(root,)).fetchone()
            slot=self._slot(generation_scope(source,use).generation_key)
            actual=self.generator._occurrence(generation_scope(source,use).generation_key)
            if outcome.occurrence is not None:
                require(actual is not None and actual[0]==outcome.occurrence and self.generator._receipt(actual[1])[0]==outcome.receipt,'PROCESSING_RESULT_NOT_COMMITTED')
            if outcome.state=='CREATED':self._append_slot(lease,use,root,'CREATED',outcome.occurrence)
            elif slot is not None and slot[6]=='RESERVED':self._append_slot(lease,use,root,'RELEASED')
            results=checkpoint.payload['results']+[dict(rule=asdict(key),state=outcome.state,
                occurrence_ref=outcome.occurrence.scope.generation_key if outcome.occurrence else None,receipt_ref=outcome.receipt.request_id if outcome.receipt else None)]
            stamp,_,_,_=self._inputs(lease)
            return self._append(lease,replace(checkpoint,input_hash=stamp,cursor=checkpoint.cursor+1,results_json=canonical(results),attempts=1))

    def _finish(self,lease,checkpoint,*,code=None,retryable=False):
        if code is not None:
            state='RUNNING' if retryable or code in ('GENERATION_STORAGE_UNAVAILABLE','GENERATION_RESERVATION_REQUIRED','GENERATION_ACKNOWLEDGEMENT_LOST','PROCESSING_STORAGE_RETRY') else 'FAILED'
            if state=='RUNNING' and checkpoint.attempts>=self.limits.max_attempts:state='FAILED';code='PROCESSING_RETRY_LIMIT'
        elif checkpoint.cursor<len(checkpoint.rule_keys):state='RUNNING';code='GENERATION_BATCH_CONTINUES'
        else:
            states=[v['state'] for v in checkpoint.payload['results']]
            state='FAILED' if 'FAILED' in states else 'WAITING_FACTS' if 'PENDING' in states else 'DONE'
            code='GENERATION_PARENT_OR_MAPPING_CONFLICT' if state=='FAILED' else None
        checkpoint=replace(checkpoint,state=state,code=code)
        with self._transaction(write=True):
            self._fence(lease)
            if code is not None and checkpoint.rule_keys:self._release_slots(lease,checkpoint.rule_keys)
            self._append(lease,checkpoint)
        settled=self.outbox.settle(lease,checkpoint.outcome(now=self.clock.now(),limits=self.limits))
        return checkpoint,settled

    def _process(self,lease):
        try:checkpoint=self._start(lease)
        except (ValueError,RuntimeError) as exc:
            import re
            code=str(exc);code=code if re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code) else 'PROCESSING_INVALID_INPUT'
            checkpoint=ProcessingCheckpoint(digest(dict(event=lease.event.event_id,policy=asdict(self.policy))),(),state='FAILED',code=code)
            return self._finish(lease,checkpoint,code=code)[0]
        if checkpoint.attempts>self.limits.max_attempts:
            return self._finish(lease,checkpoint,code='PROCESSING_RETRY_LIMIT')[0]
        for _ in range(self.limits.max_rules_per_lease):
            if checkpoint.cursor>=len(checkpoint.rule_keys):break
            # Renew before a long event's next independent rule transaction.
            if (lease.expires_at-self.clock.now()).total_seconds()<self.limits.lease_seconds/2:
                lease=self.outbox.renew(lease,lease_seconds=self.limits.lease_seconds)
            key=checkpoint.rule_keys[checkpoint.cursor]
            try:self._reserve(lease,key)
            except (ValueError,RuntimeError) as exc:return self._finish(lease,checkpoint,code=str(exc))[0]
            except Exception as exc:
                if getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                    return self._finish(lease,checkpoint,code='PROCESSING_STORAGE_RETRY')[0]
                raise
            result=self.generator.generate(lease.event.event_id,key.id,correlation_ref='processing-'+self.worker_id,caller=self.caller,lease=lease)
            if result.status=='UNKNOWN':result=self.generator.lookup(lease.event.event_id,key.id,correlation_ref='processing-reconcile',caller=self.caller)
            if result.status!='SUCCESS':return self._finish(lease,checkpoint,code=result.code,retryable=result.status in ('RETRYABLE','UNKNOWN'))[0]
            checkpoint=self._record(lease,checkpoint,key,result.value)
        return self._finish(lease,checkpoint)[0]

    def run_batch(self):
        try:
            import psycopg
        except ImportError:raise OutboxError('TRANSACTION_DRIVER_UNAVAILABLE') from None
        states=[]
        for _ in range(self.limits.max_events):
            lease=self.outbox.claim(lease_seconds=self.limits.lease_seconds)
            if lease is None:return ProcessingBatch(len(states),tuple(states),True)
            try:checkpoint=self._process(lease)
            except Exception as exc:
                # No fabricated completion. A vanished connection leaves the
                # live lease/checkpoint for expiry and scoped restart recovery.
                raise OutboxError('PROCESSING_STORAGE_RETRY') from None
            states.append(checkpoint.state)
        return ProcessingBatch(len(states),tuple(states),False)

    def wake(self,event_id):
        require(identity(event_id),'PROCESSING_EVENT_ID')
        from uuid import uuid4
        from datetime import timedelta
        with self._transaction(write=True):
            row=self.outbox._select(' AND e.event_id=%s',(event_id,),' FOR UPDATE OF h')
            require(row is not None,'PROCESSING_EVENT_NOT_OWNED')
            if row[9] not in ('WAITING_FACTS','FAILED'):return None
            event=self.outbox._snapshot(row).event
            # Temporary typed context is used only for independent input reads;
            # it grants no lease or write authority.
            probe=DeliveryLease(event,row[8]+1,row[10]+1,self.worker_id,uuid4().hex,self.clock.now(),self.clock.now()+timedelta(seconds=self.limits.lease_seconds))
            stamp,_,_,_=self._inputs(probe);old=self._get(event_id)
            require(old is not None,'PROCESSING_CHECKPOINT_REQUIRED')
            if stamp==old[1].input_hash:return None
            fresh=self.outbox._append(row,state='CLAIMED',now=self.clock.now(),attempt=row[10]+1,worker=self.worker_id,
                token=uuid4().hex,until=self.clock.now()+timedelta(seconds=self.limits.lease_seconds)).lease
        return self._process(fresh)
