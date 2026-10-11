"""Owned synthetic development bundles; no production endpoint or role export."""
from dataclasses import dataclass
from datetime import date,datetime,timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import subprocess
from uuid import uuid4
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.runtime_config import ADAPTERS,ENV_NAME,KINDS
from src.application.configuration import RuntimeConfig,SecretRef
from src.application.definitions import canonical,strict_json
from tools.postgres_harness import PostgresHarness,ROLES,ConnectionTarget,owned_run
SCHEMAS=('whattodo','whattodo_meta');MAX_ARCHIVE=134217728;MAX_MANIFEST=2097152;MAX_CONFIG=262144
HASH=re.compile('[a-f0-9]{64}\\Z');BUNDLE=re.compile('backup_[a-f0-9]{32}\\Z')
class BackupError(RuntimeError):
    def __init__(self,code,*,diagnostic=None):super().__init__(code);self.diagnostic=diagnostic
def need(value,code):
    if not value:raise BackupError(code)
def digest_file(path,limit):
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=limit,'BACKUP_FILE_SIZE_OR_KIND')
    h=sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def atom(value):
    if isinstance(value,(bytes,bytearray,memoryview)):return {'bytea':bytes(value).hex()}
    if isinstance(value,datetime):
        need(value.utcoffset() is not None,'BACKUP_NAIVE_DATABASE_TIME');return {'instant':value.astimezone(timezone.utc).isoformat()}
    if isinstance(value,date):return {'date':value.isoformat()}
    if isinstance(value,Decimal):return {'decimal':str(value)}
    if isinstance(value,(list,tuple)):return [atom(x) for x in value]
    if isinstance(value,dict):return {k:atom(v) for k,v in value.items()}
    need(value is None or type(value) in (str,int,bool,float),'BACKUP_UNSUPPORTED_DATABASE_VALUE');return value
def canonical_check(definition):
    # PostgreSQL reparses BETWEEN into comparisons and may flatten nested AND
    # when restoring its deparsed CHECK text. Preserve operands, order, quoted
    # literals and AND/OR precedence; normalize only associative boolean groups.
    tokens=re.findall(r"E?'(?:''|\\.|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+(?:\.[0-9]+)?|::|>=|<=|<>|!=|\S",definition)
    if not tokens or tokens[0]!='CHECK':return definition
    need(len(tokens)>2 and tokens[1]=='(','BACKUP_CONSTRAINT_ENCODING')
    depth=0;closing=None
    for i,token in enumerate(tokens[1:],1):
        if token=='(':depth+=1
        elif token==')':
            depth-=1
            if depth==0:closing=i;break
    need(closing is not None,'BACKUP_CONSTRAINT_ENCODING')
    def expression(parts):
        while parts and parts[0]=='(':
            level=0;end=None
            for i,t in enumerate(parts):
                if t=='(':level+=1
                elif t==')':
                    level-=1
                    if level==0:end=i;break
            if end!=len(parts)-1:break
            parts=parts[1:-1]
        for operation in ('OR','AND'):
            level=0;cuts=[]
            for i,t in enumerate(parts):
                if t=='(':level+=1
                elif t==')':level-=1
                elif level==0 and t==operation:cuts.append(i)
                elif level==0 and t=='BETWEEN':return dict(atom=parts)
            if cuts:
                chunks=[];start=0
                for end in [*cuts,len(parts)]:
                    child=expression(parts[start:end]);chunks.extend(child['args'] if child.get('op')==operation else [child]);start=end+1
                return dict(op=operation,args=chunks)
        return dict(atom=parts)
    return dict(check=expression(tokens[2:closing]),suffix=tokens[closing+1:])
def row_digest(cursor,transform=None):
    h=sha256();count=0
    while True:
        batch=cursor.fetchmany(256)
        if not batch:break
        for row in batch:
            raw=canonical(atom(transform(row) if transform else row)).encode();h.update(len(raw).to_bytes(8,'big'));h.update(raw);count+=1
    return dict(rows=count,sha256=h.hexdigest())
def config_references(config):
    need(isinstance(config,RuntimeConfig) and config.schema_version=='0.1.0-config' and config.planning_timezone=='Asia/Shanghai','BACKUP_CONFIG_REQUIRED')
    need(isinstance(config.adapters,tuple) and {a.name for a in config.adapters}==ADAPTERS and len(config.adapters)==len(ADAPTERS),'BACKUP_CONFIG_ADAPTERS')
    adapters={}
    for a in config.adapters:
        need(a.mode in ('DISABLED','FAKE','LIVE') and (a.secret_ref is None or isinstance(a.secret_ref,SecretRef) and isinstance(a.secret_ref.env_name,str) and ENV_NAME.fullmatch(a.secret_ref.env_name)),'BACKUP_CONFIG_REFERENCE')
        adapters[a.name]=dict(mode=a.mode,secret_env=a.secret_ref.env_name if a.secret_ref else None)
    defs=[dict(kind=d.kind,id=d.definition_id,version=d.version,content_hash=d.content_hash) for d in config.definitions]
    need(all(isinstance(d['content_hash'],str) and HASH.fullmatch(d['content_hash']) for d in defs),'BACKUP_DEFINITION_HASH')
    value=dict(schema_version=config.schema_version,planning_timezone=config.planning_timezone,definitions=defs,adapters=adapters,authority='REFERENCES_ONLY_NO_ACTIVATION_OR_CREDENTIAL_VALUES')
    validate_config_references(value)
    need(len(canonical(value).encode())<=MAX_CONFIG,'BACKUP_CONFIG_SIZE_LIMIT');return value

def validate_config_references(refs):
    need(isinstance(refs,dict) and set(refs)=={'schema_version','planning_timezone','definitions','adapters','authority'} and refs['authority']=='REFERENCES_ONLY_NO_ACTIVATION_OR_CREDENTIAL_VALUES','BACKUP_CONFIG_REFERENCE_SHAPE')
    need(refs['schema_version']=='0.1.0-config' and refs['planning_timezone']=='Asia/Shanghai','BACKUP_CONFIG_REFERENCE_SHAPE')
    need(isinstance(refs['adapters'],dict) and set(refs['adapters'])==ADAPTERS,'BACKUP_CONFIG_REFERENCE_SHAPE')
    for name,item in refs['adapters'].items():
        need(isinstance(item,dict) and set(item)=={'mode','secret_env'} and item['mode'] in ('DISABLED','FAKE','LIVE'),'BACKUP_CONFIG_REFERENCE_SHAPE')
        key=item['secret_env'];need(key is None or isinstance(key,str) and ENV_NAME.fullmatch(key),'BACKUP_CONFIG_REFERENCE_SHAPE')
        if name=='state_store':need(item['mode']!='DISABLED' and (item['mode']!='LIVE' or key is not None),'BACKUP_CONFIG_REFERENCE_SHAPE')
    need(isinstance(refs['definitions'],list),'BACKUP_CONFIG_REFERENCE_SHAPE');seen=set()
    for d in refs['definitions']:
        need(isinstance(d,dict) and set(d)=={'kind','id','version','content_hash'},'BACKUP_CONFIG_REFERENCE_SHAPE')
        need(isinstance(d['kind'],str) and d['kind'] in KINDS and all(isinstance(d[k],str) and bool(d[k].strip()) and len(d[k])<=200 for k in ('id','version')) and isinstance(d['content_hash'],str) and HASH.fullmatch(d['content_hash']),'BACKUP_CONFIG_REFERENCE_SHAPE')
        identity=(d['kind'],d['id']);need(identity not in seen,'BACKUP_CONFIG_REFERENCE_SHAPE');seen.add(identity)
@dataclass(frozen=True)
class BackupBundle:
    path:Path
    manifest_hash:str

def bundle_path(harness,path):
    need(isinstance(harness,PostgresHarness),'BACKUP_OWNED_HARNESS_REQUIRED')
    owned_run(harness.run_root);chosen=Path(path).resolve()
    need(chosen.parent==harness.run_root and BUNDLE.fullmatch(chosen.name) is not None and not Path(path).is_symlink(),'BACKUP_BUNDLE_SCOPE');return chosen

def checked_bundle(harness,bundle,plan,application_version):
    need(isinstance(bundle,BackupBundle) and isinstance(bundle.manifest_hash,str) and HASH.fullmatch(bundle.manifest_hash),'BACKUP_INDEPENDENT_MANIFEST_PIN_REQUIRED')
    root=bundle_path(harness,bundle.path);need(root.is_dir(),'BACKUP_BUNDLE_NOT_AVAILABLE')
    need({p.name for p in root.iterdir()}=={'manifest.json','database.dump','configuration-refs.json'},'BACKUP_UNEXPECTED_BUNDLE_FILE')
    for name in ('manifest.json','database.dump','configuration-refs.json'):need((root/name).resolve().parent==root and not (root/name).is_symlink(),'BACKUP_FILE_SCOPE')
    need(digest_file(root/'manifest.json',MAX_MANIFEST)==bundle.manifest_hash,'BACKUP_MANIFEST_HASH_DRIFT')
    try:m=strict_json((root/'manifest.json').read_bytes())
    except Exception:raise BackupError('BACKUP_MANIFEST_SHAPE') from None
    need(isinstance(m,dict) and set(m)=={'bundle_version','scope','postgres_version','application_version','schema_version','source','captured_at','migration_pins','files','inventory'},'BACKUP_MANIFEST_SHAPE')
    need(m['bundle_version']=='0.1.0-development-backup' and m['scope']=='SYNTHETIC_OWNED_POSTGRES' and m['postgres_version']=='18.6','BACKUP_VERSION_OR_SCOPE')
    source=m['source'];need(isinstance(source,dict) and set(source)=={'run_id','database'} and isinstance(source['run_id'],str) and re.fullmatch('[a-f0-9]{32}',source['run_id']) and isinstance(source['database'],str) and re.fullmatch('wt_test_'+source['run_id']+'_[1-9][0-9]*',source['database']),'BACKUP_SOURCE_IDENTITY')
    try:
        captured=datetime.fromisoformat(m['captured_at']);need(captured.utcoffset() is not None,'BACKUP_CAPTURE_TIME')
    except (TypeError,ValueError):raise BackupError('BACKUP_CAPTURE_TIME') from None
    need(m['application_version']==application_version and m['schema_version']==plan.schema_version and m['migration_pins']==[dict(id=s.migration_id,sha256=s.content_hash,schema_version=s.schema_version) for s in plan.steps],'BACKUP_MIGRATION_PLAN_DRIFT')
    need(isinstance(m['files'],dict) and set(m['files'])=={'database.dump','configuration-refs.json'},'BACKUP_MANIFEST_FILE_SCOPE')
    for name,limit in (('database.dump',MAX_ARCHIVE),('configuration-refs.json',MAX_CONFIG)):
        pin=m['files'][name];need(isinstance(pin,dict) and set(pin)=={'sha256','bytes'} and type(pin['bytes']) is int and 0<pin['bytes']<=limit and isinstance(pin['sha256'],str) and HASH.fullmatch(pin['sha256']),'BACKUP_MANIFEST_FILE_PIN')
        need((root/name).stat().st_size==pin['bytes'] and digest_file(root/name,limit)==pin['sha256'],'BACKUP_FILE_HASH_DRIFT')
    with (root/'database.dump').open('rb') as f:need(f.read(5)==b'PGDMP','BACKUP_ARCHIVE_FORMAT')
    try:refs=strict_json((root/'configuration-refs.json').read_bytes())
    except Exception:raise BackupError('BACKUP_CONFIG_REFERENCE_SHAPE') from None
    validate_config_references(refs)
    return m,refs

def _owned_target(harness,database):
    target=harness.target(database,'migration')
    with target.connect() as conn:
        need(conn.execute('SHOW cluster_name').fetchone()[0]==harness.cluster_name and conn.execute('SHOW server_version').fetchone()[0]=='18.6','BACKUP_SERVER_IDENTITY')
        row=conn.execute("SELECT current_database(),current_user,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()
        need(row==(database,ROLES['migration'],ROLES['migration'],harness.cluster_name),'BACKUP_DATABASE_IDENTITY')
    return target

def client_arguments(harness,tool,args,*,target=None):
    need(tool in ('pg_dump','pg_restore') and isinstance(args,(list,tuple)),'BACKUP_CLIENT_ARGUMENT_SCOPE')
    parts=list(map(str,args));flags=[];options={};paths=[]
    for part in parts:
        if part.startswith('--'):
            if '=' in part:
                name,value=part.split('=',1);options.setdefault(name,[]).append(value)
            else:flags.append(part)
        else:paths.append(part)
    need(len(flags)==len(set(flags)) and all(len(values)==1 or name=='--schema' and len(values)==2 for name,values in options.items()),'BACKUP_CLIENT_ARGUMENT_SCOPE')
    def scoped_file(value,*,archive=False,output=False):
        path=Path(value);resolved=path.resolve();need(resolved.is_relative_to(harness.run_root) and not path.is_symlink(),'BACKUP_CLIENT_FILE_SCOPE')
        if archive:need(resolved.name=='database.dump' and resolved.parent.parent==harness.run_root and BUNDLE.fullmatch(resolved.parent.name),'BACKUP_CLIENT_FILE_SCOPE')
        if output:need(not resolved.exists(),'BACKUP_CLIENT_FILE_EXISTS')
        else:need(resolved.is_file(),'BACKUP_CLIENT_FILE_SCOPE')
        return resolved
    if tool=='pg_dump':
        need(target is not None and not paths and flags==['--strict-names'] and set(options)=={'--format','--schema','--snapshot','--file'},'BACKUP_CLIENT_ARGUMENT_SCOPE')
        need(options['--format']==['custom'] and sorted(options['--schema'])==list(SCHEMAS) and re.fullmatch('[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+',options['--snapshot'][0]),'BACKUP_CLIENT_ARGUMENT_SCOPE')
        scoped_file(options['--file'][0],archive=True,output=True)
    elif target is not None:
        need(len(paths)==1 and set(flags)=={'--single-transaction','--exit-on-error','--no-owner'} and set(options) in ({'--dbname'},{'--dbname','--use-list'}) and options['--dbname']==[target.database],'BACKUP_CLIENT_ARGUMENT_SCOPE')
        scoped_file(paths[0],archive=True)
        if '--use-list' in options:scoped_file(options['--use-list'][0])
    else:
        need(len(paths)==1 and (flags==['--list'] and not options or not flags and set(options)=={'--file'}),'BACKUP_CLIENT_ARGUMENT_SCOPE')
        scoped_file(paths[0],archive=True)
        if '--file' in options:scoped_file(options['--file'][0],output=True)
    return parts

def run_pg(harness,tool,args,*,target=None):
    args=client_arguments(harness,tool,args,target=target);harness._owned()
    binary=harness.binary/(tool+'.exe');need(binary.resolve().parent==harness.binary.resolve() and binary.is_file(),'BACKUP_BINARY_SCOPE')
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')};env.update(TEMP=str(harness.run_root),TMP=str(harness.run_root),PGCLIENTENCODING='UTF8',PGAPPNAME='WhatToDoOwnedBackup')
    passfile=None
    try:
        if target is not None:
            need(isinstance(target,ConnectionTarget) and target==harness.target(target.database,'migration'),'BACKUP_OWNED_CONNECTION_REQUIRED')
            need(target.role==ROLES['migration'],'BACKUP_OWNER_ROLE_REQUIRED')
            passfile=harness.run_root/('backup-client-'+uuid4().hex+'.pgpass');need(passfile.resolve().parent==harness.run_root,'BACKUP_PASSFILE_SCOPE')
            password=target._password;need(isinstance(password,str) and '\n' not in password and '\r' not in password,'BACKUP_PASSWORD_FRAMING')
            line=':'.join(str(x).replace('\\','\\\\').replace(':','\\:') for x in ('127.0.0.1',target.port,target.database,target.role,password))+'\n'
            with passfile.open('x',encoding='utf-8',newline='\n') as f:f.write(line)
            os.chmod(passfile,0o600)
            env.update(PGPASSFILE=str(passfile),PGHOST='127.0.0.1',PGHOSTADDR='127.0.0.1',PGPORT=str(target.port),PGUSER=target.role,PGDATABASE=target.database,PGSSLMODE='disable',PGGSSENCMODE='disable',PGCONNECT_TIMEOUT='5',PGOPTIONS='-c statement_timeout=15000 -c lock_timeout=5000')
        result=subprocess.run([str(binary),*map(str,args)],cwd=harness.run_root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        need(result.returncode==0,'BACKUP_DUMP_FAILED' if tool=='pg_dump' else 'BACKUP_RESTORE_FAILED');return result.stdout
    except (OSError,subprocess.SubprocessError):raise BackupError('BACKUP_CLIENT_PROCESS_FAILED') from None
    finally:
        if passfile is not None and passfile.exists():passfile.unlink()

def _tables(conn):return conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('whattodo','whattodo_meta') ORDER BY 1,2").fetchall()
def _sequences(conn):
    from psycopg import sql
    values={}
    for schema,name in conn.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname IN ('whattodo','whattodo_meta') ORDER BY 1,2").fetchall():
        values[schema+'.'+name]=list(conn.execute(sql.SQL('SELECT last_value,is_called FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(name))).fetchone())
    return values

def inventory(conn):
    from psycopg import sql
    conn.execute('SET LOCAL search_path=pg_catalog');tables={}
    for schema,name in _tables(conn):
        columns=conn.execute('SELECT count(*) FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped',(schema+'.'+name,)).fetchone()[0]
        tables[schema+'.'+name]=row_digest(conn.execute(sql.SQL('SELECT * FROM {}.{} ORDER BY ').format(sql.Identifier(schema),sql.Identifier(name))+sql.SQL(',').join(sql.Literal(i) for i in range(1,columns+1))))
    where="n.nspname IN ('whattodo','whattodo_meta')"
    queries={
      'columns':"SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum WHERE "+where+" AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3",
      'constraints':"SELECT n.nspname,coalesce(c.relname,t.typname),q.conname,q.contype,q.condeferrable,q.condeferred,q.convalidated,q.connoinherit,q.conislocal,q.coninhcount,pg_get_constraintdef(q.oid) FROM pg_constraint q JOIN pg_namespace n ON n.oid=q.connamespace LEFT JOIN pg_class c ON c.oid=q.conrelid LEFT JOIN pg_type t ON t.oid=q.contypid WHERE "+where+" ORDER BY 1,2,3",
      'indexes':"SELECT n.nspname,c.relname,pg_get_indexdef(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "+where+" AND c.relkind='i' ORDER BY 1,2",
      'functions':"SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE "+where+" ORDER BY 1,2,3",
      'triggers':"SELECT n.nspname,c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "+where+" AND NOT t.tgisinternal ORDER BY 1,2,3",
      'domains':"SELECT n.nspname,t.typname,format_type(t.typbasetype,t.typtypmod),t.typnotnull,t.typdefault FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE "+where+" AND t.typtype='d' ORDER BY 1,2",
      'table_permissions':"SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner),ARRAY(SELECT concat_ws(':',pg_get_userbyid(x.grantor),CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,x.privilege_type,x.is_grantable::text) FROM aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 's'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) x ORDER BY 1) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "+where+" AND c.relkind IN ('r','S') ORDER BY 1,2",
      'function_permissions':"SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),pg_get_userbyid(p.proowner),ARRAY(SELECT concat_ws(':',pg_get_userbyid(x.grantor),CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,x.privilege_type,x.is_grantable::text) FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) x ORDER BY 1) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE "+where+" ORDER BY 1,2,3",
      'schema_permissions':"SELECT n.nspname,pg_get_userbyid(n.nspowner),ARRAY(SELECT concat_ws(':',pg_get_userbyid(x.grantor),CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,x.privilege_type,x.is_grantable::text) FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) x ORDER BY 1) FROM pg_namespace n WHERE "+where+" ORDER BY 1",
      'sequence_definitions':"SELECT n.nspname,c.relname,format_type(s.seqtypid,-1),s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "+where+" ORDER BY 1,2"}
    catalogs={name:row_digest(conn.execute(query),transform=(lambda row:tuple(row[:-1])+(canonical_check(row[-1]),)) if name=='constraints' else None) for name,query in queries.items()}
    epoch=conn.execute('SELECT revision,last_transaction_ref FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone();need(epoch is not None,'BACKUP_EPOCH_UNAVAILABLE')
    return dict(tables=tables,catalogs=catalogs,sequences=_sequences(conn),store_revision=epoch[0],last_transaction_ref=epoch[1])

def create_backup(harness,database,*,plan,application_version,config,clock):
    refs=config_references(config);target=_owned_target(harness,database)
    root=bundle_path(harness,harness.run_root/('backup_'+uuid4().hex));root.mkdir(exist_ok=False)
    try:
        with target.connect() as conn:
            with schema_checked_transaction(conn,plan,application_version=application_version):
                snapshot=conn.execute('SELECT pg_export_snapshot()').fetchone()[0];need(isinstance(snapshot,str) and re.fullmatch('[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+',snapshot),'BACKUP_SNAPSHOT_IDENTITY')
                captured=inventory(conn)
                run_pg(harness,'pg_dump',['--format=custom','--schema=whattodo','--schema=whattodo_meta','--strict-names','--snapshot='+snapshot,'--file='+str(root/'database.dump')],target=target)
                need(_sequences(conn)==captured['sequences'],'BACKUP_SEQUENCE_CHANGED_DURING_CAPTURE')
        (root/'configuration-refs.json').write_bytes(canonical(refs).encode())
        files={name:dict(sha256=digest_file(root/name,limit),bytes=(root/name).stat().st_size) for name,limit in (('database.dump',MAX_ARCHIVE),('configuration-refs.json',MAX_CONFIG))}
        now=clock.now();need(isinstance(now,datetime) and now.utcoffset() is not None,'BACKUP_CLOCK_REQUIRED')
        m=dict(bundle_version='0.1.0-development-backup',scope='SYNTHETIC_OWNED_POSTGRES',postgres_version='18.6',application_version=application_version,schema_version=plan.schema_version,source=dict(run_id=harness.run_id,database=database),captured_at=now.isoformat(),migration_pins=[dict(id=s.migration_id,sha256=s.content_hash,schema_version=s.schema_version) for s in plan.steps],files=files,inventory=captured)
        raw=canonical(m).encode();need(len(raw)<=MAX_MANIFEST,'BACKUP_MANIFEST_SIZE_LIMIT');(root/'manifest.json').write_bytes(raw);return BackupBundle(root,sha256(raw).hexdigest())
    except BackupError:raise
    except Exception:raise BackupError('BACKUP_CAPTURE_FAILED') from None

def _empty(conn):
    schemas=conn.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('information_schema','public')").fetchall()
    occupied=conn.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public') OR EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public') OR EXISTS(SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public')").fetchone()[0]
    need(not schemas and not occupied,'BACKUP_EMPTY_TARGET_REQUIRED')

def validate_restored(harness,database,bundle,*,plan,application_version):
    m,refs=checked_bundle(harness,bundle,plan,application_version);target=_owned_target(harness,database)
    with target.connect() as conn:
        with schema_checked_transaction(conn,plan,application_version=application_version):actual=inventory(conn)
    if actual!=m['inventory']:
        expected=m['inventory'];groups=[k for k in actual if actual[k]!=expected.get(k)]
        categories=[k for k in actual['catalogs'] if actual['catalogs'][k]!=expected.get('catalogs',{}).get(k)]
        raise BackupError('BACKUP_RESTORED_STATE_OR_SCHEMA_DRIFT',diagnostic=dict(groups=groups,catalog_categories=categories,table_mismatch_count=sum(v!=expected.get('tables',{}).get(k) for k,v in actual['tables'].items())))
    return dict(status='VERIFIED',tables_checked=len(actual['tables']),store_revision=actual['store_revision'],configuration_refs=refs)

def restore_backup(harness,database,bundle,*,plan,application_version):
    m,refs=checked_bundle(harness,bundle,plan,application_version)
    need(database!=m['source']['database'],'BACKUP_SOURCE_OVERWRITE_DENIED')
    target=_owned_target(harness,database)
    with target.connect() as conn:_empty(conn)
    # Full custom restore retains reviewed ACLs and recreates constraints/triggers.
    # No --clean, --create, superuser, role export or trigger disabling is used.
    run_pg(harness,'pg_restore',['--single-transaction','--exit-on-error','--no-owner','--dbname='+database,str(bundle.path/'database.dump')],target=target)
    return validate_restored(harness,database,bundle,plan=plan,application_version=application_version)
