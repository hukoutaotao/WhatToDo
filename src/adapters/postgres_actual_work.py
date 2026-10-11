"""Immutable actual report storage inside the coordinator's audited transaction."""
from src.adapters.postgres_migrations import schema_checked_transaction
from src.application.definitions import canonical
from src.application.ports import AggregateKey
from src.application.transactions import require,valid_permit
from src.application.work_reports import ActualWorkStorageRecord,admit_actual_record
from src.domain.task_aggregate import instant


class PostgresActualWorkRepository:
    def __init__(self,connection,codec,plan,*,application_version,clock,permits=()):
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock
        self._permits={p.permit_ref:p for p in permits}

    def get(self,observation_id):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            return self._get_in_transaction(observation_id)

    def total(self,task_id):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            return self._total_in_transaction(task_id)

    def _total_in_transaction(self,task_id):
        return int(self.connection.execute("SELECT COALESCE(sum(seconds),0) FROM whattodo.effort_observation WHERE task_id=%s AND kind='ACTUAL_WORK'",(task_id,)).fetchone()[0])

    def _projection(self,record,transaction_ref):
        v=record.as_record();r=record.report;f=r.as_record()
        return (r.observation_id,r.task_id,'ACTUAL_WORK',f['mode'],f['seconds'],v['previous_total_seconds'],v['increment_seconds'],v['resulting_total_seconds'],
            f['stage_id'],instant(f['session_started_at']) if f['session_started_at'] else None,
            instant(f['session_ended_at']) if f['session_ended_at'] else None,v['source_ref'],r.authority_ref,r.principal_id,v['recorded_task_revision'],
            transaction_ref,r.fingerprint,r.fact_fingerprint,record.content_hash,record.raw_bytes)

    def _get_in_transaction(self,observation_id):
        row=self.connection.execute('SELECT * FROM whattodo.actual_work_report WHERE observation_id=%s',(observation_id,)).fetchone()
        if row is None:return None
        record=admit_actual_record(self.codec,bytes(row[-1]));expected=self._projection(record,record.report.command_id)
        require(row[:-1]+(bytes(row[-1]),)==expected,'ACTUAL_WORK_PROJECTION_DRIFT')
        v=record.as_record();r=record.report
        observation=self.connection.execute('SELECT task_id,kind,seconds,observed_at,source_record_ref,authority_ref,transaction_ref FROM whattodo.effort_observation WHERE observation_id=%s',
            (r.observation_id,)).fetchone()
        require(observation==(r.task_id,'ACTUAL_WORK',v['increment_seconds'],instant(v['source_observed_at']),v['source_ref'],r.authority_ref,r.command_id),
            'ACTUAL_WORK_OBSERVATION_DRIFT')
        return record

    def _append_in_transaction(self,record,*,request,caller,permit_ref,audit_change_ref):
        from psycopg.pq import TransactionStatus
        require(self.connection.info.transaction_status==TransactionStatus.INTRANS,'ACTUAL_WORK_TRANSACTION_REQUIRED')
        require(isinstance(record,ActualWorkStorageRecord),'ACTUAL_WORK_TYPED_RECORD_REQUIRED')
        record=admit_actual_record(self.codec,record.raw_bytes);v=record.as_record();r=record.report
        require((r.command_id,r.principal_id,v['source_ref'])==
            (request.context.request_id,caller.principal_id,request.source_ref),'ACTUAL_WORK_EXACT_WRITE_REQUIRED')
        valid_permit(request,caller,self._permits.get(permit_ref),self.clock.now())
        write=next((w for w in request.writes if w.key==AggregateKey('WORK_REPORT',record.observation_id)),None)
        require(write is not None and write.expected_revision is None and write.body_json==canonical(v),'ACTUAL_WORK_EXACT_WRITE_REQUIRED')
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE').fetchone()==(request.expected_store_revision,),
            'STALE_STORE_REVISION')
        require(self.connection.execute('SELECT request_hash,principal_id,origin,authority_ref,xmin=pg_current_xact_id()::text::xid FROM whattodo.command_transaction WHERE request_id=%s',
            (request.context.request_id,)).fetchone()==(request.fingerprint,caller.principal_id,caller.origin,permit_ref,True),'ACTUAL_WORK_PREPARED_TRANSACTION_REQUIRED')
        require(self.connection.execute('SELECT principal_id,origin,source_record_ref FROM whattodo.authority_record WHERE authority_ref=%s',
            (r.authority_ref,)).fetchone()==(caller.principal_id,'USER_COMMAND',request.source_ref),'ACTUAL_WORK_ROOT_AUTHORITY_REQUIRED')
        require(self.connection.execute('SELECT audit_id,aggregate_kind,aggregate_id,before_revision,after_revision,before_value,after_value,request_id FROM whattodo.audit_change WHERE change_id=%s',
            (audit_change_ref,)).fetchone()==(request.audit_id,'WORK_REPORT',r.observation_id,None,1,None,v,request.context.request_id),'ACTUAL_WORK_PREPARED_AUDIT_REQUIRED')
        require(self._get_in_transaction(r.observation_id) is None,'ACTUAL_WORK_OBSERVATION_ALREADY_RECORDED')
        require(self._total_in_transaction(r.task_id)==v['previous_total_seconds'],'ACTUAL_WORK_TOTAL_CHANGED')
        require(instant(v['source_observed_at'])<=self.clock.now(),'WORK_REPORT_SOURCE_TIME_REQUIRED')
        # Both rows belong to the same outer transaction as Task/audit/receipt.
        self.connection.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (r.observation_id,r.task_id,'ACTUAL_WORK',v['increment_seconds'],instant(v['source_observed_at']),self.clock.now(),v['source_ref'],r.authority_ref,None,request.context.request_id))
        self.connection.execute('INSERT INTO whattodo.actual_work_report VALUES('+','.join(['%s']*20)+')',self._projection(record,request.context.request_id))
        require(self._get_in_transaction(r.observation_id)==record,'ACTUAL_WORK_ROUNDTRIP_FAILED')
