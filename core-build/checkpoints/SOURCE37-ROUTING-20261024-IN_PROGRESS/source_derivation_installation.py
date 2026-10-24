"""Optional037 exact layout classifier. No implicit install or DDL mutation.

The checked installer and full service are NOT implemented by this module.
Layout identity is separate from creation-history/current-permission checks.
"""
import hashlib,re,sqlite3
from .source_derivation_facts import DOMAIN,PREFIX,OP_PREFIX,require
from .source_derivation_history import signal,projection_signal
from kageyoni.workspaces.source_authority_installation import strict_json

DOMAINS={DOMAIN:{'contract':'json'}}
REQUIRED={DOMAIN:['contract']}
COMPONENT='source_derivation_interface';INTERFACE='1'
LOCATOR="kageyoni/workspaces/source_derivations.py:DOMAINS['source_derivation']"

def schema_objects(source):
    statement='';result={};aliases=set()
    for line in source.splitlines(keepends=True):
        if line.lstrip().startswith('--'):continue
        for character in line:
            statement+=character
            if character!=';'or not sqlite3.complete_statement(statement):continue
            m=re.match(r'\s*CREATE\s+(?:UNIQUE\s+)?(TABLE|TRIGGER|INDEX)\s+"?(\w+)"?\b',statement,re.I)
            require(m is not None,'derivation migration must contain explicit DDL only')
            key=(m[1].lower(),m[2]);alias=(key[0],key[1].casefold());require(alias not in aliases,'aliased/repeated derivation object');aliases.add(alias);result[key]=statement.strip().rstrip(';');statement=''
    require(not statement.strip()and ('table',DOMAIN)in result,'incomplete derivation DDL');return result

def classify_layout(objects,expected,*,facts=False,marker=False,checksum=False,registry=False,nonempty=False):
    require(all(type(v)is bool for v in (facts,marker,checksum,registry,nonempty)),'strict layout flags required')
    if marker or checksum:
        require(marker and checksum and registry and objects==expected,'partial/mismatched derivation installation');return 'installed'
    require(not facts and not registry and not nonempty,'unmarked derivation facts cannot be adopted')
    if not objects:return 'absent'
    require(objects=={k:v for k,v in expected.items()if k==('table',DOMAIN)},'partial derivation projection/layout');return 'pristine'

def installation_state(engine,source):
    """source is exact bundled SQL bytes, never caller-selected executable DDL.

    Fixed future facade must supply schema_path('migration_037.sql').read_bytes.
    No runtime activation authority is granted by passing layout classification.
    """
    require(type(source)is bytes,'exact fixed SQL bytes required');db=engine.db
    expected=schema_objects(source.decode('utf-8'));objects={};implicit=[]
    for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master'):
        kind,name,table,sql=tuple(row)
        if sql is None and kind=='index'and table==DOMAIN and name=='sqlite_autoindex_source_derivation_1':implicit.append(name);continue
        if name.casefold().startswith(('source_derivation','source-derivation'))or table.casefold()==DOMAIN or sql is not None and re.search(r'\bsource_derivation\b',sql,re.I):objects[kind,name]=sql.strip().rstrip(';')if sql else None
    require(bool(implicit)==(('table',DOMAIN)in objects)and len(implicit)<=1,'implicit derivation primary-key index differs')
    markers=[tuple(r)for r in db.execute('SELECT component,version FROM engine_versions')if r[0].casefold().startswith(('source_derivation','source-derivation'))]
    checks=[tuple(r)for r in db.execute('SELECT checksum,predecessor,script_name,engine_min FROM migration_checks WHERE version=37')]
    registry=[]
    for r in db.execute('SELECT kind,stable_id,version,status,locator,compatibility_json FROM registry_entries'):
        kind,stable,version,status,locator,compat=tuple(r)
        if stable.casefold().startswith(('source_derivation','source-derivation','migration_037'))or 'source_derivation'in locator.casefold()or signal(strict_json(compat)):registry.append(tuple(r))
    facts=False
    for r in db.execute('SELECT * FROM records'):
        facts=(r['domain'].casefold().startswith(DOMAIN)or r['id'].casefold().startswith(PREFIX)or signal(strict_json(r['audience_json']))or signal(strict_json(r['evidence_json']))or projection_signal(db,r)or facts)
    for r in db.execute('SELECT * FROM changes'):
        facts=r['record_id'].casefold().startswith(PREFIX)or any(signal(strict_json(r[k]))for k in ('before_json','after_json')if r[k]is not None)or facts
    for r in db.execute('SELECT * FROM events'):
        facts=r['request_id'].casefold().startswith(OP_PREFIX)or r['kind'].casefold().startswith(DOMAIN)or signal(strict_json(r['command_json']))or signal(strict_json(r['receipt_json']))or facts
    for r in db.execute('SELECT state_json FROM snapshots'):facts=signal(strict_json(r[0]))or facts
    for r in db.execute('SELECT request_id FROM artifacts'):facts=r[0].casefold().startswith('source-derivation-output:')or facts
    nonempty=bool(('table',DOMAIN)in objects and db.execute('SELECT 1 FROM source_derivation LIMIT 1').fetchone())
    state=classify_layout(objects,expected,facts=bool(facts),marker=bool(markers),checksum=bool(checks),registry=bool(registry),nonempty=nonempty)
    if state=='installed':
        from .. import model
        require(model.DOMAINS.get(DOMAIN)==DOMAINS[DOMAIN]and model.REQUIRED.get(DOMAIN)==REQUIRED[DOMAIN],'derivation model binding differs')
        require(markers==[(COMPONENT,INTERFACE)]and checks==[(hashlib.sha256(source).hexdigest(),36,'migration_037.sql','4')],'derivation marker/checksum/predecessor differs')
        require(registry==[('domain',DOMAIN,'1','verified',LOCATOR,'{"source_derivation_interface":"1"}')],'derivation registry differs')
        require(not db.execute('SELECT 1 FROM source_derivation p LEFT JOIN records r ON r.branch=p.branch AND r.id=p.id WHERE r.domain IS NULL OR r.domain<>? LIMIT 1',(DOMAIN,)).fetchone(),'orphan derivation projection')
        require(not db.execute('SELECT 1 FROM records r LEFT JOIN source_derivation p ON p.branch=r.branch AND p.id=r.id WHERE r.domain=? AND p.id IS NULL LIMIT 1',(DOMAIN,)).fetchone(),'missing derivation projection')
    return state


def install_source_derivation(engine):
    """Explicit checked036 predecessor, unique backup, atomic fixed037 DDL.

    Authored source only: not installed/qualified and not a producer build GO.
    No arbitrary script, callback, implicit upgrade or marker-only success.
    """
    from .source_derivations import verify_source_derivations
    from .source_authorities import verify_source_authorities
    from .source_authority_installation import _maintenance_token
    from ..resources import schema_path
    from ..persistence.unit_of_work import UnitOfWork
    from pathlib import Path
    from uuid import uuid4
    import stat
    db=engine.db
    require(not db.in_transaction and not db.execute('PRAGMA query_only').fetchone()[0],'finish writable unit before installation')
    source=schema_path('migration_037.sql').read_bytes();state=installation_state(engine,source)
    if state=='installed':
        require(engine.verify()['ok']and engine.validate_registry()['ok'],'installed derivation verification failed')
        return verify_source_derivations(engine)
    require(state in ('absent','pristine'),'invalid derivation predecessor layout')
    require(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==36 and verify_source_authorities(engine)['installed'],'actual checked036 predecessor required')
    token=_maintenance_token(engine);verification=engine.verify();registry=engine.validate_registry()
    require(verification['ok']and registry['ok']and _maintenance_token(engine)==token,'derivation preflight failed/changed')
    require(str(engine.path)!=':memory:','real file-backed checked backup required')
    destination=Path(engine.path).with_name(Path(engine.path).name+'.pre-v37-'+uuid4().hex+'.bak')
    backup=engine.backup(destination)
    require(Path(backup).resolve()==destination.resolve()and stat.S_ISREG(destination.lstat().st_mode),'checked backup publication differs')
    backup_proof={'path':str(destination),'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
    objects=schema_objects(source.decode())
    with UnitOfWork(db):
        require(_maintenance_token(engine)==token and installation_state(engine,source)==state,'world/layout changed during backup')
        require(schema_path('migration_037.sql').read_bytes()==source,'fixed DDL changed')
        for (kind,name),statement in objects.items():
            if state=='pristine'and kind=='table':continue
            db.execute(statement)
        db.execute('INSERT INTO engine_versions(component,version) VALUES(?,?)',(COMPONENT,INTERFACE))
        db.execute('INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(?,?,?,?,?)',(37,36,'migration_037.sql',hashlib.sha256(source).hexdigest(),'4'))
        engine.register_component('domain',DOMAIN,'1',LOCATOR,status='verified',readers=['verify_source_derivations'],writers=[],compatibility={COMPONENT:INTERFACE},declared_by='explicit-source-derivation-installer')
        result=verify_source_derivations(engine)
        require(engine.verify()['ok']and engine.validate_registry()['ok'],'post-install derivation global/registry verification failed')
    result['maintenance']={'checked_backup':backup_proof,'preflight_verification':verification,'preflight_registry':registry}
    return result
