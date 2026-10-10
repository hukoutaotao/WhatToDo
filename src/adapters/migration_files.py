"""Load trusted checked-in migration resources without evaluating configuration."""
from hashlib import sha256
import re
from pathlib import Path
import sysconfig

from src.adapters.contract_json import strict_json
from src.application.migrations import MigrationError,MigrationPlan,MigrationStep,need


def sql_statements(text):
    """Split top-level SQL while retaining quoted function bodies and comments.

    This is a lexical transaction-boundary guard, not SQL authorization or a
    general PostgreSQL parser. Only trusted manifest-pinned SQL may be loaded.
    """
    out=[];current=[];i=0;quote=None;dollar=None;block=0
    while i<len(text):
        char=text[i]
        if dollar is not None:
            if text.startswith(dollar,i):current.append(dollar);i+=len(dollar);dollar=None
            else:current.append(char);i+=1
        elif block:
            if text.startswith('/*',i):block+=1;i+=2
            elif text.startswith('*/',i):block-=1;i+=2
            else:i+=1
        elif quote is not None:
            current.append(char);i+=1
            if char==quote:
                if i<len(text) and text[i]==quote:current.append(text[i]);i+=1
                else:quote=None
            elif char=='\\' and quote=="'":
                # Keep this lexical subset independent of the server's
                # standard_conforming_strings setting; use doubled quotes.
                raise MigrationError('MIGRATION_UNSUPPORTED_STRING_ESCAPE')
        elif text.startswith('--',i):
            end=text.find('\n',i);i=len(text) if end<0 else end+1;current.append(' ')
        elif text.startswith('/*',i):block=1;i+=2;current.append(' ')
        elif char in ("'",'"'):quote=char;current.append(char);i+=1
        elif char=='$' and (match:=re.match(r'\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$',text[i:])):
            dollar=match.group();current.append(dollar);i+=len(dollar)
        elif char==';':
            if statement:=( ''.join(current).strip()):out.append(statement)
            current=[];i+=1
        else:current.append(char);i+=1
    need(quote is None and dollar is None and block==0,'MIGRATION_SQL_ENCODING')
    need(not ''.join(current).strip(),'MIGRATION_SQL_TERMINATOR')
    return tuple(out)


def migration_body(source):
    statements=sql_statements(source)
    need(len(statements)>=3 and statements[0].upper()=='BEGIN' and statements[-1].upper()=='COMMIT','MIGRATION_TRANSACTION_ENVELOPE')
    prohibited={'BEGIN','START','COMMIT','END','ROLLBACK','ABORT','SAVEPOINT','RELEASE','PREPARE'}
    need(all(s.split()[0].upper() not in prohibited for s in statements[1:-1]),'MIGRATION_TRANSACTION_CONTROL')
    return ';\n'.join(statements[1:-1])+';\n'


def load_migration_plan(*,root=None,manifest_path=None):
    root=Path(root).resolve() if root is not None else Path(sysconfig.get_path('data'))/'share/whattodo'
    path=Path(manifest_path) if manifest_path is not None else root/'database/migration-plan.json'
    try:
        need(path.resolve().is_relative_to(root),'MIGRATION_RESOURCE_SCOPE')
        manifest=strict_json(path.read_bytes())
        need(isinstance(manifest,dict) and set(manifest)=={'version','application_versions','steps'},'MIGRATION_MANIFEST_FIELDS')
        need(isinstance(manifest['application_versions'],list) and isinstance(manifest['steps'],list),'MIGRATION_MANIFEST_FIELDS')
        steps=[]
        for ref in manifest['steps']:
            need(isinstance(ref,dict) and set(ref)=={'id','path','content_hash','schema_version','legacy_design_version'},'MIGRATION_REFERENCE_FIELDS')
            need(isinstance(ref['path'],str),'MIGRATION_RESOURCE_SCOPE')
            source_path=(root/ref['path']).resolve()
            need(source_path.is_relative_to(root),'MIGRATION_RESOURCE_SCOPE')
            with source_path.open('r',encoding='utf-8',newline=None) as stream:source=stream.read(2097153)
            need(len(source.encode('utf-8'))<=2097152,'MIGRATION_RESOURCE_SIZE')
            need(sha256(source.encode('utf-8')).hexdigest()==ref['content_hash'],'MIGRATION_HASH')
            need(ref['legacy_design_version'] is None or isinstance(ref['legacy_design_version'],str) and bool(ref['legacy_design_version'].strip()),'MIGRATION_DESIGN_VERSION')
            steps.append(MigrationStep(ref['id'],ref['content_hash'],ref['schema_version'],source,migration_body(source),ref['legacy_design_version']))
        return MigrationPlan(manifest['version'],tuple(manifest['application_versions']),tuple(steps))
    except MigrationError:raise
    except (OSError,ValueError,TypeError,UnicodeError,RecursionError):raise MigrationError('MIGRATION_RESOURCES_UNREADABLE') from None
