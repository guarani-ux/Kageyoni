from __future__ import annotations
from collections import defaultdict
from typing import Any, Iterable
from ..engine import digest, require

_OPS={'pressure','assert','gate'}
_OPPOSITES={('increase','decrease'),('decrease','increase'),('activate','suppress'),('suppress','activate')}

def _conditions(effect):
    c=effect.get('conditions',[])
    if c in (None,[]): return []
    if not isinstance(c,list): return None
    # v11 does not silently evaluate invented predicate languages. Conditions remain unresolved.
    return c

class EffectResolver:
    def resolve(self, aspects: Iterable[dict[str,Any]], *, active_aspects:set[str]|None=None):
        aspects=[dict(a) for a in aspects]; contributions=[];claims=[];gates=[];invalid=[];unresolved=[]
        seen=set()
        for aspect in aspects:
            aid=aspect.get('aspect_id','')
            if aid in seen:
                invalid.append({'aspect_id':aid,'reason':'duplicate aspect identity'});continue
            seen.add(aid)
            if active_aspects is not None and aid not in active_aspects:continue
            for index,effect in enumerate(aspect.get('effects',[]) or []):
                if not isinstance(effect,dict):
                    invalid.append({'aspect_id':aid,'effect_index':index,'reason':'effect must be an object'});continue
                op,target=effect.get('operation'),effect.get('target')
                if op not in _OPS or not isinstance(target,str) or not target:
                    invalid.append({'aspect_id':aid,'effect_index':index,'reason':'invalid effect contract'});continue
                cond=_conditions(effect)
                if cond is None:
                    invalid.append({'aspect_id':aid,'effect_index':index,'reason':'invalid effect conditions'});continue
                base={'aspect_id':aid,'target':target,'provenance':aspect.get('provenance',[]),'effect_index':index}
                if cond:
                    unresolved.append({**base,'operation':op,'conditions':cond,'status':'UNRESOLVED','reason':'effect conditions require an explicit evaluator'})
                    continue
                if op=='pressure':
                    direction=effect.get('direction')
                    if direction not in {'increase','decrease','activate','suppress'}:invalid.append({**base,'reason':'invalid pressure direction'});continue
                    contributions.append({**base,'operation':'pressure','direction':direction,'strength':effect.get('strength','unspecified'),'conditions':[]})
                elif op=='assert':claims.append({**base,'operation':'assert','value':effect.get('value'),'status':effect.get('status','proposed')})
                else:
                    disposition,action=effect.get('disposition'),effect.get('action')
                    if disposition not in {'allow','block'} or not action:invalid.append({**base,'reason':'invalid gate effect'});continue
                    gates.append({**base,'operation':'gate','action':action,'disposition':disposition,'reason':effect.get('reason','')})
        by_target=defaultdict(list)
        for c in contributions:by_target[c['target']].append(c)
        conflicts=[]
        for target,items in by_target.items():
            directions={x['direction'] for x in items}
            if any(a in directions and b in directions for a,b in _OPPOSITES):conflicts.append({'target':target,'kind':'opposing_pressures','directions':sorted(directions),'contributors':[x['aspect_id'] for x in items]})
        by_action=defaultdict(list)
        for g in gates:by_action[g['action']].append(g)
        action_state=[]
        for action,items in sorted(by_action.items()):
            dispositions={x['disposition'] for x in items};state='CONFLICTED' if len(dispositions)>1 else ('BLOCKED' if 'block' in dispositions else 'AVAILABLE')
            action_state.append({'action':action,'state':state,'contributors':items})
        from .explanation import validate_explanation_graph
        explanation_edges=[]
        for aspect in aspects:
            if active_aspects is None or aspect.get('aspect_id') in active_aspects:explanation_edges.extend(aspect.get('explanation_edges',[]) or [])
        explanation=validate_explanation_graph(explanation_edges)
        if not explanation['valid']:invalid.append({'reason':'invalid explanation graph','details':explanation})
        result={'contributions':contributions,'conflicts':conflicts,'claims':claims,'action_gates':action_state,'unresolved_effects':unresolved,'invalid_effects':invalid,'explanation':explanation}
        result['valid']=not invalid and not unresolved;result['digest']=digest(result);return result

class ExpressionContract:
    def build(self,compilation,resolution):
        require(isinstance(compilation,dict) and isinstance(resolution,dict),'compilation and resolution required')
        must=[]
        for slot in compilation.get('slots',[]):
            if slot.get('status') not in {'FILLED','DERIVED','INFERRED','NOT_APPLICABLE'}:must.append({'slot_id':slot.get('slot_id'),'status':slot.get('status'),'reason':slot.get('reason','')})
        return {'runnable':bool(compilation.get('runnable')) and bool(resolution.get('valid')),'must_preserve':must,'pressures':[{k:v for k,v in c.items() if k in {'target','direction','strength','aspect_id'}} for c in resolution.get('contributions',[])],'conflicts':resolution.get('conflicts',[]),'actions':resolution.get('action_gates',[]),'claims':resolution.get('claims',[]),'unresolved_effects':resolution.get('unresolved_effects',[]),'creative_freedom':'Host may choose language, performance, imagery, pacing, and non-canonical detail so long as it does not contradict preserved state or invent unsupported canonical facts.'}

class ExpressionVerifier:
    def verify(self,compilation,declared_claims):
        if compilation.get('runnable') is False:
            return {'passed':False,'claims':[{'status':'UNSUPPORTED','reason':'non-runnable compilation cannot qualify canonical claims'}],'scope':'declared claims only'}
        if 'admitted_aspect_ids' in compilation:
            available=set(compilation.get('admitted_aspect_ids') or [])
        else:
            available=set()
            for slot in compilation.get('slots',[]):
                if slot.get('status') in {'FILLED','DERIVED','INFERRED'}: available.update(slot.get('aspect_ids',[]) or [])
        results=[]
        for i,claim in enumerate(declared_claims or []):
            kind=claim.get('kind');refs=claim.get('evidence_refs',[]) or []
            if kind not in {'canonical','interpretive','expressive'}:results.append({'index':i,'status':'INVALID','reason':'unknown claim kind'});continue
            if kind=='canonical':
                missing=[r for r in refs if r not in available]
                if not refs:results.append({'index':i,'status':'UNSUPPORTED','reason':'canonical claim requires evidence_refs'});continue
                if missing:results.append({'index':i,'status':'UNSUPPORTED','reason':f'evidence refs not in admitted compiled state: {missing}'});continue
            results.append({'index':i,'status':'SUPPORTED' if kind=='canonical' else 'OPEN','kind':kind})
        return {'passed':all(x['status'] not in {'INVALID','UNSUPPORTED'} for x in results),'claims':results,'scope':'verifies declared claims against admitted runnable evidence only; does not certify prose completeness or semantic entailment, which remains a qualified host judgment'}
