"""Owned native stage-journal publication probes, not public handler acceptance."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
from threading import Barrier

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src import __version__
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.migration_files import load_migration_plan, migration_body
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import apply_migrations, schema_checked_transaction, DatabaseRoles
from src.adapters.postgres_stage_commit import PostgresStageCommitWriter
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.command_ledger import validate_audit_fingerprint
from src.application.definitions import canonical
from src.application.migrations import MigrationStep
from src.application.ports import RequestContext, TransactionPermit
from src.application.stage_commands import StageCommand, StageCommandGrant
from src.application.stage_commit import StageCommandJournal, prepare_stage_commit
from src.application.task_storage import TaskStorageBindings
from src.application.transactions import TransactionError
from src.domain.provenance import capture_source
from tools.postgres_harness import PostgresHarness, HarnessError, ROLES, require
from tools import verify_lifecycle as fixtures

NOW = fixtures.NOW; CLOCK = fixtures.CLOCK; CALLER = fixtures.CALLER; SCOPE = fixtures.SCOPE


def candidate_plan():
    """Require the activated exact stage step; never append an unpinned candidate."""
    base = load_migration_plan(root=ROOT)
    source = (ROOT/'database/runtime-migrations/017_stage_commands.sql').read_text(encoding='utf-8')
    step = MigrationStep('017_stage_commands', sha256(source.encode()).hexdigest(),
        '0.13.0-stage-commands', source, migration_body(source))
    require(len(base.steps)>=18 and base.steps[17]==step,'STAGE_RUNTIME_MIGRATION_PIN_DRIFT')
    return base


def verify(h, report):
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    setup = dict(native_checks=[]); initial = len(h._created); plan=candidate_plan()
    fixtures.verify(h, setup, migration_plan=replace(plan,steps=plan.steps[:17]))
    require(len(h._created) == initial+1, 'STAGE_FIXTURE_DATABASE_COUNT')
    database = h._created[-1]
    roles = DatabaseRoles(ROLES['migration'], ROLES['application'], ROLES['test'])
    codec = ContractJSONCodec(load_supported_schemas(root=ROOT)); checks = report['native_checks']
    report['fixture_native_check_count'] = len(setup['native_checks'])
    with h.target(database, 'migration').connect() as owner:
        prefix = owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        old_payloads = owner.execute('SELECT task_id,task_revision,raw_bytes FROM whattodo.task_payload_revision ORDER BY 1,2').fetchall()
        applied = apply_migrations(owner, plan, roles=roles, application_version=__version__)
        require(applied.applied == ('017_stage_commands','018_review_queue'), 'STAGE_CANDIDATE_APPLY')
        require(owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=17 ORDER BY position').fetchall() == prefix
            and owner.execute('SELECT task_id,task_revision,raw_bytes FROM whattodo.task_payload_revision ORDER BY 1,2').fetchall() == old_payloads,
            'STAGE_UPGRADE_REWROTE_HISTORY')
    checks.append('pinned_eighteenth_step_preserves_all_prior_migration_and_task_payload_history')
    with h.target(database).connect() as conn:
        reader = PostgresTaskRepository(conn, codec, plan, application_version=__version__, clock=CLOCK)
        def epoch(): return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        tables = ('task_revision','stage_revision','task_payload_revision','task_stage_revision','stage_effort_revision',
            'effort_observation','stage_command_journal','stage_relationship_issue','stage_pending_resolution',
            'command_transaction','authority_record','audit_entry','audit_change','store_epoch')
        def state(): return tuple(conn.execute(sql.SQL('SELECT * FROM whattodo.{} ORDER BY 1,2').format(sql.Identifier(t))).fetchall() for t in tables)
        def evidence(name, raw):
            source = capture_source(provider=SCOPE.provider, scope_ref=SCOPE.scope_ref, external_id=name,
                raw_bytes=raw, captured_at=NOW-timedelta(minutes=1), source_type='USER')
            PostgresEvidenceRepository(conn, codec, plan, application_version=__version__, clock=CLOCK, scopes=(SCOPE,)).observe_source(
                canonical(source.as_record()).encode(), raw_content=raw, locator_ref='synthetic-'+name)
            return source
        def setup_command(name, *, fields, operation='REWORK'):
            before = reader.get('staged'); v = before.aggregate.as_record()
            revision = next(d['revision'] for d in v['stage_details'] if d['stage_id']=='staged-stage-0')
            command = StageCommand(name, CALLER.principal_id, 'stage-root-'+name, before.task_id, before.revision,
                'staged-stage-0', revision, operation, canonical(fields))
            raw = json.dumps(command.as_record(), indent=2).encode(); source = evidence(name, raw)
            grant = StageCommandGrant(command, source.record_id, NOW-timedelta(minutes=2), source.captured_at, NOW+timedelta(hours=1))
            with h.target(database, 'migration').connect() as owner:
                owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (command.authority_ref, command.principal_id, 'USER_COMMAND', source.record_id, command.fingerprint,
                        Jsonb(grant.as_record()), grant.issued_at, grant.expires_at))
            prepared = prepare_stage_commit(codec, raw, grant, before, caller=CALLER, now=NOW,
                context=RequestContext(name,'native-stage'), expected_store_revision=epoch(), audit_id='audit-'+name)
            permit = TransactionPermit('stage-permit-'+name, CALLER.principal_id, CALLER.origin,
                prepared.request.fingerprint, NOW, NOW+timedelta(minutes=1))
            return prepared, permit, before
        def publish(prepared, permit, *, connection=conn):
            with schema_checked_transaction(connection, plan, application_version=__version__, read_only=False):
                return PostgresStageCommitWriter(connection, codec, plan, application_version=__version__, clock=CLOCK).append_in_transaction(
                    prepared, caller=CALLER, permit=permit, bindings=TaskStorageBindings())
        def reject_write(prepared, permit, expected, *, mutation=None):
            baseline = state()
            try:
                with schema_checked_transaction(conn, plan, application_version=__version__, read_only=False):
                    PostgresStageCommitWriter(conn, codec, plan, application_version=__version__, clock=CLOCK).append_in_transaction(
                        prepared, caller=CALLER, permit=permit, bindings=TaskStorageBindings())
                    if mutation: mutation()
            except Exception as exc:
                code = getattr(exc, 'sqlstate', None) or str(exc)
                require(code == expected, 'STAGE_UNEXPECTED_REJECTION')
            else: require(False, 'STAGE_EXPECTED_REJECTION')
            require(state() == baseline, 'STAGE_REJECTION_MUTATED_HISTORY')

        class ConnectionProxy:
            def __init__(self, actual): self.actual = actual
            def __getattr__(self, key): return getattr(self.actual, key)
            def text(self, statement): return statement.as_string(self.actual) if hasattr(statement, 'as_string') else statement
        class DisconnectAfterJournal(ConnectionProxy):
            reached = False
            def execute(self, statement, *args, **kwargs):
                text = self.text(statement)
                result = self.actual.execute(statement, *args, **kwargs)
                if text.startswith('INSERT INTO whattodo.stage_command_journal'):
                    self.reached = True
                    self.actual.close()
                return result
        class TamperJournal(ConnectionProxy):
            def __init__(self, actual, columns): super().__init__(actual); self.columns = columns
            def execute(self, statement, *args, **kwargs):
                if self.text(statement).startswith('INSERT INTO whattodo.stage_command_journal'):
                    values = list(args[0]); values[self.columns.index('raw_command_hash')] = '0'*64
                    return self.actual.execute(statement, tuple(values), **kwargs)
                return self.actual.execute(statement, *args, **kwargs)

        original = reader.get('staged'); old_history = reader.get('staged', original.revision)
        actuals = conn.execute("SELECT * FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK' ORDER BY observation_id").fetchall()
        for name, intent in (('ambiguous','UNRESOLVED'), ('correction','CORRECTION'), ('new-obligation','NEW_OBLIGATION')):
            prepared, permit, _ = setup_command(name, fields=dict(intent=intent))
            before_epoch = epoch(); receipt = publish(prepared, permit)
            require(prepared.journal.state == 'PENDING' and receipt.store_revision == before_epoch+1
                and reader.get('staged') == original and not prepared.observations, 'STAGE_PENDING_EFFECTS')
            stored = conn.execute('SELECT runtime_payload,raw_command FROM whattodo.stage_command_journal WHERE command_id=%s',(name,)).fetchone()
            require(StageCommandJournal.from_payload(stored[0]) == prepared.journal and bytes(stored[1]) == prepared.journal.raw_command,
                'STAGE_PENDING_RAW_ROUNDTRIP')
        checks.append('ambiguous_correction_and_new_obligation_pending_persist_losslessly_without_task_or_estimate_changes')
        prepared, permit, _ = setup_command('needs-estimate', fields=dict(intent='SAME_OBLIGATION'))
        publish(prepared, permit)
        require(prepared.journal.code == 'STAGE_REWORK_REMAINING_REQUIRED' and reader.get('staged') == original, 'STAGE_REQUIRED_ESTIMATE')
        checks.append('completed_parent_rework_without_fresh_positive_u_persists_pending_without_reopening')

        prepared, permit, _ = setup_command('reopen', fields=dict(intent='SAME_OBLIGATION',parent_remaining_seconds=900))
        baseline = state()
        corrupt = replace(prepared, observations=())
        reject_write(corrupt, permit, 'STAGE_EXACT_COMMIT_PLAN_REQUIRED')
        checks.append('forged_typed_plan_cannot_drop_required_observations_and_leaves_no_transaction_effects')
        publish(prepared, permit)
        after = reader.get('staged'); value = after.aggregate.as_record()
        require(after == prepared.task and value['core']['completion']=='INCOMPLETE' and value['timing']['completed_at'] is None
            and value['effort']['user_remaining']['seconds']==900 and value['effort']['stages'][0]['completion']=='INCOMPLETE'
            and value['effort']['stages'][0]['user_remaining'] is None and value['effort']['stages'][1]['completion']=='COMPLETE'
            and reader.get('staged', old_history.revision)==old_history, 'STAGE_TRUTHFUL_REWORK')
        require(conn.execute("SELECT * FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK' ORDER BY observation_id").fetchall()==actuals,
            'STAGE_REWORK_CHANGED_ACTUAL_WORK')
        checks.append('exact_audited_rework_atomically_reopens_existing_stage_parent_and_retains_completion_actual_work_and_other_stage_history')
        require(conn.execute('SELECT authority_ref,observed_at,recorded_at FROM whattodo.effort_observation WHERE transaction_ref=%s',
            ('reopen',)).fetchone()==(prepared.journal.command.authority_ref, prepared.journal.source_observed_at, NOW)
            and value['effort']['user_remaining']['verified_at']==prepared.journal.source_observed_at.isoformat(),
            'STAGE_U_PROVENANCE')
        checks.append('fresh_parent_remaining_uses_original_user_grant_and_actual_source_capture_time')
        row = conn.execute('SELECT after_value FROM whattodo.audit_change WHERE request_id=%s ORDER BY aggregate_kind',('reopen',)).fetchall()
        require(len(row)==2 and all(a.tuple[-1] in [r[0] for r in row] for a in prepared.audits), 'STAGE_FULL_AUDITS')
        validate_audit_fingerprint(prepared.receipt, principal_id=CALLER.principal_id, expected_store_revision=prepared.request.expected_store_revision,
            source_ref=prepared.request.source_ref, correlation_ref='native-stage', changes=tuple(a.tuple for a in prepared.audits))
        checks.append('task_and_transition_are_bound_to_one_full_audit_receipt_and_epoch_advance')

        finished, permit, _ = setup_command('complete-stage', operation='COMPLETE', fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))
        baseline = state()
        try:
            publish(finished, permit, connection=TamperJournal(conn,
                tuple(finished.journal.sql_row(finished.request.context.request_id, 'unused'))))
        except psycopg.errors.CheckViolation: pass
        else: require(False, 'STAGE_SQL_RAW_HASH_NOT_CHECKED')
        require(state()==baseline, 'STAGE_RAW_HASH_REJECTION_MUTATED')
        checks.append('actual_sql_raw_hash_constraint_rejects_bypassed_writer_tampering_and_rolls_back_all_effects')
        with h.target(database).connect() as victim:
            proxy = DisconnectAfterJournal(victim)
            try: publish(finished, permit, connection=proxy)
            except (psycopg.OperationalError, psycopg.InterfaceError): pass
            else: require(False, 'STAGE_DISCONNECT_DID_NOT_FAIL')
            require(proxy.reached and victim.closed, 'STAGE_DISCONNECT_NOT_REACHED')
        require(state()==baseline, 'STAGE_REAL_DISCONNECT_MUTATED')
        checks.append('real_connection_close_after_task_and_journal_insertion_rolls_back_observations_audits_receipt_and_epoch')
        reject_write(finished, permit, '23514', mutation=lambda:conn.execute("UPDATE whattodo.stage_command_journal SET state=state"))
        require(reader.get('staged')==after, 'STAGE_COMPOSITE_ROLLBACK')
        checks.append('real_deferred_or_history_failure_rolls_back_staged_task_observations_journal_audits_receipt_and_epoch')
        publish(finished, permit)
        require(reader.get('staged').aggregate.as_record()['core']['completion']=='INCOMPLETE'
            and reader.get('staged').aggregate.as_record()['effort']['stages'][0]['completion']=='COMPLETE', 'STAGE_COMPLETION_PARENT_TRUTH')
        checks.append('explicit_stage_completion_preserves_incomplete_parent_and_reported_time_without_fabricated_work')

        competitors = [setup_command('concurrent-'+name, fields=dict(intent='SAME_OBLIGATION',parent_remaining_seconds=600))
            for name in ('one','two')]
        before_race_epoch = epoch(); before_race = reader.get('staged'); barrier = Barrier(2)
        targets = [h.target(database),h.target(database)]
        class RaceConnection(ConnectionProxy):
            def execute(self, statement, *args, **kwargs):
                if self.text(statement).startswith('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE NOWAIT'):
                    barrier.wait(timeout=20)
                return self.actual.execute(statement, *args, **kwargs)
        def compete(index):
            candidate, permit, _ = competitors[index]
            with targets[index].connect() as actual:
                try:
                    publish(candidate, permit, connection=RaceConnection(actual))
                    return 'COMMITTED',candidate.request.context.request_id
                except psycopg.Error as exc: return exc.sqlstate,None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = tuple(pool.map(compete, range(2)))
        winners = [name for code,name in outcomes if code=='COMMITTED']
        require(len(winners)==1 and all(code in ('COMMITTED','55P03','40001') for code,_ in outcomes)
            and epoch()==before_race_epoch+1 and reader.get('staged').revision==before_race.revision+1,
            'STAGE_SIMULTANEOUS_CAS')
        require(conn.execute("SELECT command_id FROM whattodo.stage_command_journal WHERE command_id LIKE 'concurrent-%'").fetchall()==[(winners[0],)],
            'STAGE_CAS_LOSER_PERSISTED')
        checks.append('actual_simultaneous_epoch_lock_and_parent_cas_publish_one_rework_and_no_loser_history')
        for table in ('stage_command_journal','stage_relationship_issue','stage_pending_resolution'):
            for verb in ('UPDATE whattodo.'+table+' SET revision=revision', 'DELETE FROM whattodo.'+table):
                try:
                    with conn.transaction(): conn.execute(verb)
                except psycopg.errors.CheckViolation: pass
                else: require(False, 'STAGE_HISTORY_NOT_IMMUTABLE')
        checks.append('application_role_cannot_update_or_delete_journal_issue_or_pending_resolution_history')
        tables_count = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        fk_count = conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
        require((tables_count,fk_count)==(87,221), 'STAGE_CANDIDATE_SCHEMA_COUNTS')
        report.update(candidate_schema_version=plan.schema_version, candidate_steps=len(plan.steps), domain_tables=tables_count,
            domain_foreign_keys=fk_count, activated_steps=len(load_migration_plan(root=ROOT).steps))
    with h.target(database).connect() as fresh:
        stored = fresh.execute('SELECT runtime_payload FROM whattodo.stage_command_journal WHERE command_id=%s',('reopen',)).fetchone()[0]
        require(StageCommandJournal.from_payload(stored)==prepared.journal, 'STAGE_FRESH_JOURNAL_READ')
    checks.append('fresh_connection_reconstructs_original_journal_after_later_parent_and_stage_changes')


def main():
    h = PostgresHarness(); report = dict(task='M3B-07.b', status='IN_PROGRESS',
        scope='SYNTHETIC_INTERNAL_COMPOSITE_STAGE_WRITER_AND_PINNED_SQL_UPGRADE', native_checks=[])
    try:
        with h: verify(h, report)
        report.update(status='PASS', native_check_count=len(report['native_checks']), limitations=[
            'No public stage-command handler or independently resolved current relationship/account scope',
            'Migration 017 is applied only to an owned disposable test database',
            'Complete handler and generated endpoint checks are separate verifiers',
            'The prerequisite lifecycle fixture checks are reported separately and not counted as new stage checks'])
    except Exception as exc:
        report.update(status='FAIL', failure_type=type(exc).__name__, failure_code=str(exc) if isinstance(exc,HarnessError) else 'STAGE_COMMIT_NATIVE_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None), failed_migration=getattr(exc,'failed_migration',None))
    report['harness'] = h.safe_summary(); path = h.run_root/'stage-commit-report.json'
    if h.run_root.exists(): path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
