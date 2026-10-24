"""Authored pure correspondence tests; no native creation/authentication."""
from copy import deepcopy
from pathlib import Path
import json,unittest
from source_derivation_facts import *

class Facts(unittest.TestCase):
    def sample(self,legacy=False):
        # Retained actual Native20 metadata, not an invented native fact.
        cases=json.loads((Path(__file__).parent/'parent-cases.json').read_text())
        b=deepcopy(next(c['result']for c in cases if c['case']==('actual-legacy-alias-and-long-ID'if legacy else'actual-active-control-pin')))
        p={'workspace_id':b['workspace_id'],'question':'AUTHORED PURE contract specimen','required_fields':['f'],'claims':[{'field':'f','evidence':deepcopy(i['occurrence']['citation'])}for i in b['inputs']],'counters':[],'viewer':None,'recipient':'visitor'}
        b['payload_digest']=digest(p)
        r={'workspace_id':b['workspace_id'],'question':p['question'],'audience':'visitor','fields':{'f':{'supports':[{'status':'available','citation':deepcopy(c['evidence']),'text':'AUTHOR-SUPPLIED PURE passage; not Native producer output'}for c in p['claims']],'counters':[],'unavailable':[]}},'inquiry_id':'authored:pure-result','phase':'completed'}
        return p,r,b
    def make(self,p,r,b):
        body=canonical(r).encode();out={'artifact_id':'artifact:authored-pure-output','workspace_id':b['workspace_id'],'viewer':'visitor','request_id':output_request_for(branch=b['branch'],workspace_id=b['workspace_id'],controller_principal='synthetic:operator',request_id='synthetic:pure:request',payload_digest=b['payload_digest']),'digest':digest(r),'size':len(body),'media_type':MEDIA_TYPE}
        out['payload_hash']=digest({'workspace_id':b['workspace_id'],'viewer':None,'recipient':'visitor','media_type':MEDIA_TYPE,'digest':out['digest'],'size':out['size']})
        return creation_for(payload=p,result=r,bindings=b,output=out,controller_principal='synthetic:operator',request_id='synthetic:pure:request')
    def bad(self,value,change):
        v=deepcopy(value);change(v)
        with self.assertRaises(ValueError):validate_creation(v)
    def test_01_actual_active_metadata_contract_roundtrip(self):
        p,r,b=self.sample();v=self.make(p,r,b);self.assertEqual(validate_creation(v),v);self.assertEqual(v['bindings']['inputs'][0]['control'],b['inputs'][0]['control'])
    def test_02_all_legacy_alias_occurrences_and_20k_stored_ID(self):
        p,r,b=self.sample(True);v=self.make(p,r,b);self.assertEqual(len(v['result_routes']),4);self.assertEqual([i['source_pin']['id']for i in v['bindings']['inputs'][:3]],['1']*3);self.assertEqual(len(v['bindings']['inputs'][3]['source_pin']['id']),20000)
    def test_03_counter_unavailable_and_duplicate_routes(self):
        p,r,b=self.sample();i=deepcopy(b['inputs'][0]);p['counters']=[deepcopy(p['claims'][0])]*2
        b['inputs']+=[dict(deepcopy(i),occurrence=dict(deepcopy(i['occurrence']),group='counters',index=j))for j in range(2)];b['payload_digest']=digest(p)
        passage=deepcopy(r['fields']['f']['supports'][0]);r['fields']['f']['counters']=[deepcopy(passage)];passage['status']='stale';r['fields']['f']['unavailable']=[passage]
        v=self.make(p,r,b);self.assertEqual([x['group']for x in v['result_routes']],['supports','counters','unavailable'])
    def test_04_dropped_later_counter_refused(self):
        p,r,b=self.sample();p['counters']=[deepcopy(p['claims'][0])];b['payload_digest']=digest(p)
        with self.assertRaises(ValueError):self.make(p,r,b)
    def test_05_input_order_and_path_tampering_refused(self):
        p,r,b=self.sample(True);v=self.make(p,r,b)
        self.bad(v,lambda x:x['bindings']['inputs'].reverse())
        self.bad(v,lambda x:x['bindings']['inputs'][1]['occurrence'].update(index=0))
    def test_06_mutated_raw_metadata_not_normalized(self):
        v=self.make(*self.sample());self.bad(v,lambda x:x['bindings']['inputs'][0]['source_row'].update(metadata_json='{}'))
    def test_07_wrong_workspace_recipient_and_output_digest(self):
        v=self.make(*self.sample())
        for field,new in [('workspace_id','other'),('viewer','keeper'),('digest','0'*64)]:self.bad(v,lambda x,f=field,n=new:x['output'].update({f:n}))
    def test_08_output_reuse_and_body_change_refused(self):
        p,r,b=self.sample();v=self.make(p,r,b);self.bad(v,lambda x:x['output'].update(artifact_id=b['inputs'][0]['artifact']['artifact_id']))
        r['fields']['f']['supports'][0]['text']='different body'
        with self.assertRaises(ValueError):creation_for(payload=p,result=r,bindings=b,output=v['output'],controller_principal=v['controller_principal'],request_id=v['request_id'])
    def test_09_bool_version_and_nonfinite_refused(self):
        v=self.make(*self.sample());self.bad(v,lambda x:x.update(revision=True));self.bad(v,lambda x:x['bindings']['inputs'][0]['source_pin'].update(version=True));self.bad(v,lambda x:x['payload'].update(question=float('inf')))
    def test_10_detached_inputs_outputs(self):
        p,r,b=self.sample();v=self.make(p,r,b);w=validate_creation(v);w['bindings']['inputs'].clear();self.assertEqual(len(v['bindings']['inputs']),1);b['inputs'].clear();self.assertEqual(len(v['bindings']['inputs']),1)
    def test_11_fixed_command_only_creation_no_extra_effect(self):
        v=self.make(*self.sample());c=command_for(v,4);self.assertEqual(validate_command(c),v)
        for mut in [lambda x:x.update(actor='other'),lambda x:x['changes'][0].update(op='patch'),lambda x:x.update(effects=[]),lambda x:x.update(expected_revision=True)]:
            bad=deepcopy(c);mut(bad)
            with self.assertRaises(ValueError):validate_command(bad)
    def test_12_native_record_immutable_wrapper(self):
        v=self.make(*self.sample());c=command_for(v,0);r={k:deepcopy(c['changes'][0][k])for k in ('id','domain','data','status','visibility','audience','evidence')};r.update(branch=v['branch'],version=1,updated_event='synthetic:pure-event');self.assertEqual(validate_record(r),r)
        for mut in [lambda x:x.update(version=2),lambda x:x.update(visibility='public'),lambda x:x.update(audience=[]),lambda x:x['data'].update(body='leak')]:
            bad=deepcopy(r);mut(bad)
            with self.assertRaises(ValueError):validate_record(bad)
    def test_13_no_passage_text_in_history_contract(self):
        p,r,b=self.sample();v=self.make(p,r,b);self.assertNotIn('AUTHOR-SUPPLIED PURE passage',canonical(command_for(v,0)));self.assertEqual(v['result_digest'],digest(r))
    def test_14_output_request_bound_to_whole_operation(self):
        v=self.make(*self.sample());self.bad(v,lambda x:x.update(request_id='other'));self.bad(v,lambda x:x.update(controller_principal='other'))
    def test_15_route_gaps_duplicates_and_wrong_group(self):
        v=self.make(*self.sample());self.bad(v,lambda x:x['result_routes'][0].update(index=1));self.bad(v,lambda x:x['result_routes'][0].update(group='counters'))
    def test_16_subclasses_and_extras_refused(self):
        class S(str):pass
        v=self.make(*self.sample());self.bad(v,lambda x:x.update(profile=S(PROFILE)));self.bad(v,lambda x:x.update(extra=None))

if __name__=='__main__':unittest.main(verbosity=2)
