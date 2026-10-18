"""Checked engine persistence for application property lifecycles.

This is not another property registry/resolver or a second world history.
Application authorization and resolver policy sit at the receiving boundary;
the native engine still validates base assignments and commits world events.
"""
import hashlib
import json
from ..engine import require,digest
from ..resources import schema_path


def verify_property_changes(engine):
    db=engine.db
    version=db.execute("SELECT version FROM engine_versions WHERE component='property_change_interface'").fetchone()
    require(version and version[0]=='1','unsupported property change interface')
    check=db.execute('SELECT checksum FROM migration_checks WHERE version=28').fetchone()
    require(check and check[0]==hashlib.sha256(schema_path('migration_028.sql').read_bytes()).hexdigest(),'property change migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(),'property change foreign key failure')
    for row in db.execute('SELECT * FROM property_selections'):
        require(digest(json.loads(row['frozen_json']))==row['frozen_digest'],'selection digest mismatch')
    for row in db.execute('SELECT * FROM property_change_sets'):
        require(digest(json.loads(row['proposal_json']))==row['proposal_digest'],'change proposal digest mismatch')
        snapshot=db.execute('SELECT * FROM property_selections WHERE snapshot_id=?',(row['snapshot_id'],)).fetchone()
        require(snapshot and snapshot['workspace_id']==row['workspace_id'] and snapshot['principal_id']==row['principal_id'] and snapshot['authority_epoch']==row['authority_epoch'],'change selection binding mismatch')
        reference=json.loads(row['diff_ref_json'])
        artifact=db.execute('SELECT workspace_id,digest FROM artifacts WHERE artifact_id=?',(reference['id'],)).fetchone()
        require(artifact and artifact['workspace_id']==row['workspace_id'] and artifact['digest']==reference['digest'] and reference['version']==1,'change diff artifact mismatch')
        require(row['status'] not in ('active','waiting') or row['applied_event'],'active change lacks native event')
    for row in db.execute('SELECT * FROM property_effects'):
        value=json.loads(row['override_json'])
        require(digest(value)==row['override_digest'] and value['effect_id']==row['effect_id'] and value['version']==row['version'] and
            value['property_id']==row['property_id'] and value['definition_version']==row['definition_version'],'property effect binding mismatch')
        change=db.execute('SELECT * FROM property_change_sets WHERE change_id=?',(row['change_id'],)).fetchone()
        proposal=json.loads(change['proposal_json'])
        require(change['workspace_id']==row['workspace_id'] and row['entity_id'] in proposal['targets'] and value in proposal['overrides'],'effect proposal mismatch')
        require(row['state']!='active' or (change['status'] in ('active','waiting') and row['ended_event'] is None),'active effect lifecycle mismatch')
        require(row['state']!='ended' or row['ended_event'] is not None,'ended effect lacks event')
    for row in db.execute('SELECT * FROM property_support_bindings'):
        record=engine.get(row['branch'],row['resource_id'])
        require(record and record['domain']=='resource','support resource unavailable')
        require(record['data']['holder']==(row['entity_id'] if row['active'] else 'studio'),'support binding/native resource mismatch')
        require(record['data']['unit']=='kg' and record['data']['quantity']==12 and record['data']['availability']==('supported' if row['active'] else 'on the studio floor'),'support native resource contents mismatch')
        reference=json.loads(row['trace_ref_json'])
        artifact=db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(reference['id'],)).fetchone()
        require(artifact and artifact['workspace_id']==row['workspace_id'] and artifact['digest']==reference['digest'] and reference['version']==1,'support trace artifact mismatch')
        require(json.loads(bytes(artifact['content']))==json.loads(row['dependency_json']),'support trace/dependency mismatch')
    return {'installed':True,'interface':'1'}
