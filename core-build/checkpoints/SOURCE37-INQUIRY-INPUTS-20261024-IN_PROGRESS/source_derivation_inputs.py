"""Pure citation closure for the actual Documents.inquire producer.

No authentication, native history, permission decision or body fetch. Returned
occurrences must later bind to actual stored source/artifact/control identities
inside the producer's UoW; matching JSON alone cannot establish those facts.
"""
from collections import Counter
from copy import deepcopy
import json
import math

class DerivationInputError(ValueError):
    pass

def require(value, message):
    if not value:
        raise DerivationInputError(message)

def primitive(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        require(math.isfinite(value), 'nonfinite JSON number')
        return
    if type(value) is list:
        for item in value:
            primitive(item)
        return
    if type(value) is dict:
        require(all(type(key) is str for key in value), 'JSON string keys required')
        for item in value.values():
            primitive(item)
        return
    raise DerivationInputError('exact JSON primitives required')

def citation(value):
    require(type(value) is dict and set(value) == {'source_id','revision','digest','start','end'}, 'exact citation required')
    # Preserve the caller value until a trusted stored-row resolver supplies
    # canonical family identity. SQLite aliases are not resolved by this leaf.
    require(value['source_id'] is None or type(value['source_id']) in (str,int,bool,float), 'JSON source selector required')
    require(type(value['revision']) is int and value['revision'] > 0, 'positive source revision required')
    digest=value['digest']
    require(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest), 'source digest required')
    require(type(value['start']) is int and type(value['end']) is int and 0 <= value['start'] < value['end'], 'citation span required')
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def inquiry_occurrences(payload, result):
    """Account for every producer citation occurrence, without deduplication.

    payload is exactly the native inquiry payload formed before cache lookup;
    result is the complete returned native result. Validation covers citation
    closure, not passage text, full result semantics or authenticity. In a
    historical cached result, closure does not establish current permission.
    """
    primitive(payload);primitive(result)
    require(type(payload) is dict and {'workspace_id','question','required_fields','claims','counters','viewer'} <= set(payload) <= {'workspace_id','question','required_fields','claims','counters','viewer','recipient'}, 'native inquiry payload required')
    require(type(payload['workspace_id']) is str and payload['workspace_id'] and type(payload['question']) is str and payload['question'], 'native workspace and question strings required')
    fields=payload['required_fields']
    require(type(fields) is list and 1 <= len(fields) <= 64 and all(type(f) is str and f for f in fields) and len(set(fields))==len(fields), 'distinct required fields required')
    require(type(payload['claims']) is list and type(payload['counters']) is list and len(payload['claims'])+len(payload['counters'])<=256, 'bounded claim lists required')
    require(type(result) is dict and result.get('workspace_id')==payload['workspace_id'] and result.get('question')==payload['question'], 'producer identity differs')
    actual_fields=result.get('fields')
    require(type(actual_fields) is dict and set(actual_fields)==set(fields), 'result field set differs')
    expected={f:{'supports':Counter(),'counters':Counter()} for f in fields}
    occurrences=[]
    for request_group,result_group in (('claims','supports'),('counters','counters')):
        for index,item in enumerate(payload[request_group]):
            require(type(item) is dict and set(item)=={'field','evidence'} and type(item['field']) is str and item['field'] in expected, 'field mapping required')
            key=citation(item['evidence']);expected[item['field']][result_group][key]+=1
            occurrences.append({'group':request_group,'index':index,'field':item['field'],'citation':deepcopy(item['evidence'])})
    for field in fields:
        row=actual_fields[field]
        require(type(row) is dict and set(row)=={'supports','counters','unavailable'}, 'exact result groups required')
        counts={name:Counter() for name in row}
        for group,passages in row.items():
            require(type(passages) is list,'passage list required')
            for passage in passages:
                require(type(passage) is dict,'passage required')
                status=passage.get('status')
                require(status=='available' if group!='unavailable' else status in ('stale','identity_mismatch'), 'passage availability group differs')
                counts[group][citation(passage.get('citation'))]+=1
        support, counter=expected[field]['supports'],expected[field]['counters']
        require(not (counts['supports']-support) and not (counts['counters']-counter), 'invented or wrong-group available citation')
        require((support-counts['supports'])+(counter-counts['counters'])==counts['unavailable'], 'missing or extra citation occurrence')
    return occurrences
