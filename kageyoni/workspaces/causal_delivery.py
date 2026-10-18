"""Native event/process delivery metadata verification, not a second world."""
import hashlib,json
from ..engine import require,digest
from ..resources import schema_path


def verify_causal_delivery(engine):
    db=engine.db
    version=db.execute("SELECT version FROM engine_versions WHERE component='causal_delivery_interface'").fetchone()
    require(version and version[0]=='1','unsupported causal delivery interface')
    row=db.execute('SELECT checksum FROM migration_checks WHERE version=29').fetchone()
    require(row and row[0]==hashlib.sha256(schema_path('migration_029.sql').read_bytes()).hexdigest(),'causal delivery migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(),'causal delivery foreign key failure')
    for root in db.execute('SELECT * FROM causal_roots'):
        event=db.execute('SELECT * FROM events WHERE id=?',(root['source_event'],)).fetchone()
        require(event and event['kind']=='world_event','causal source event unavailable')
        require(digest(json.loads(event['command_json']))==root['source_digest'],'causal source digest mismatch')
    for row in db.execute('SELECT * FROM causal_deliveries'):
        event=db.execute('SELECT branch FROM events WHERE id=?',(row['source_event'],)).fetchone()
        require(event and engine._current_process(event['branch'],row['process_id']),'causal process unavailable')
        if row['state']=='delivered':require(row['result_event'] and row['trace_ref_json'],'delivered causal work lacks native event/trace')
        if row['trace_ref_json']:
            ref=json.loads(row['trace_ref_json']);artifact=db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(ref['id'],)).fetchone()
            require(artifact and artifact['workspace_id']==row['workspace_id'] and artifact['digest']==ref['digest'] and ref['version']==1,'causal trace artifact mismatch')
    return {'installed':True,'interface':'1'}
