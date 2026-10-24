"""Synthetic native Task storage; fixture coordinator is not a live handler."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles, apply_migrations, schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.ports import AggregateKey, CommitRequest, RecordWrite, RequestContext, TransactionPermit
from src.application.definitions import DefinitionKey
from src.application.task_storage import TaskStorageBindings, TaskStorageError, admit_storage, sql_value
from src.domain.authorization import CallerIdentity
from tools.check_contract_registry import trusted_schemas
from tools.postgres_harness import HarnessError, PostgresHarness, ROLES, require
from tools.verify_toolchain import native_transactions

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CALLER = CallerIdentity('principal', 'USER_COMMAND', True)


def verify(harness, report):
    import psycopg
    from psycopg.types.json import Jsonb
    plan = load_migration_plan(root=ROOT)
    old = load_migration_plan(root=ROOT, manifest_path=ROOT/'reports/acceptance/M3A-06-migration-plan.json')
    roles = DatabaseRoles(ROLES['migration'], ROLES['application'], ROLES['test'])
    codec = ContractJSONCodec(trusted_schemas())
    clock = FrozenClock(NOW)
    checks = report['native_checks']
    cases = json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text())['cases']
    name = harness.create_database(initialize_schema=False)

    def example(case, task_id):
        value = deepcopy(next(c['payload'] for c in cases if c['id'] == case))
        value['core']['task_id'] = value['effort']['task_id'] = task_id
        value['core']['acceptance']['authority_ref'] = 'authority'
        if value['effort']['user_remaining']:
            value['effort']['user_remaining']['observation_id'] = 'estimate-'+task_id
        for stage in value['effort']['stages']:
            if stage['user_remaining']:
                stage['user_remaining']['observation_id'] = 'estimate-'+stage['stage_id']
        if value['timing']['release']:
            value['timing']['release']['source_ref'] = 'record'
        if value['timing']['deadline']:
            value['timing']['deadline']['value']['source_ref'] = 'record'
            value['timing']['deadline']['due_ref'] = 'due-'+task_id
        if value['work']['total_estimate']:
            value['work']['total_estimate']['source_ref'] = 'record'
        for p in value['provenance']:
            p['source_ref'] = 'record'
        return value

    with harness.target(name, 'migration').connect() as migration:
        apply_migrations(migration, old, roles=roles, application_version=__version__)
        native_transactions(migration)
        with migration.transaction():
            migration.execute("INSERT INTO whattodo.command_transaction VALUES('legacy-create',%s,'principal','USER_COMMAND','authority',2,3,'legacy-audit',%s,%s)",
                ('e'*64, NOW, Jsonb(dict(synthetic=True))))
            migration.execute("INSERT INTO whattodo.audit_entry VALUES('legacy-audit','legacy-create','record','legacy-correlation',%s)", (NOW,))
            migration.execute("INSERT INTO whattodo.audit_change VALUES('legacy-change','legacy-audit','TASK','legacy-task',NULL,1,NULL,%s,'legacy-create')",
                (Jsonb(dict(synthetic=True)),))
            migration.execute("INSERT INTO whattodo.task_identity VALUES('legacy-task','legacy-create',%s)", (NOW,))
            migration.execute('''INSERT INTO whattodo.task_revision(task_id,revision,title,domain,acceptance_ref,
                completion,disposition,requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,
                audit_change_ref,aggregate_kind,transaction_ref,metadata)
                VALUES('legacy-task',1,'Synthetic legacy core','study','authority','INCOMPLETE','ACTIVE','REQUIRED',3,3,3,3,
                'legacy-change','TASK','legacy-create',%s)''', (Jsonb(dict(trust='UNKNOWN',overdue='UNKNOWN')),))
            migration.execute("INSERT INTO whattodo.stage_revision VALUES('legacy-stage',3,'legacy-task',1,'Known historical stage','INCOMPLETE',NULL,'authority','legacy-create',NULL,NULL)")
            migration.execute("UPDATE whattodo.store_epoch SET revision=3,last_transaction_ref='legacy-create' WHERE singleton=TRUE AND revision=2")
        old_stage = migration.execute("SELECT * FROM whattodo.stage_revision WHERE stage_id='legacy-stage'").fetchall()
        before = migration.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        upgraded = apply_migrations(migration, plan, roles=roles, application_version=__version__)
        require(upgraded.applied == tuple(s.migration_id for s in plan.steps[len(old.steps):]), 'TASK_STORAGE_FORWARD_UPGRADE')
        require(migration.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=7 ORDER BY position').fetchall() == before,
            'TASK_STORAGE_CHANGED_OLD_RECEIPTS')
        checks.append('eighth_step_preserves_all_seven_existing_receipts')
        require(migration.execute("SELECT * FROM whattodo.stage_revision WHERE stage_id='legacy-stage'").fetchall()==old_stage
            and migration.execute("SELECT task_id,transaction_ref FROM whattodo.stage_identity WHERE stage_id='legacy-stage'").fetchone()==('legacy-task','legacy-create'),
            'TASK_STORAGE_LEGACY_STAGE_OWNER')
        checks.append('forward_upgrade_binds_existing_stage_owner_without_rewriting_its_history')

    with harness.target(name).connect() as conn:
        reader = PostgresTaskRepository(conn, codec, plan, application_version=__version__, clock=clock)
        require(reader.get('unknown') is None and reader.list_current() == (), 'TASK_STORAGE_EMPTY_QUERY')
        checks.append('unknown_task_and_empty_current_query_are_explicit')
        try:
            reader.get('legacy-task', 1)
        except TaskStorageError as exc:
            require(str(exc)=='TASK_STORAGE_LEGACY_PAYLOAD_UNAVAILABLE','TASK_STORAGE_LEGACY_CODE')
        else:
            raise HarnessError('TASK_STORAGE_FABRICATED_LEGACY_PAYLOAD')
        checks.append('legacy_core_without_wire_bytes_is_explicitly_unavailable_not_guessed')

        def publish(value, request_id, expected=None, *, fail=None, caller=CALLER,
                    include_permit=True, catch_append_error=False, bindings=TaskStorageBindings()):
            record = admit_storage(codec, json.dumps(value, ensure_ascii=False, indent=2).encode())
            epoch = conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
            request = CommitRequest(RequestContext(request_id, 'correlation-'+request_id),
                CALLER.principal_id, epoch,
                (RecordWrite(AggregateKey('TASK', record.task_id), expected, json.dumps(value)),),
                'audit-'+request_id, 'record')
            permit = TransactionPermit('permit-'+request_id, CALLER.principal_id, CALLER.origin,
                request.fingerprint, NOW-timedelta(minutes=1), NOW+timedelta(hours=1))
            repo = PostgresTaskRepository(conn, codec, plan, application_version=__version__,
                clock=clock, permits=(permit,) if include_permit else ())
            with schema_checked_transaction(conn, plan, application_version=__version__, read_only=False):
                conn.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (permit.permit_ref, CALLER.principal_id, CALLER.origin, 'record', request.fingerprint,
                    Jsonb(dict(request_fingerprint=request.fingerprint, synthetic=True)), permit.issued_at, permit.expires_at))
                conn.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (request_id, request.fingerprint, CALLER.principal_id, CALLER.origin, permit.permit_ref,
                    epoch, epoch+1, request.audit_id, NOW, Jsonb(dict(synthetic=True))))
                conn.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
                    (request.audit_id, request_id, 'record', request.context.correlation_ref, NOW))
                previous = repo._get_in_transaction(record.task_id)
                conn.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('change-'+request_id, request.audit_id, 'TASK', record.task_id, expected,
                    record.revision, Jsonb(previous.aggregate.as_record()) if previous else None,
                    Jsonb(value), request_id))
                estimates = [value['effort']['user_remaining']] + [s['user_remaining'] for s in value['effort']['stages']]
                for u in estimates:
                    if u is not None and conn.execute('SELECT 1 FROM whattodo.effort_observation WHERE observation_id=%s',
                            (u['observation_id'],)).fetchone() is None:
                        conn.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                            (u['observation_id'], record.task_id, 'USER_REMAINING', u['seconds'],
                            sql_value('observed_at', u['observed_at']), NOW, 'record', 'authority', None, request_id))
                deadline = value['timing']['deadline']
                if deadline is not None:
                    due = deadline['value']
                    conn.execute('INSERT INTO whattodo.normalized_due VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                        (deadline['due_ref'], due['input_kind'], due['original_value'], due['source_ref'],
                        sql_value('due_at', due['instant']), due['original_value'] if due['input_kind']=='DATE_ONLY' else None,
                        due['default_policy_ref'], 'Asia/Shanghai' if due['input_kind']=='DATE_ONLY' else None))
                if fail == 'missing_audit':
                    change_ref = 'nonexistent-change'
                else:
                    change_ref = 'change-'+request_id
                try:
                    repo._append_in_transaction(record, bindings, request=request,
                        caller=caller, permit_ref=permit.permit_ref, audit_change_ref=change_ref)
                except TaskStorageError:
                    if catch_append_error:
                        require(conn.execute('SELECT 1 FROM whattodo.task_identity WHERE task_id=%s',
                            (record.task_id,)).fetchone() is None, 'TASK_STORAGE_SAVEPOINT_LEFT_IDENTITY')
                        require(conn.execute('SELECT 1 FROM whattodo.task_revision WHERE task_id=%s',
                            (record.task_id,)).fetchone() is None, 'TASK_STORAGE_SAVEPOINT_LEFT_CORE')
                        require(conn.execute('SELECT 1 FROM whattodo.command_transaction WHERE request_id=%s',
                            (request_id,)).fetchone() is not None, 'TASK_STORAGE_ROLLED_BACK_OUTER_TRANSACTION')
                        checks.append('append_savepoint_removes_partial_task_even_when_coordinator_catches_error')
                    raise
                if fail == 'after_staging':
                    raise TaskStorageError('SYNTHETIC_AFTER_STAGING_FAILURE')
                changed = conn.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE singleton=TRUE AND revision=%s',
                    (epoch+1, request_id, epoch)).rowcount
                require(changed == 1, 'TASK_STORAGE_FIXTURE_CAS')
            return record

        stages = example('aggregate-stages-retain-historical-completed-stage-u', 'staged-task')
        original = publish(stages, 'create-stages')
        require(reader.get(original.task_id) == original and reader.get(original.task_id, 1) == original,
            'TASK_STORAGE_STAGE_ROUNDTRIP')
        checks.append('stage_aggregate_roundtrips_original_bytes_titles_order_and_old_completed_estimates')
        require(reader.get('staged-task').aggregate.stage_partition(at=NOW).parent_seconds == 2400,
            'TASK_STORAGE_STAGE_DOUBLE_COUNT')
        checks.append('stages_remain_one_parent_budget')
        cancelled = deepcopy(stages)
        cancelled['core']['revision'] = cancelled['effort']['task_revision'] = 2
        cancelled['core']['disposition'] = cancelled['effort']['disposition'] = 'CANCELLED'
        cancelled['core']['metadata']['trust'] = 'CONFLICTED'
        updated = publish(cancelled, 'cancel-stages', 1)
        require(reader.get('staged-task') == updated and reader.get('staged-task', 1) == original,
            'TASK_STORAGE_HISTORY_REWRITTEN')
        require(reader.list_current(disposition='CANCELLED', trust='CONFLICTED') == (updated,),
            'TASK_STORAGE_DIMENSIONS_MERGED')
        checks.extend(['new_task_revision_preserves_old_wire_and_stage_history',
            'completion_disposition_and_trust_query_independently'])
        require(conn.execute("SELECT count(*) FROM whattodo.stage_revision WHERE task_id='staged-task'").fetchone() == (2,),
            'TASK_STORAGE_DUPLICATED_UNCHANGED_STAGE')
        checks.append('unchanged_stages_reuse_owned_immutable_revision')

        explicit = publish(example('aggregate-explicit-facts-and-original-total-below-current-u', 'explicit-task'), 'create-explicit')
        require(reader.get('explicit-task') == explicit and explicit.aggregate.budget(at=NOW).seconds == 2400,
            'TASK_STORAGE_EXPLICIT_FACTS_ROUNDTRIP')
        require(explicit.aggregate.as_record()['work']['total_estimate']['seconds'] == 1800,
            'TASK_STORAGE_TOTAL_BECAME_U')
        checks.append('release_original_offset_date_only_due_total_and_provenance_roundtrip_without_changing_u')
        unknown = example('aggregate-unknown-facts', 'unknown-effort-task')
        unknown['effort']['user_remaining'] = None
        unknown = publish(unknown, 'create-unknown')
        require(reader.get('unknown-effort-task') == unknown and unknown.aggregate.budget(at=NOW).seconds is None,
            'TASK_STORAGE_UNKNOWN_BECAME_ZERO')
        checks.append('unknown_remaining_effort_remains_unknown')
        complete = publish(example('aggregate-complete-with-unknown-historical-completion-time', 'complete-task'), 'create-complete')
        require(reader.list_current(completion='COMPLETE') == (complete,) and
            complete.aggregate.as_record()['timing']['completed_at'] is None,
            'TASK_STORAGE_COMPLETION_TIME_INVENTED')
        checks.append('complete_zero_remaining_and_unknown_completion_time_remain_distinct')

        wrong_owner = example('aggregate-stages-retain-historical-completed-stage-u', 'other-parent')
        wrong_owner['effort']['user_remaining'] = None
        for stage in wrong_owner['effort']['stages']:
            stage['user_remaining'] = None
        unresolved_profile = example('aggregate-unknown-facts', 'missing-profile-task')
        unresolved_profile['core']['context'] = dict(kind='COURSE', id='unregistered-course')
        unresolved_type = example('aggregate-unknown-facts', 'missing-type-task')
        unresolved_type['core']['task_type_ref'] = dict(id='unregistered-type', version='1')
        unresolved_goal = example('aggregate-unknown-facts', 'missing-goal-task')
        unresolved_goal['core']['context'] = dict(kind='GOAL', id='unregistered-goal')
        unresolved_exam = example('aggregate-unknown-facts', 'missing-exam-task')
        unresolved_exam['core']['context'] = dict(kind='EXAM', id='unregistered-exam')

        for request_id, value, expected, options, code in [
            ('untrusted', example('aggregate-unknown-facts', 'unauthorized-task'), None,
                dict(caller=CallerIdentity('principal', 'EXTERNAL', True)), 'TASK_STORAGE_UNTRUSTED_CALLER'),
            ('no-permit', example('aggregate-unknown-facts', 'no-permit-task'), None,
                dict(include_permit=False), 'TASK_STORAGE_EXACT_ACTIVE_PERMIT_REQUIRED'),
            ('no-audit', example('aggregate-unknown-facts', 'no-audit-task'), None,
                dict(fail='missing_audit'), 'TASK_STORAGE_PREPARED_AUDIT_REQUIRED'),
            ('rollback', example('aggregate-unknown-facts', 'rollback-task'), None,
                dict(fail='after_staging'), 'SYNTHETIC_AFTER_STAGING_FAILURE'),
            ('wrong-owner', wrong_owner, None,
                dict(catch_append_error=True), 'TASK_STORAGE_STAGE_OWNER_CONFLICT'),
            ('missing-profile', unresolved_profile, None,
                dict(bindings=TaskStorageBindings(DefinitionKey('COURSE_PROFILE','unregistered-course','1'))),
                'TASK_STORAGE_UNRESOLVED_PROFILE'),
            ('missing-type', unresolved_type, None, {}, 'TASK_STORAGE_UNRESOLVED_TASK_TYPE'),
            ('missing-goal', unresolved_goal, None, {}, 'TASK_STORAGE_UNRESOLVED_CONTEXT'),
            ('missing-exam', unresolved_exam, None, {}, 'TASK_STORAGE_UNRESOLVED_CONTEXT'),
        ]:
            epoch = conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()
            try:
                publish(value, request_id, expected, **options)
            except TaskStorageError as exc:
                require(str(exc) == code, 'TASK_STORAGE_UNEXPECTED_FAILURE_'+request_id)
            else:
                raise HarnessError('TASK_STORAGE_NEGATIVE_ACCEPTED_'+request_id)
            require(conn.execute('SELECT 1 FROM whattodo.command_transaction WHERE request_id=%s', (request_id,)).fetchone() is None,
                'TASK_STORAGE_PARTIAL_RECEIPT')
            require(reader.get(value['core']['task_id']) is None, 'TASK_STORAGE_PARTIAL_TASK')
            require(conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone() == epoch,
                'TASK_STORAGE_PARTIAL_EPOCH')
            checks.append(request_id+'_rejects_and_rolls_back_entire_fixture_transaction')

        try:
            with conn.transaction():
                conn.execute("INSERT INTO whattodo.task_stage_revision VALUES('explicit-task',1,'stage-1',1,0)")
        except psycopg.errors.ForeignKeyViolation:
            checks.append('native_membership_fk_rejects_stage_of_an_unrelated_task')
        else:
            raise HarnessError('TASK_STORAGE_NATIVE_OWNER_FK_ACCEPTED')
        try:
            with conn.transaction():
                conn.execute("INSERT INTO whattodo.stage_revision VALUES('stage-1',99,'explicit-task',1,'Wrong owner','INCOMPLETE',NULL,'authority','create-explicit',NULL,NULL)")
        except psycopg.errors.ForeignKeyViolation:
            checks.append('native_stage_revision_fk_prevents_changing_permanent_parent')
        else:
            raise HarnessError('TASK_STORAGE_NATIVE_STAGE_OWNER_CHANGED')
        try:
            with conn.transaction():
                conn.execute("INSERT INTO whattodo.stage_effort_revision VALUES('stage-1',1,'staged-task',20,'estimate-staged-task',NULL,%s,%s)", (NOW,NOW))
        except psycopg.errors.CheckViolation:
            checks.append('native_stage_estimate_check_rejects_partial_null_binding')
        else:
            raise HarnessError('TASK_STORAGE_NATIVE_PARTIAL_ESTIMATE_ACCEPTED')

        # Native constraints also defend against trusted code using incorrect SQL.
        for table in ['task_payload_revision', 'task_stage_revision', 'stage_effort_revision', 'stage_identity']:
            try:
                with conn.transaction():
                    conn.execute('DELETE FROM whattodo.'+table)
            except psycopg.errors.CheckViolation:
                checks.append(table+'_rejects_history_mutation')
            else:
                raise HarnessError('TASK_STORAGE_HISTORY_MUTATED')
        tables = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        fks = conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
        require((tables, fks) == (87, 221), 'TASK_STORAGE_SCHEMA_COUNTS')
        report.update(domain_tables=tables, domain_foreign_keys=fks)
        checks.append('native_schema_has_87_domain_tables_and_221_foreign_keys')
    with harness.target(name).connect() as restarted:
        repository = PostgresTaskRepository(restarted, codec, plan, application_version=__version__, clock=clock)
        require(repository.get('staged-task') == updated and repository.get('staged-task', 1) == original,
            'TASK_STORAGE_RESTART_HISTORY_LOST')
        checks.append('fresh_connection_reads_persisted_current_and_historical_aggregates')


def main():
    harness = PostgresHarness()
    report = dict(task='M3A-07', status='IN_PROGRESS', scope='SYNTHETIC_TASK_REPOSITORY',
        verified_on='2026-10-10', native_checks=[])
    try:
        with harness:
            verify(harness, report)
        report.update(status='PASS', native_check_count=len(report['native_checks']),
            limitations=['Synthetic fixture coordinator only; no live Task creation handler',
                'Atomic command publication/authority resolution/deduplication remain separate tasks',
                'No real course, Task, source, Calendar or service activation'])
    except Exception as exc:
        report.update(status='FAIL', failure_type=type(exc).__name__,
            failure_sqlstate=getattr(exc,'sqlstate',None),
            failure_code=str(exc) if isinstance(exc, (TaskStorageError, HarnessError)) else 'TASK_STORAGE_NATIVE_CHECK_FAILED')
    report['harness'] = harness.safe_summary()
    target = harness.run_root/'task-report.json'
    if harness.run_root.exists():
        target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], report=str(target),
        checks=len(report['native_checks']), server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
