"""Isolated metadata preflight proposal, NOT installed Native21/producer.

Consumes an actual Native20 Engine and owning UoW. Never reads an artifact
body, creates a fact, mints host authority, or alters a permission. Native
viewer=None is existing owner authorization, not authenticated host identity.
"""
from copy import deepcopy
from source_derivation_inputs import requested_occurrences

PROFILE='samsara-source-derivation-inputs/20261024-1'
SOURCE_COLUMNS='workspace_id,source_id,revision,request_id,payload_hash,artifact_id,metadata_json'
ARTIFACT_COLUMNS='artifact_id,workspace_id,viewer,request_id,payload_hash,digest,media_type,size'

def bind_inquiry_inputs(engine, payload, unit):
    from kageyoni.engine import Engine,require,digest
    from kageyoni.persistence.unit_of_work import _lexical_generation
    from kageyoni.persistence.artifacts import Artifacts
    from kageyoni.workspaces.registry import Registry
    from kageyoni.workspaces.source_authority_history import collect_source_authority_metadata
    require(type(engine) is Engine,'actual native Engine required')
    _lexical_generation(engine.db,unit)
    # Authorization precedes source diagnostics and all controlled metadata.
    workspace=Registry(engine).read(payload['workspace_id'],viewer=payload['viewer'])
    audience=Artifacts._audience(payload['viewer'],payload.get('recipient'))
    occurrences=requested_occurrences(payload)
    resolved=collect_source_authority_metadata(engine)
    inputs=[]
    for occurrence in occurrences:
        cite=occurrence['citation']
        row=engine.db.execute('SELECT '+SOURCE_COLUMNS+' FROM document_sources WHERE workspace_id=? AND source_id=? ORDER BY revision DESC LIMIT 1',(payload['workspace_id'],cite['source_id'])).fetchone()
        require(row is not None,'inquiry source unavailable')
        source=dict(row)
        artifact_row=engine.db.execute('SELECT '+ARTIFACT_COLUMNS+' FROM artifacts WHERE artifact_id=?',(source['artifact_id'],)).fetchone()
        require(artifact_row is not None,'inquiry source artifact unavailable')
        artifact=dict(artifact_row)
        # Same input audience constraints as native _audience_passage/source,
        # before content. Caller authorization remains separate from output.
        require(artifact['workspace_id']==source['workspace_id'] and artifact['viewer'] in (None,audience),'inquiry source audience unavailable')
        if payload['viewer'] is not None:
            require(artifact['viewer']==payload['viewer'],'inquiry caller source unavailable')
        require(source['revision']==cite['revision'] and artifact['digest']==cite['digest'],'inquiry source pin stale')
        controlled=resolved['families'].get((source['workspace_id'],source['source_id']))
        control=None
        if controlled is not None:
            image=controlled['image'];record=controlled['record']
            require(image['branch']==workspace['branch'] and image['phase']=='active' and image['revision']==1 and image['recipient']==audience,'inquiry source control unavailable')
            require(controlled['source']==source and controlled['artifact']==artifact,'inquiry source control correspondence differs')
            control={'id':record['id'],'version':record['version'],'creation_digest':digest(controlled['creation']),'event_id':record['updated_event']}
        inputs.append({'occurrence':deepcopy(occurrence),'source_row':source,'artifact':artifact,'source_pin':{'id':source['source_id'],'version':source['revision'],'digest':artifact['digest']},'artifact_pin':{'id':artifact['artifact_id'],'version':1,'digest':artifact['digest']},'stored_metadata_digest':digest({'profile':PROFILE,'source_row':source}),'control':control})
    return {'profile':PROFILE,'branch':workspace['branch'],'workspace_id':workspace['workspace_id'],'audience':audience,'payload_digest':digest(payload),'inputs':inputs}
