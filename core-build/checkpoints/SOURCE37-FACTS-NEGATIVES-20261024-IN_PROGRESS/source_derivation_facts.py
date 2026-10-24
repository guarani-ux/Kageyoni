"""Immutable inquiry creation correspondence, not installed authority.

Pure data/command validation. Passing this contract does NOT authenticate the
producer, insert an event, authorize a read, or establish current permission.
No result passage text is copied into record/history metadata. The full result
belongs in a separately guarded artifact, bound here by its complete digest.
"""
from copy import deepcopy
import hashlib
import json
from source_derivation_inputs import primitive,requested_occurrences,inquiry_occurrences,citation

PROFILE='samsara-source-derivation/20261024-1'
INPUT_PROFILE='samsara-source-derivation-inputs/20261024-1'
DOMAIN='source_derivation'
PREFIX='source-derivation:'
OP_PREFIX='source-derivation-operation:'
PRODUCER={'name':'Documents.inquire','version':'1'}
MEDIA_TYPE='application/json; charset=utf-8'
EVIDENCE=[{'source_derivation_profile':PROFILE,'note':'Fixed native inquiry creation; current selected-world custody only.'}]
SOURCE_KEYS={'workspace_id','source_id','revision','request_id','payload_hash','artifact_id','metadata_json'}
ARTIFACT_KEYS={'artifact_id','workspace_id','viewer','request_id','payload_hash','digest','media_type','size'}
INPUT_KEYS={'occurrence','source_row','artifact','source_pin','artifact_pin','stored_metadata_digest','control'}
CREATION_KEYS={'profile','producer','branch','workspace_id','controller_principal','recipient','request_id','payload','bindings','result_digest','result_routes','output','revision'}

class DerivationError(ValueError):pass
def require(ok,message):
    if not ok:raise DerivationError(message)
def canonical(value):
    try:
        primitive(value)
        return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,OverflowError,RecursionError)as e:
        raise DerivationError('exact finite derivation JSON required')from e
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def keys(value,names,label):
    require(type(value)is dict and set(value)==names,label+' exact fields required')
def text(value,label,limit=20000):
    # Actual legacy source IDs are stored strings, not the new controller IDs.
    require(type(value)is str and 0<len(value.strip())<=limit,label+' stored string required')
def identity(value,label):
    from kageyoni.workspaces.source_authority_schema import _identifier
    try:_identifier(value,label)
    except ValueError as e:raise DerivationError(label+' controlled identity required')from e
def hash_value(value):
    require(type(value)is str and len(value)==64 and all(c in '0123456789abcdef'for c in value),'64 lowercase hex digest required')
def integer(value,minimum=1,maximum=2**53-1):
    require(type(value)is int and minimum<=value<=maximum,'exact bounded integer required')
def pin(value,identifier,version,body_digest):
    keys(value,{'id','version','digest'},'pin');integer(value['version']);hash_value(value['digest'])
    require(value['id']==identifier and type(value['id'])is str and value['version']==version and value['digest']==body_digest,'pin correspondence differs')

def validate_bindings(payload,bindings):
    canonical(payload);canonical(bindings)
    occurrences=requested_occurrences(payload)
    keys(bindings,{'profile','branch','workspace_id','audience','payload_digest','inputs'},'bindings')
    identity(bindings['branch'],'branch');identity(bindings['workspace_id'],'workspace');identity(bindings['audience'],'recipient')
    require(bindings['profile']==INPUT_PROFILE and bindings['workspace_id']==payload['workspace_id'] and bindings['payload_digest']==digest(payload),'binding payload identity differs')
    require(payload.get('recipient',payload['viewer'])==bindings['audience'],'binding output audience differs')
    require(payload['viewer']is None or payload['viewer']==bindings['audience'],'input caller/output audience differs')
    items=bindings['inputs'];require(type(items)is list and len(items)==len(occurrences),'complete occurrence inventory required')
    for occurrence,item in zip(occurrences,items):
        keys(item,INPUT_KEYS,'input binding')
        require(canonical(item['occurrence'])==canonical(occurrence),'ordered occurrence correspondence differs')
        source=item['source_row'];artifact=item['artifact'];cite=occurrence['citation']
        keys(source,SOURCE_KEYS,'source row');keys(artifact,ARTIFACT_KEYS,'artifact row')
        for key in ('workspace_id','source_id','request_id','artifact_id'):text(source[key],key)
        integer(source['revision']);hash_value(source['payload_hash']);require(type(source['metadata_json'])is str,'raw stored metadata TEXT required')
        from kageyoni.workspaces.source_authority_installation import strict_json
        require(type(strict_json(source['metadata_json']))is dict,'stored metadata object required')
        for key in ('artifact_id','workspace_id','request_id','media_type'):text(artifact[key],key)
        integer(artifact['size'],0,10000000);hash_value(artifact['digest']);hash_value(artifact['payload_hash'])
        require(source['workspace_id']==bindings['workspace_id']==artifact['workspace_id'] and source['artifact_id']==artifact['artifact_id'] and source['revision']==cite['revision'] and artifact['digest']==cite['digest'],'stored input scope/pin differs')
        # Selector aliases were resolved by trusted SQLite metadata binding.
        # Do not compare or coerce original int/bool selectors to stored IDs.
        require(artifact['viewer']in(None,bindings['audience']) and (payload['viewer']is None or artifact['viewer']==payload['viewer']),'stored artifact audience differs')
        pin(item['source_pin'],source['source_id'],source['revision'],artifact['digest']);pin(item['artifact_pin'],artifact['artifact_id'],1,artifact['digest'])
        require(item['stored_metadata_digest']==digest({'profile':INPUT_PROFILE,'source_row':source}),'raw stored metadata digest differs')
        control=item['control']
        if control is not None:
            keys(control,{'id','version','creation_digest','event_id'},'control creation pin')
            from kageyoni.workspaces.source_authority_schema import authority_id
            require(control['id']==authority_id(source['workspace_id'],source['source_id']),'control family identity differs')
            integer(control['version'],1,1);hash_value(control['creation_digest']);identity(control['event_id'],'control event')
            require(artifact['viewer']==bindings['audience'],'controlled input recipient differs')
    return deepcopy(bindings)

def result_routes(payload,result):
    occurrences=inquiry_occurrences(payload,result)
    remaining=set(range(len(occurrences)));out=[]
    for field in payload['required_fields']:
        for group in ('supports','counters','unavailable'):
            for position,passage in enumerate(result['fields'][field][group]):
                selected=next((i for i in sorted(remaining)if occurrences[i]['field']==field and citation(occurrences[i]['citation'])==citation(passage['citation']) and (group=='unavailable'or occurrences[i]['group']==('claims'if group=='supports'else'counters'))),None)
                require(selected is not None,'result occurrence has no input')
                remaining.remove(selected);out.append({'input_index':selected,'field':field,'group':group,'index':position})
    require(not remaining,'result did not account for every input')
    return sorted(out,key=lambda r:r['input_index'])

def output_request_for(*,branch,workspace_id,controller_principal,request_id,payload_digest):
    for value in (branch,workspace_id,controller_principal,request_id):identity(value,'output request scope')
    hash_value(payload_digest)
    return 'source-derivation-output:'+digest([PROFILE,branch,workspace_id,controller_principal,request_id,payload_digest])

def validate_creation(value):
    canonical(value);keys(value,CREATION_KEYS,'immutable creation')
    require(value['profile']==PROFILE and canonical(value['producer'])==canonical(PRODUCER),'fixed native producer/profile required')
    for key in ('branch','workspace_id','controller_principal','recipient','request_id'):identity(value[key],key)
    integer(value['revision'],1,1)
    bound=validate_bindings(value['payload'],value['bindings'])
    require(value['branch']==bound['branch']and value['workspace_id']==bound['workspace_id']and value['recipient']==bound['audience'],'creation input scope differs')
    hash_value(value['result_digest']);output=value['output'];keys(output,ARTIFACT_KEYS,'output artifact metadata')
    for key in ('artifact_id','request_id'):identity(output[key],key)
    require(output['request_id']==output_request_for(branch=value['branch'],workspace_id=value['workspace_id'],controller_principal=value['controller_principal'],request_id=value['request_id'],payload_digest=bound['payload_digest']),'output native producer request differs')
    integer(output['size'],1,10000000);hash_value(output['payload_hash']);hash_value(output['digest'])
    require(output['workspace_id']==value['workspace_id']and output['viewer']==value['recipient']and output['media_type']==MEDIA_TYPE and output['digest']==value['result_digest'],'output artifact scope/digest differs')
    require(all(output['artifact_id']!=r['artifact']['artifact_id']for r in bound['inputs']),'output must have a new artifact identity')
    # The fixed producer uses owner authorization and explicit private recipient.
    require(output['payload_hash']==digest({'workspace_id':value['workspace_id'],'viewer':None,'recipient':value['recipient'],'media_type':MEDIA_TYPE,'digest':output['digest'],'size':output['size']}),'output artifact creation payload differs')
    routes=value['result_routes'];require(type(routes)is list and len(routes)==len(bound['inputs']),'complete result routes required')
    seen=set();positions=set()
    for i,route in enumerate(routes):
        keys(route,{'input_index','field','group','index'},'result route');integer(route['input_index'],0);integer(route['index'],0)
        require(route['input_index']==i and route['field']==bound['inputs'][i]['occurrence']['field']and route['group']in('supports','counters','unavailable'),'ordered result route differs')
        expected='supports'if bound['inputs'][i]['occurrence']['group']=='claims'else'counters'
        require(route['group']in(expected,'unavailable'),'result route group differs')
        place=(route['field'],route['group'],route['index']);require(place not in positions,'duplicate output occurrence position');positions.add(place);seen.add(i)
    for field in value['payload']['required_fields']:
        for group in ('supports','counters','unavailable'):
            indices=sorted(position for f,g,position in positions if f==field and g==group)
            require(indices==list(range(len(indices))),'result route positions are not contiguous')
    return deepcopy(value)

def creation_for(*,payload,result,bindings,output,controller_principal,request_id):
    """Build correspondence from producer data; caller data is NOT authority."""
    require(result.get('audience')==bindings['audience'],'complete result audience differs')
    body=canonical(result).encode()
    require(len(body)==output['size']and hashlib.sha256(body).hexdigest()==output['digest'],'complete result body differs from actual output metadata')
    return validate_creation({'profile':PROFILE,'producer':deepcopy(PRODUCER),'branch':bindings['branch'],'workspace_id':bindings['workspace_id'],'controller_principal':controller_principal,'recipient':bindings['audience'],'request_id':request_id,'payload':deepcopy(payload),'bindings':deepcopy(bindings),'result_digest':digest(result),'result_routes':result_routes(payload,result),'output':deepcopy(output),'revision':1})

def derivation_id(creation):
    v=validate_creation(creation)
    return PREFIX+digest([PROFILE,v['branch'],v['workspace_id'],v['output']['artifact_id']])

def command_for(creation,expected_revision):
    v=validate_creation(creation);integer(expected_revision,0)
    return {'api_version':3,'branch':v['branch'],'expected_revision':expected_revision,'request_id':OP_PREFIX+digest(v),'actor':v['controller_principal'],'kind':'maintenance','narrative':'Fixed inquiry derivation creation; current selected-world custody only.','changes':[{'op':'create','id':derivation_id(v),'domain':DOMAIN,'expected_version':0,'data':{'contract':v},'status':'confirmed','visibility':'restricted','audience':[v['recipient']],'evidence':deepcopy(EVIDENCE)}],'causes':[],'judgment':{'source_derivation_creation':v}}

def validate_command(value):
    canonical(value);require(type(value)is dict and type(value.get('judgment'))is dict and set(value['judgment'])=={'source_derivation_creation'},'fixed derivation judgment required')
    v=validate_creation(value['judgment']['source_derivation_creation'])
    require(canonical(value)==canonical(command_for(v,value.get('expected_revision'))),'fixed derivation command differs')
    return v

def validate_record(value):
    canonical(value);keys(value,{'branch','id','domain','version','status','visibility','audience','evidence','data','updated_event'},'native derivation record')
    keys(value['data'],{'contract'},'native derivation data');v=validate_creation(value['data']['contract'])
    integer(value['version'],1,1);identity(value['updated_event'],'updated event')
    require(value['branch']==v['branch']and value['id']==derivation_id(v)and value['domain']==DOMAIN and value['status']=='confirmed'and value['visibility']=='restricted'and canonical(value['audience'])==canonical([v['recipient']])and canonical(value['evidence'])==canonical(EVIDENCE),'immutable derivation native wrapper differs')
    return deepcopy(value)
