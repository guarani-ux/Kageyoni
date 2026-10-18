"""Verify operational installed-content pins; native facts remain native."""
import hashlib
import json
from ..engine import require, digest
from ..resources import schema_path


def verify_extensions(engine):
    db=engine.db
    version=db.execute("SELECT version FROM engine_versions WHERE component='extension_lifecycle_interface'").fetchone()
    require(version and version[0]=='1','unsupported extension lifecycle interface')
    checksum=db.execute('SELECT checksum FROM migration_checks WHERE version=30').fetchone()
    require(checksum and checksum[0]==hashlib.sha256(schema_path('migration_030.sql').read_bytes()).hexdigest(),'extension migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(),'extension foreign key failure')
    for row in db.execute('SELECT * FROM extension_assets'):
        require(digest(json.loads(row['content_json']))==row['digest'],'extension asset content digest mismatch')
    for row in db.execute('SELECT * FROM extension_versions'):
        require(digest(json.loads(row['manifest_json']))==row['manifest_digest'],'extension manifest digest mismatch')
        for key in ('capsule_ref_json','preview_ref_json','ending_trace_ref_json'):
            if row[key] is None:continue
            ref=json.loads(row[key]);asset=db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(ref['id'],)).fetchone()
            require(asset and asset['workspace_id']==row['workspace_id'] and asset['digest']==ref['digest'] and ref['version']==1,'extension retained artifact mismatch')
    for row in db.execute('SELECT * FROM extension_pins'):
        table,column=('property_change_sets','change_id') if row['kind']=='change' else ('property_support_bindings','support_id')
        require(db.execute(f'SELECT 1 FROM {table} WHERE workspace_id=? AND {column}=?',(row['workspace_id'],row['reference_id'])).fetchone(),'extension consumer pin unavailable')
    return {'installed':True,'interface':'1'}
