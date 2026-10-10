"""Pinned migration values and compatibility rules, independent of PostgreSQL."""
from dataclasses import dataclass,field
from hashlib import sha256
import re

ID=re.compile(r'[0-9]{3}_[a-z0-9_]+\Z')
HASH=re.compile(r'[a-f0-9]{64}\Z')


class MigrationError(RuntimeError):
    def __init__(self,code,*,failed_migration=None,sqlstate=None,applied=()):
        super().__init__(code)
        self.code=code;self.failed_migration=failed_migration;self.sqlstate=sqlstate;self.applied=tuple(applied)


def need(condition,code):
    if not condition:raise MigrationError(code)


@dataclass(frozen=True)
class MigrationStep:
    migration_id:str
    content_hash:str
    schema_version:str
    source_sql:str=field(repr=False)
    body_sql:str=field(repr=False)
    legacy_design_version:str|None=None


@dataclass(frozen=True)
class MigrationPlan:
    manifest_version:str
    application_versions:tuple[str,...]
    steps:tuple[MigrationStep,...]

    def __post_init__(self):
        need(self.manifest_version=='0.1.0-migrations','MIGRATION_MANIFEST_VERSION')
        need(isinstance(self.application_versions,tuple) and bool(self.application_versions) and all(isinstance(v,str) and v.strip() for v in self.application_versions),'MIGRATION_APPLICATION_VERSIONS')
        need(isinstance(self.steps,tuple) and bool(self.steps),'MIGRATION_STEPS')
        for step in self.steps:
            need(isinstance(step,MigrationStep),'MIGRATION_STEP_VALUE')
            need(isinstance(step.migration_id,str) and ID.fullmatch(step.migration_id) is not None,'MIGRATION_ID')
            need(isinstance(step.content_hash,str) and HASH.fullmatch(step.content_hash) is not None,'MIGRATION_HASH')
            need(isinstance(step.schema_version,str) and bool(step.schema_version.strip()),'MIGRATION_SCHEMA_VERSION')
            need(isinstance(step.source_sql,str) and isinstance(step.body_sql,str),'MIGRATION_SQL_VALUE')
            try:digest=sha256(step.source_sql.encode('utf-8')).hexdigest()
            except UnicodeError:raise MigrationError('MIGRATION_SQL_VALUE') from None
            need(digest==step.content_hash,'MIGRATION_HASH')
            need(step.legacy_design_version is None or isinstance(step.legacy_design_version,str) and bool(step.legacy_design_version.strip()),'MIGRATION_DESIGN_VERSION')
        ids=tuple(s.migration_id for s in self.steps)
        need(ids==tuple(sorted(set(ids))) and ids[0]=='000_runtime_metadata','MIGRATION_ORDER')

    @property
    def schema_version(self):return self.steps[-1].schema_version


@dataclass(frozen=True)
class MigrationRecord:
    position:int
    migration_id:str
    content_hash:str
    schema_version:str


@dataclass(frozen=True)
class SchemaState:
    generation:int
    schema_version:str
    recovery_required:bool
    failed_migration_id:str|None


@dataclass(frozen=True)
class MigrationResult:
    applied:tuple[str,...]
    skipped:tuple[str,...]
    schema_version:str


@dataclass(frozen=True)
class SchemaCompatibility:
    schema_version:str
    generation:int
    application_version:str
    authority:str='SCHEMA_COMPATIBILITY_ONLY'


def check_history(plan,records,state,*,application_version,complete=False):
    need(application_version in plan.application_versions,'MIGRATION_APPLICATION_INCOMPATIBLE')
    need(len(records)<=len(plan.steps),'MIGRATION_UNKNOWN_APPLIED_VERSION')
    for index,record in enumerate(records):
        step=plan.steps[index]
        need(isinstance(record,MigrationRecord) and type(record.position) is int,'MIGRATION_APPLIED_DRIFT')
        need(record==MigrationRecord(index+1,step.migration_id,step.content_hash,step.schema_version),'MIGRATION_APPLIED_DRIFT')
    expected_version=plan.steps[len(records)-1].schema_version if records else 'UNINITIALIZED'
    need(type(state.generation) is int and state.generation==len(records) and state.schema_version==expected_version,'MIGRATION_STATE_DRIFT')
    need(type(state.recovery_required) is bool and state.recovery_required==(state.failed_migration_id is not None),'MIGRATION_RECOVERY_STATE')
    if state.recovery_required:
        need(len(records)<len(plan.steps) and state.failed_migration_id==plan.steps[len(records)].migration_id,'MIGRATION_RECOVERY_STATE')
    if complete:
        need(not state.recovery_required,'MIGRATION_RECOVERY_REQUIRED')
        need(len(records)==len(plan.steps),'MIGRATION_SCHEMA_INCOMPATIBLE')
    return len(records)
