"""Explicit additive node migration; Engine opening alone does not install it."""
import hashlib
import sqlite3
from pathlib import Path
from ..resources import schema_path
from ..engine import require
from .unit_of_work import UnitOfWork

MIGRATION=schema_path('migration_009.sql')

def install_nodes(engine):
    db=engine.db
    require(not db.in_transaction,'install nodes before starting a unit of work')
    checksum=hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
    old=db.execute('SELECT checksum FROM migration_checks WHERE version=9').fetchone()
    if old:
        require(old[0]==checksum,'node migration checksum mismatch')
        row=db.execute("SELECT version FROM engine_versions WHERE component='node_interface'").fetchone()
        require(row and row[0]=='1','unsupported node interface')
        return
    require(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==8,'node migration predecessor mismatch')
    require(engine.verify()['ok'],'baseline verification failed')
    # A unique backup is made for every attempt; never reuse a stale backup.
    from uuid import uuid4
    engine.migration_backup(Path(engine.path).with_name(Path(engine.path).name+'.pre-v9-'+uuid4().hex+'.bak'))
    with UnitOfWork(db):
        statement=''
        for line in MIGRATION.read_text().splitlines(keepends=True):
            statement+=line
            if sqlite3.complete_statement(statement):
                db.execute(statement);statement=''
        require(not statement.strip(),'incomplete migration statement')
        require(not db.execute('PRAGMA foreign_key_check').fetchall(),'node migration foreign key failure')
        require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','node migration integrity failure')
        db.execute("INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(9,8,'migration_009.sql',?,'4')",(checksum,))
    require(engine.verify()['ok'],'post-migration verification failed')

METHOD_MIGRATION=schema_path('migration_010.sql')
CONTRIBUTION_MIGRATION=schema_path('migration_011.sql')

def _install_component(engine, path, version, predecessor, component):
    db=engine.db
    require(not db.in_transaction,'install interfaces before starting a unit of work')
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    old=db.execute('SELECT checksum FROM migration_checks WHERE version=?',(version,)).fetchone()
    if old:
        require(old[0]==checksum,component+' migration checksum mismatch')
        row=db.execute('SELECT version FROM engine_versions WHERE component=?',(component,)).fetchone()
        require(row and row[0]=='1','unsupported '+component)
        return
    require(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==predecessor,component+' migration predecessor mismatch')
    require(engine.verify()['ok'],'baseline verification failed')
    from uuid import uuid4
    engine.migration_backup(Path(engine.path).with_name(Path(engine.path).name+'.pre-v'+str(version)+'-'+uuid4().hex+'.bak'))
    with UnitOfWork(db):
        statement=''
        for line in path.read_text().splitlines(keepends=True):
            statement+=line
            if sqlite3.complete_statement(statement):
                db.execute(statement);statement=''
        require(not statement.strip(),'incomplete migration statement')
        require(not db.execute('PRAGMA foreign_key_check').fetchall(),'migration foreign key failure')
        require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','migration integrity failure')
        db.execute('INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(?,?,?,?,?)',
                   (version,predecessor,path.name,checksum,'4'))
        require(engine.verify()['ok'],'post-migration verification failed')

def install_methods(engine):
    install_nodes(engine)
    _install_component(engine,METHOD_MIGRATION,10,9,'method_interface')

def install_contributions(engine):
    install_methods(engine)
    _install_component(engine,CONTRIBUTION_MIGRATION,11,10,'contribution_interface')

LEARNING_MIGRATION=schema_path('migration_012.sql')

def install_learning(engine):
    install_contributions(engine)
    _install_component(engine,LEARNING_MIGRATION,12,11,'learning_interface')

ENCOUNTER_MIGRATION=schema_path('migration_013.sql')
WORKSPACE_MIGRATION=schema_path('migration_014.sql')
NETWORK_MIGRATION=schema_path('migration_015.sql')
PIPELINE_MIGRATION=schema_path('migration_016.sql')
OPERATIONS_MIGRATION=schema_path('migration_017.sql')
COMPOSITION_MIGRATION=schema_path('migration_018.sql')
V11_MIGRATION=schema_path('migration_019.sql')
V11_RUNTIME_MIGRATION=schema_path('migration_020.sql')
V11_ENFORCER_EVAL_MIGRATION=schema_path('migration_021.sql')
V11_TRUST_MIGRATION=schema_path('migration_022.sql')
SITUATION_MIGRATION=schema_path('migration_023.sql')

def install_encounters(engine):
    install_learning(engine)
    _install_component(engine,ENCOUNTER_MIGRATION,13,12,'encounter_interface')

def install_workspaces(engine):
    install_encounters(engine)
    _install_component(engine,WORKSPACE_MIGRATION,14,13,'workspace_interface')

def install_network(engine):
    install_workspaces(engine)
    _install_component(engine,NETWORK_MIGRATION,15,14,'network_interface')

def install_pipelines(engine):
    install_network(engine)
    _install_component(engine,PIPELINE_MIGRATION,16,15,'pipeline_interface')

def install_operations(engine):
    install_pipelines(engine)
    _install_component(engine,OPERATIONS_MIGRATION,17,16,'operations_interface')

def install_composition(engine):
    install_operations(engine)
    _install_component(engine,COMPOSITION_MIGRATION,18,17,'composition_interface')
    from ..composition.registry import CompositionRegistry
    CompositionRegistry(engine).install_builtins()

def install_v11(engine):
    install_composition(engine)
    _install_component(engine,V11_MIGRATION,19,18,'v11_enforcement')
    _install_component(engine,V11_RUNTIME_MIGRATION,20,19,'v11_runtime')
    _install_component(engine,V11_ENFORCER_EVAL_MIGRATION,21,20,'v11_enforcer_eval')
    _install_component(engine,V11_TRUST_MIGRATION,22,21,'v11_trust')

def install_situations(engine):
    install_v11(engine)
    _install_component(engine,SITUATION_MIGRATION,23,22,'situation_architecture')

def install_all(engine):
    install_situations(engine)

SHINOBI_MIGRATION=schema_path('migration_024.sql')

def install_shinobi(engine):
    """Opt-in Kageyoni-Shinobi protocol storage on top of the full engine schema.

    Deliberately not part of install_all(): existing campaign databases keep
    their schema unless a Shinobi home explicitly installs this interface.
    """
    install_all(engine)
    _install_component(engine,SHINOBI_MIGRATION,24,23,'shinobi_interface')

def install_action_dispatch(engine):
    """Opt-in issued requests; preserve legacy dispatch rows unchanged."""
    install_shinobi(engine)
    _install_component(engine,schema_path('migration_025.sql'),25,24,'action_dispatch_interface')


def install_activities(engine):
    """Opt-in application continuation on the separately versioned engine."""
    install_action_dispatch(engine)
    _install_component(engine,schema_path('migration_026.sql'),26,25,'activity_interface')


def install_activity_queue(engine):
    """Explicit maintenance only; opening an older world does not install it."""
    install_activities(engine)
    _install_component(engine,schema_path('migration_027.sql'),27,26,'activity_queue_interface')


def install_property_changes(engine):
    """Explicit maintenance; participants cannot silently upgrade a save."""
    install_activity_queue(engine)
    _install_component(engine,schema_path('migration_028.sql'),28,27,'property_change_interface')


def install_causal_delivery(engine):
    install_property_changes(engine)
    _install_component(engine,schema_path('migration_029.sql'),29,28,'causal_delivery_interface')


def install_extensions(engine):
    install_causal_delivery(engine)
    _install_component(engine,schema_path('migration_030.sql'),30,29,'extension_lifecycle_interface')


def install_resource_profiles(engine):
    """Explicit future capacity profile; never installed by merely opening a world."""
    install_extensions(engine)
    _install_component(engine,schema_path('migration_031.sql'),31,30,'resource_profile_interface')
    from ..workspaces.resource_profiles import verify_resource_profiles
    verify_resource_profiles(engine)


def install_resource_admission(engine):
    """Explicit indexed membership and native configured-capacity gates."""
    install_resource_profiles(engine)
    # A v31 trusted writer can retain activities before v32's final-usage
    # guard exists. Refuse an over-capacity predecessor before changing its
    # schema, even when the caller has not yet integrated the global hook.
    from ..workspaces.resource_admission import _validate_configured_usage
    for row in engine.db.execute('SELECT workspace_id FROM operational_workspaces'):
        _validate_configured_usage(engine,row['workspace_id'])
    _install_component(engine,schema_path('migration_032.sql'),32,31,'resource_admission_interface')
    from ..workspaces.resource_admission import verify_resource_admission
    verify_resource_admission(engine)


def install_worker_liveness(engine):
    """Explicit opt-in033; preserve old attempts and checked v32 predecessors."""
    install_resource_admission(engine)
    _install_component(engine,schema_path('migration_033.sql'),33,32,'worker_liveness_interface')
    from ..workspaces.worker_liveness import verify_worker_liveness
    verify_worker_liveness(engine)


def install_worker_custody(engine):
    """Explicit034 companion history; never backfill old process observations."""
    from .migration_034 import install_worker_custody as install
    install(engine)
