"""Current PostgreSQL references plus independent grants, before command effects."""
import json

from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_validation import (CreationProvenance,PreparedUserEstimate,
    admit_command,grant_record,validate_effects)
from src.application.command_ledger import validate_caller
from src.application.definitions import DefinitionKey
from src.application.evidence_storage import SourceScope
from src.application.migrations import MigrationError
from src.application.ports import CommitRequest,PortResult
from src.application.task_storage import (TaskStorageError,TaskStorageRecord,
    TaskStorageBindings,admit_storage,validate_bindings)
from src.application.transactions import TransactionError,require
from src.domain.authorization import (AuthorityGrant,Command,CreationRecord,NoticeEvidence)


def register_grant(connection,grant,plan,*,application_version):
    """Trusted resolver/setup only: persist its immutable source-backed scope.

    Grant construction/registration is not a command transport operation. JSON
    command input never calls this helper or constructs AuthorityGrant values.
    """
    require(isinstance(grant,AuthorityGrant),'AUTHORITY_TYPED_GRANT_REQUIRED')
    from psycopg.types.json import Jsonb
    body=grant_record(grant);command=Command(grant.command_id,grant.principal_id,
        grant.origin,grant.grant_id,grant.changes,grant.rule_scope,grant.batch_ref,grant.batch_members)
    expected=(grant.principal_id,grant.origin,grant.evidence_ref,command.fingerprint,
        body,grant.issued_at,grant.expires_at)
    with schema_checked_transaction(connection,plan,application_version=application_version,read_only=False):
        row=connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (grant.grant_id,)).fetchone()
        if row is not None:require(row==expected,'AUTHORITY_GRANT_IMMUTABLE_CONFLICT');return
        connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (grant.grant_id,*expected[:4],Jsonb(body),*expected[5:]))


class PostgresCommandService:
    def __init__(self,connection,codec,plan,*,application_version,clock,grants=(),
                 seeds=(),bindings=(),source_scopes=(),conditions=(),
                 creation_provenance=(),prepared_estimates=()):
        require(isinstance(grants,tuple) and all(isinstance(g,AuthorityGrant) for g in grants)
            and len({g.grant_id for g in grants})==len(grants),'AUTHORITY_TRUSTED_GRANT_REGISTRY')
        require(isinstance(seeds,tuple) and all(isinstance(r,TaskStorageRecord) for r in seeds)
            and len({r.task_id for r in seeds})==len(seeds),'AUTHORITY_TRUSTED_SEED_REGISTRY')
        require(isinstance(source_scopes,tuple) and all(isinstance(s,SourceScope) for s in source_scopes)
            and len({(s.provider,s.scope_ref) for s in source_scopes})==len(source_scopes),
            'AUTHORITY_TRUSTED_SOURCE_SCOPE_REGISTRY')
        require(isinstance(conditions,tuple) and all(isinstance(n,NoticeEvidence) for n in conditions)
            and len({n.notice_id for n in conditions})==len(conditions),'AUTHORITY_TRUSTED_CONDITION_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan
        self.application_version=application_version;self.clock=clock
        self._grants={g.grant_id:g for g in grants};self._seeds=seeds
        self._bindings=bindings;self._scopes=source_scopes
        self._conditions={n.notice_id:n for n in conditions}
        require(isinstance(creation_provenance,tuple) and
            all(isinstance(p,CreationProvenance) for p in creation_provenance) and
            len({p.task_id for p in creation_provenance})==len(creation_provenance),
            'AUTHORITY_TRUSTED_CREATION_PROVENANCE')
        require(isinstance(prepared_estimates,tuple) and
            all(isinstance(o,PreparedUserEstimate) for o in prepared_estimates) and
            len({o.observation_id for o in prepared_estimates})==len(prepared_estimates),
            'AUTHORITY_TRUSTED_PREPARED_ESTIMATES')
        self._creation_provenance=creation_provenance;self._prepared_estimates=prepared_estimates
        self._reader=PostgresTaskRepository(connection,codec,plan,
            application_version=application_version,clock=clock)

    def commit(self,raw,request,*,caller):
        require(isinstance(request,CommitRequest),'TYPED_TRANSACTION_REQUIRED')
        correlation=request.context.correlation_ref
        database_error=();transport_error=()
        try:
            admitted=admit_command(self.codec,raw);command=admitted.command
            validate_caller(caller,principal_id=request.principal_id)
            require(1<=len(request.writes)<=100 and sum(len(w.body_json.encode('utf-8'))
                for w in request.writes)<=8388608,'TRANSACTION_SIZE_LIMIT')
            require((command.command_id,command.principal_id,command.origin)==
                (request.context.request_id,caller.principal_id,caller.origin) and
                caller.authenticated and caller.origin!='EXTERNAL','UNTRUSTED_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,
                application_version=self.application_version,clock=self.clock)
            prior=coordinator.lookup_commit(request.context,caller=caller)
            if prior.status=='SUCCESS':
                with schema_checked_transaction(self.connection,self.plan,
                        application_version=self.application_version):
                    row=self.connection.execute('''SELECT a.resolved_scope FROM whattodo.authority_record a
                        JOIN whattodo.command_transaction c ON c.authority_ref=a.authority_ref
                        WHERE c.request_id=%s''',(command.command_id,)).fetchone()
                    annotation=row[0].get('authorization') if row else None
                    require(annotation is not None and annotation.get('command_fingerprint')==command.fingerprint,
                        'COMMAND_AUTHORITY_REPLAY_CONFLICT')
                # The coordinator independently checks exact request content and ownership.
                return coordinator.commit(request,caller=caller,permit_ref='REPLAY_ONLY')
            if prior.status!='UNKNOWN':return prior
            grant=self._grants.get(command.authority_ref)
            require(grant is not None,'UNREGISTERED_AUTHORITY')
            with schema_checked_transaction(self.connection,self.plan,
                    application_version=self.application_version):
                require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
                    ==(request.expected_store_revision,),'STALE_STORE_REVISION')
                self._grant(grant)
                records=[]
                ids={c.task_id for c in command.changes}
                if command.rule_scope:ids.add(command.rule_scope.source_task_id)
                for item_id in sorted(ids):
                    record=self._reader._get_in_transaction(item_id)
                    if record is not None:records.append(record)
                observations=[];effective_bindings=[]
                for write in request.writes:
                    record=admit_storage(self.codec,write.body_json.encode('utf-8'))
                    value=record.aggregate.as_record()
                    if write.key.kind=='TASK':
                        estimates=[value['effort']['user_remaining']]+[s['user_remaining'] for s in value['effort']['stages']]
                        for u in estimates:
                            if u is not None:
                                row=self.connection.execute('''SELECT observation_id,task_id,kind,seconds,
                                    observed_at,source_record_ref,authority_ref FROM whattodo.effort_observation
                                    WHERE observation_id=%s''',(u['observation_id'],)).fetchone()
                                if row is not None:observations.append(row)
                for observation in self._prepared_estimates:
                    require(observation.task_id in {c.task_id for c in command.changes} and
                        (observation.source_ref,observation.authority_ref)==(grant.evidence_ref,grant.grant_id)
                        and observation.observed_at<=self.clock.now(),'COMMAND_UNRESOLVED_EFFORT_FACT')
                    existing=self.connection.execute('''SELECT observation_id,task_id,kind,seconds,
                        observed_at,source_record_ref,authority_ref FROM whattodo.effort_observation
                        WHERE observation_id=%s''',(observation.observation_id,)).fetchone()
                    require(existing is None or existing==observation.row,'COMMAND_UNRESOLVED_EFFORT_FACT')
                    observations.append(observation.row)
                creations=self._creations(command,request)
                notices=self._notices(command)
                authorized=validate_effects(self.codec,admitted,request,caller=caller,grant=grant,
                    records=tuple(records),seeds=self._seeds,observations=tuple(observations),
                    creations=creations,notices=notices,now=self.clock.now())
                context=authorized.context
                if self._creation_provenance:
                    seed_by_id={s.task_id:s for s in self._seeds}
                    for proof in self._creation_provenance:
                        require(any(c.task_id==proof.task_id and c.action=='CREATE_TASK' for c in command.changes)
                            and proof.task_id in seed_by_id and seed_by_id[proof.task_id].content_hash==proof.seed_hash,
                            'COMMAND_CREATION_PROVENANCE_MISMATCH')
                    context['creation_provenance']=[dict(task_id=p.task_id,seed_hash=p.seed_hash,details=p.details)
                        for p in sorted(self._creation_provenance,key=lambda p:p.task_id)]
                for write in request.writes:
                    record=admit_storage(self.codec,write.body_json.encode('utf-8'))
                    binding=self._binding(record,write.expected_revision)
                    validate_bindings(record,binding)
                    self._reader._check_references(record,binding,
                        resolved_estimates=tuple(o.row for o in self._prepared_estimates))
                    for stage in record.aggregate.as_record()['effort']['stages']:
                        owner=self.connection.execute('SELECT task_id FROM whattodo.stage_identity WHERE stage_id=%s',
                            (stage['stage_id'],)).fetchone()
                        require(owner is None or owner==(record.task_id,),'COMMAND_STAGE_OWNER_CONFLICT')
                    effective_bindings.append((record.task_id,binding))
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,
                application_version=self.application_version,clock=self.clock,
                permits=(authorized.permit,),bindings=tuple(effective_bindings),
                authorization_context=context,prepared_estimates=self._prepared_estimates)
            return coordinator.commit(request,caller=caller,permit_ref=authorized.permit.permit_ref)
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('STALE_STORE_REVISION','STALE_STATE_VERSION',
                'TARGET_ALREADY_EXISTS','COMMAND_AUTHORITY_REPLAY_CONFLICT') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except TaskStorageError as exc:return PortResult('PERMANENT',str(exc),correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation) if str(exc) in \
                ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            # Reference resolution is read-only: no fresh command can have
            # committed here. A lost connection/busy snapshot is retryable.
            if isinstance(exc,transport_error) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','COMMAND_REFERENCES_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','COMMAND_REFERENCE_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','COMMAND_VALIDATION_FAILED',correlation)

    def _binding(self,record,expected_revision):
        binding=dict(self._bindings).get(record.task_id,TaskStorageBindings())
        profile=binding.profile_key
        if expected_revision is not None:
            old=self.connection.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=%s',
                (record.task_id,expected_revision)).fetchone()
            require(old is not None,'COMMAND_PROFILE_HISTORY_UNAVAILABLE')
            if profile is not None:require(profile.configuration_ref==old[0],'COMMAND_UNAUTHORIZED_PROFILE_REFERENCE')
            if old[0] is not None:
                row=self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s',
                    (old[0],)).fetchone()
                require(row is not None,'COMMAND_PROFILE_HISTORY_UNAVAILABLE');profile=DefinitionKey(*row)
        expired=record.aggregate.as_record()['core']['disposition']=='EXPIRED'
        notice=expected_revision if expired else None
        require(binding.notice_task_revision is None or binding.notice_task_revision==notice,
            'COMMAND_UNAUTHORIZED_NOTICE_VERSION')
        return TaskStorageBindings(profile,notice)

    def _grant(self,grant):
        expected_command=Command(grant.command_id,grant.principal_id,grant.origin,grant.grant_id,
            grant.changes,grant.rule_scope,grant.batch_ref,grant.batch_members)
        row=self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (grant.grant_id,)).fetchone()
        require(row==(grant.principal_id,grant.origin,grant.evidence_ref,expected_command.fingerprint,
            grant_record(grant),grant.issued_at,grant.expires_at),'AUTHORITY_REGISTERED_SCOPE_MISMATCH')
        source=self.connection.execute('''SELECT s.source_type,s.provider,s.scope_ref,a.account_ref
            FROM whattodo.source_record r JOIN whattodo.source_identity s USING(source_id)
            JOIN whattodo.source_scope a USING(provider,scope_ref) WHERE r.record_id=%s''',
            (grant.evidence_ref,)).fetchone()
        require(source is not None and source[0]=='USER' and
            any((s.provider,s.scope_ref,s.account_ref)==source[1:] for s in self._scopes),
            'AUTHORITY_SOURCE_SCOPE_REQUIRED')

    def _creations(self,command,request):
        if command.rule_scope is None:return ()
        s=command.rule_scope
        rule=self.connection.execute('''SELECT active,acceptance_ref,trigger_kind,target_role,
            source_type_ref,target_type_ref,template_ref,template_version,configuration_ref,obligation_kind
            FROM whattodo.relationship_rule_revision WHERE rule_id=%s AND version=%s''',
            (s.rule_id,s.version)).fetchone()
        require(rule is not None and rule[0] and rule[1] is not None and
            rule[2:4] == ('CANONICAL_CREATION',s.target_role) and rule[9]=='SEPARATE_TASK',
            'AUTHORITY_ACCEPTED_RULE_REQUIRED')
        require(self.connection.execute('''SELECT configuration_ref FROM whattodo.definition_cache
            WHERE kind='RELATIONSHIP_RULE' AND id=%s AND version=%s''',(s.rule_id,s.version)).fetchone()
            ==(rule[8],),'AUTHORITY_ACCEPTED_RULE_REQUIRED')
        require(self.connection.execute('''SELECT version FROM whattodo.definition_cache
            WHERE kind='TASK_TEMPLATE' AND configuration_ref=%s''',(rule[6],)).fetchone()
            ==(rule[7],),'AUTHORITY_ACCEPTED_RULE_REQUIRED')
        source=self._reader._get_in_transaction(s.source_task_id)
        source_type=source.aggregate.as_record()['core']['task_type_ref'] if source else None
        require(source_type is not None and DefinitionKey('TASKTYPE',**source_type).configuration_ref
            ==rule[4],'AUTHORITY_RULE_TYPE_SCOPE_MISMATCH')
        for write in request.writes:
            target=admit_storage(self.codec,write.body_json.encode('utf-8')).aggregate.as_record()['core']['task_type_ref']
            require(target is not None and DefinitionKey('TASKTYPE',**target).configuration_ref
                ==rule[5],'AUTHORITY_RULE_TYPE_SCOPE_MISMATCH')
        row=self.connection.execute('SELECT transaction_ref FROM whattodo.task_identity WHERE task_id=%s',
            (s.source_task_id,)).fetchone()
        require(row==(s.creation_event_ref,),'CANONICAL_CREATION_REQUIRED')
        return (CreationRecord(s.creation_event_ref,s.source_task_id,s.occurrence_key,True),)

    def _notices(self,command):
        notices=[]
        for item in command.changes:
            if item.action!='EXPIRE_TASK':continue
            ref=item.fields.get('expiration_notice_ref');confirmation=self._conditions.get(ref)
            require(confirmation is not None,'AUTHORITY_CONFIRMED_CONDITION_REQUIRED')
            row=self.connection.execute('''SELECT task_id,task_revision,condition_ref,detected_at
                FROM whattodo.expiration_notice WHERE notice_id=%s''',(ref,)).fetchone()
            require(row==(confirmation.task_id,confirmation.task_revision,confirmation.condition_ref,
                confirmation.condition_observed_at),'AUTHORITY_NOTICE_REFERENCE_MISMATCH')
            delivered=self.connection.execute('''SELECT delivered_at FROM whattodo.dispatch_result
                WHERE notice_id=%s AND state='DELIVERED' ORDER BY delivered_at LIMIT 1''',(ref,)).fetchone()
            require(delivered is not None and confirmation.condition_confirmed and
                delivered[0]==confirmation.delivered_at,'CONFIRMED_NOTICE_REQUIRED')
            notices.append(confirmation)
        return tuple(notices)
