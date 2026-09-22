import json, unittest
from copy import deepcopy
from pathlib import Path
from kageyoni.composition.compiler import Compiler
from kageyoni.composition.explanation import validate_explanation_graph
from kageyoni.composition.effects import EffectResolver
DATA=Path(__file__).resolve().parents[2]/'kageyoni'/'composition'/'data'

class FoundryKernelAttack(unittest.TestCase):
  def frame(self): return json.loads((DATA/'narrative_scene.json').read_text())
  def fixture(self):
    f=self.frame();a=[];b={}
    for s in f['slots']:
      if s['requirement']!='required': continue
      aid='x:'+s['slot_id']; item={'aspect_id':aid,'type':s['accepts'][0],'family':s['family'],'authority':s['authority_policy'][0],'compatible_slots':[s['slot_id']],'properties':{},'provenance':[{'kind':'test','ref':aid}]}
      a.append(item);b[s['slot_id']]=[aid]
    for z in a:
      if z['aspect_id'].endswith('governing.context'): z['semantic_key']=z['aspect_id']
      if z.get('type') in {'orientation','capability','trait','knowledge_state','internal_pressure'}: z['lineage']={'entity_id':'fixture-actor'}
      if z['aspect_id'].endswith('scene.participants'): z.setdefault('properties',{})['record_id']='fixture-actor'
    return f,a,b
  def test_F03_branch_and_effective_time_are_not_collapsed(self):
    f,a,b=self.fixture(); x=next(z for z in a if z['aspect_id']=='x:scene.situation');x['scope']={'branch':'fork'}
    r=Compiler(f,a).compile(b,context={'branch':'main','revision':10});self.assertFalse(r['runnable']);self.assertTrue(any('branch' in z['reason'] for z in r['input_issues']))
    x['scope']={'branch':'main'};x['temporal']={'effective_from_revision':11}
    r=Compiler(f,a).compile(b,context={'branch':'main','revision':10});self.assertFalse(r['runnable']);self.assertTrue(any(z['status']=='STALE' for z in r['input_issues']))
  def test_F04_identity_bound_aspect_from_other_entity_is_counterfeit(self):
    f,a,b=self.fixture(); p=next(z for z in a if z['aspect_id']=='x:scene.participants');p['properties']['record_id']='sciel'
    c=next(z for z in a if z['aspect_id']=='x:actor.configuration');c['lineage']={'entity_id':'other-sciel'}
    r=Compiler(f,a).compile(b);self.assertFalse(r['runnable']);self.assertTrue(any('semantic counterfeit' in z['reason'] for z in r['input_issues']))
  def test_F05_semantic_duplicate_causal_influence_is_rejected(self):
    f,a,b=self.fixture(); base=next(z for z in a if z['aspect_id']=='x:governing.context');base['semantic_key']='twilight'
    dup=deepcopy(base);dup['aspect_id']='twilight:alias';a.append(dup);b['governing.context'].append(dup['aspect_id'])
    r=Compiler(f,a).compile(b);self.assertFalse(r['runnable']);self.assertTrue(any('duplicate semantic influence' in z['reason'] for z in r['input_issues']))
  def test_F06_direct_population_budget_fails_closed(self):
    f,a,b=self.fixture(); proto=next(z for z in a if z['aspect_id']=='x:scene.participants');b['scene.participants']=[]
    for i in range(33):
      z=deepcopy(proto);z['aspect_id']=f'actor:{i}';z['properties']['record_id']=f'actor:{i}';a.append(z);b['scene.participants'].append(z['aspect_id'])
    # relationship is supplied, so budget rather than relationship absence must still block.
    rel={'aspect_id':'rels','type':'relationship_state','family':'relational','authority':'mechanical','compatible_slots':['actor.relationships'],'properties':{},'provenance':[{'kind':'test','ref':'rels'}]};a.append(rel);b['actor.relationships']=['rels']
    r=Compiler(f,a).compile(b);self.assertFalse(r['runnable']);self.assertTrue(any('resolution budget exceeded' in z['reason'] for z in r['input_issues']))
  def test_F11_causal_cycles_fail_but_context_cycles_do_not(self):
    bad=validate_explanation_graph([{'source':'a','target':'b','kind':'causes'},{'source':'b','target':'a','kind':'supports'}]);self.assertFalse(bad['valid']);self.assertTrue(bad['causal_cycle'])
    good=validate_explanation_graph([{'source':'a','target':'b','kind':'context'},{'source':'b','target':'a','kind':'references'}]);self.assertTrue(good['valid'])
    r=EffectResolver().resolve([{'aspect_id':'x','effects':[],'explanation_edges':[{'source':'a','target':'b','kind':'causes'},{'source':'b','target':'a','kind':'causes'}]}]);self.assertTrue(r['invalid_effects'])
  def test_F01_history_can_become_causally_required(self):
    f,a,b=self.fixture();p=next(z for z in a if z['aspect_id']=='x:scene.participants');p['properties']['requires_history']=True
    r=Compiler(f,a).compile(b);self.assertFalse(r['runnable']);h=next(z for z in r['slots'] if z['slot_id']=='scene.relevant_history');self.assertEqual(h['status'],'UNKNOWN')

class FoundryCompositionPolicyAttack(unittest.TestCase):
  def test_F06_aggregate_population_does_not_consume_direct_actor_budget(self):
    f=json.loads((DATA/'narrative_scene.json').read_text());aspects=[];bindings={}
    for s in f['slots']:
      if s['requirement']!='required': continue
      aid='z:'+s['slot_id'];x={'aspect_id':aid,'type':s['accepts'][0],'family':s['family'],'authority':s['authority_policy'][0],'compatible_slots':[s['slot_id']],'properties':{},'provenance':[{'kind':'test','ref':aid}]}
      if s.get('semantic_identity_required'):x['semantic_key']=aid
      if s.get('lineage_required'):x['lineage']={'entity_id':'actor:one'}
      if s['slot_id']=='scene.participants':x['properties']['record_id']='actor:one'
      aspects.append(x);bindings[s['slot_id']]=[aid]
    crowd={'aspect_id':'crowd:8000','type':'population_cohort','family':'entity','authority':'derived','compatible_slots':['scene.population'],'properties':{'estimated_count':8000},'provenance':[{'kind':'aggregation','ref':'festival-census'}]}
    aspects.append(crowd);bindings['scene.population']=['crowd:8000']
    self.assertTrue(Compiler(f,aspects).compile(bindings)['runnable'])
  def test_F09_descriptive_audience_slot_rejects_baked_action_gate(self):
    f=json.loads((DATA/'content_development.json').read_text());
    demographic={'aspect_id':'demo:genz','type':'demographic','family':'configuration','authority':'evidence','compatible_slots':['audience.attributes'],'provenance':[{'kind':'research','ref':'r1'}],'effects':[{'operation':'gate','action':'use_fast_cuts','disposition':'allow'}]}
    # We only need the target slot result to establish the policy; other missing slots may also block.
    r=Compiler(f,[demographic]).compile({'audience.attributes':['demo:genz']})
    slot=next(x for x in r['slots'] if x['slot_id']=='audience.attributes');self.assertEqual(slot['status'],'INVALID');self.assertIn('effect policy',slot['violations'][0]['reason'])

class FoundryBypassAttack(unittest.TestCase):
 def test_effect_bearing_aspect_cannot_omit_semantic_identity(self):
  f=json.loads((DATA/'content_development.json').read_text())
  a={'aspect_id':'interest:x','type':'interest','family':'configuration','authority':'evidence','compatible_slots':['audience.attributes'],'provenance':[{'kind':'evidence','ref':'r'}],'effects':[{'operation':'pressure','target':'attention.depth','direction':'increase'}]}
  r=Compiler(f,[a]).compile({'audience.attributes':['interest:x']});slot=next(x for x in r['input_issues'] if 'semantic_key' in x['reason']);self.assertEqual(slot['status'],'INVALID')
 def test_world_scope_mismatch_is_counterfeit(self):
  f=json.loads((DATA/'content_development.json').read_text())
  a={'aspect_id':'idea:x','type':'idea','family':'entity','authority':'owner','compatible_slots':['content.idea'],'provenance':[{'kind':'owner','ref':'x'}],'scope':{'world_id':'fork-B'}}
  r=Compiler(f,[a]).compile({'content.idea':['idea:x']},context={'world_id':'main-world'});self.assertTrue(any('world' in x['reason'] for x in r['input_issues']))
