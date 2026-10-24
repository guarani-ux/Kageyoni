"""Pure diagnostic routing, NEVER authentication/history/permission evidence.

Only a complete fixed derivation record or command may carry typed input
witnesses. A raw creation, nested arbitrary dictionary or malformed envelope
does not gain this interpretation. Full derivation metadata/current guards
remain mandatory; this module calls no collector, preventing recursive scans.
"""
from copy import deepcopy

def _record_view(value):
    from .source_derivation_facts import DOMAIN, validate_record
    if type(value)is not dict or value.get('domain')!=DOMAIN:return value
    try:validate_record(value)
    except (ValueError,TypeError,KeyError,RecursionError):return value
    result=deepcopy(value)
    # These are operational source/artifact/control witnesses, not definitions
    # of direct source-authority records. Keep every other field visible.
    result['data']['contract']['bindings']={}
    return result

def direct_scan_view(value):
    from .source_derivation_facts import validate_command
    if type(value)is dict:
        if type(value.get('judgment'))is dict and 'source_derivation_creation'in value['judgment']:
            try:validate_command(value)
            except (ValueError,TypeError,KeyError,RecursionError):return value
            result=deepcopy(value)
            result['judgment']['source_derivation_creation']['bindings']={}
            result['changes'][0]['data']['contract']['bindings']={}
            return result
        if type(value.get('records'))is list:
            result=deepcopy(value);result['records']=[_record_view(r)for r in value['records']];return result
        return _record_view(value)
    if type(value)is list:return [_record_view(r)for r in value]
    return value

def projection_view(db,row):
    """Validate the complete actual row wrapper before routing its contract."""
    from .source_derivation_facts import DOMAIN
    if row['domain']!=DOMAIN:return None
    raw=db.execute('SELECT * FROM records WHERE branch=? AND id=?',(row['branch'],row['id'])).fetchone()
    projection=db.execute('SELECT contract FROM source_derivation WHERE branch=? AND id=?',(row['branch'],row['id'])).fetchone()
    from .source_authority_installation import strict_json
    from .source_derivation_facts import require,validate_record
    require(raw is not None and projection is not None,'derivation projection/wrapper missing')
    record=dict(raw);record['audience']=strict_json(record.pop('audience_json'));record['evidence']=strict_json(record.pop('evidence_json'));record['data']={'contract':strict_json(projection[0])}
    validate_record(record)
    return _record_view(record)
