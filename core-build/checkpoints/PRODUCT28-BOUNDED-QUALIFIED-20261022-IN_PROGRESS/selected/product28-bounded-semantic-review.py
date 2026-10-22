"""Root semantic receipt for the actual bounded fix, not full release."""
import hashlib,json,os
from pathlib import Path
R=Path('/workspace/scratch/5c7ed9200168/recovery-20261022')
def read(p):return json.loads((R/p).read_text())
mixed=read('product28-genuine-affected-r1/evidence/test-results.json')
post=read('product28-genuine-affected-r1/readonly-postconditions.json')
six=read('product28-genuine-affected-r1/genuine-six-returns.json')
received=read('product28-receiving-r1/fresh-receiving/result.json')
relocated=read('product28-receiving-r1/fresh-receiving/physical-relocation.json')
prior=read('product28-affected-r1/summary.json')
assert [s['passed_calls'] for s in mixed['statuses']]==[2,18,7]
assert all(s['exitstatus']==0 for s in mixed['statuses'])
assert len(post['worlds'])==27 and all(w['valid'] and w['all_world_bytes_unchanged'] and w['total_changes']==0 and not w['FK'] for w in post['worlds'])
assert mixed['all_238_payloads_unchanged'] and mixed['all_32_test_sources_unchanged']
assert not mixed['transport_unknown'] and all(x['closed'] for x in mixed['owners']+mixed['clients'])
assert received['payloads']==238 and received['source_original_unchanged']
assert received['output_bytes']==553 and received['new_quiet']['state']=='finished'
assert relocated['old_private_absent'] and relocated['all_bytes_equal']
assert prior['mandatory_predicates']=={'passed':2,'failed':1,'not_run':17}
receipt={
 'status':'QUALIFIED_BOUNDED_UNFED_EOF_EXIT_FIX_ONLY',
 'candidate':{'product':'0.5.3.dev28','engine':'11.1.0.dev16','runtime':'1289b896d6de9194f286a0e9860e20ff65337b78a3efb536bae981cd90ebc858','product_wheel':'7360f0b41ed2691abab83bbfaf245eb61215b09f8c4a39fe3ce8a857efff4d4b','native_wheel':'845d7b4aaa3b81c66364eed09d34e91b57e5c0f99df6aaa654b470d4a1db4ff3','payloads':238},
 'changed_behavior':'An unfed owned child whose native registration fails receives EOF and at most100ms actual natural-exit observation. No signal/first-stop reset; timeout retains local charge.',
 'actual_evidence':{'original_failed_registration_now_passes':'Actual owned wait/poll21, initial stopped28run observation~1.2ms, final actual child reaped; original assertion unchanged.',
 'pure_adverse_cases':5,'mixed_actual_predicates':[2,18,7],'genuine_fixture_workers':6,'actual_worker_exit_codes':[0,0,0,0,0,0],
 'original_assertions_AST_preserved':[7,4],'all_closed_worlds_native_RO_valid_unchanged':27,
 'fresh_operator_receiving':'553B actual returned component exact before/after reopen; physical copied-world relocation oldprivatepath absent; actual new native rest accepted/reopened; checkedbackup; source unchanged.',
 'selected_real_owner_loss':'Unchanged original owner-kill/discard/newgeneration/returned-output predicate actually passed on28; no historical numeric exit fabricated.'},
 'raw_failures_preserved':['Product27 original failed-registration pollNone, no demonstrated predecessor guarantee removed.','Product28 original fake-return fairness assertion FAIL; native rejected unregistered claim→returned. No guard weakened.','Earlier native journal/copied SQLite recovery and product27overlay postrun integrity failures unresolved.','Initial fresh28env missingjsonschema before anyworld; offline dependency setup repaired.'],
 'fixture_decision':'Two invalid pure-queue completion fixture steps were replaced in EXPLICIT new counterparts by genuine registered process return. All7+4 original assert ASTs retained; original files/failure unchanged. Not a clean original20suite.',
 'observation_limits':['Mixed-run per-line trace filter was shadowed;0source-frame events. Actual1246API/wire/Popen/lifecycle/postimageevents, JUnit and unchanged source retained; no reconstructed trace.','Single current host/trusted built-in worker lane.100ms is a maximum observation wait, not guaranteed OS scheduling.','No wholeD15b/fullproduct/generalhost/model/unknownworker/human/fullmatrix/compatibility/fullF1-F5 qualification.','New media26 results stay exact26/native15 history; not silently transferred to28.','Historical unknown-absence RECOVER and both new custody transaction SIGKILL seams still require actual execution.'],
 'next':'Root review source-only custody control helper; actual recover/unacceptedbytes/dual interruption/recipient/recovery on matching28. Review/integrate independentF3a native source without treating source/API as world.',
 'full_release_qualified':False}
files=['product28-genuine-affected-r1/evidence/test-results.json','product28-genuine-affected-r1/readonly-postconditions.json','product28-genuine-affected-r1/genuine-six-returns.json','product28-receiving-r1/fresh-receiving/result.json','product28-receiving-r1/fresh-receiving/physical-relocation.json','product28-affected-r1/summary.json','product28-actual-queue-fixture/root-assertion-review.json','product27-failed-registration-diagnosis/diagnosis-and-28-review.md','product28-build/unfed-pure.log']
receipt['evidence_sha256']={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
dest=R/'product28-bounded-semantic-receipt.json';assert not dest.exists();dest.write_text(json.dumps(receipt,indent=2)+'\n')
p=R/'BUILD_STATUS.json';before=p.read_bytes();d=json.loads(before)
old=R/'BUILD_STATUS-before-product28-bounded.json';assert not old.exists();old.write_bytes(before)
protected=('core_loops','old_requirements','old_slices','increments','full_release_increments','full_release_breadth','load_scenarios','resource_policy');scope={k:d[k] for k in protected}
d['full_release_continuation']['stages']['D15b-E0']={'status':receipt['status'],'receipt':dest.name,'receipt_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'scope':receipt['changed_behavior'],'full_release_qualified':False}
d['current_unfinished_work']['status']='IN_PROGRESS_BOUNDED_EOF_FIX_QUALIFIED_CUSTODY_RECOVER_INTERRUPTION_PENDING'
d['current_unfinished_work']['next']=receipt['next']
d['current_unqualified_checkpoint']['bounded_fix_qualification']=dest.name
d['latest_candidate_status']='CURRENT28_BOUNDED_EOF_FIX_QUALIFIED; MIXED27PASS_AND_FRESH_RELOCATION_RECEIVING; WHOLE_D15b_AND_F1-F5_IN_PROGRESS'
d['current_recovery_checkpoint']['selected_product28_new_results']={'receipt':dest.name,'mixed_predicates':[2,18,7],'closed_worlds':27,'fresh_output_bytes':553,'physical_relocation_old_private_absent':True,'old_failures_unresolved':True,'new_raw_custody':'PENDING_NEXT_CAPTURE','active_DB_process_jobs':'NONE at root receipt; control author source-only, F3a author source-only; writer old28/R3raw active.'}
d['current_recovery_checkpoint']['active_or_uncertain_operations']=['Current28 genuine mixed suite and fresh receiving/nativecontinuation closed; no unknown new effects.','Solewriterrecover_current26 active only frozen earlier28/R3/raw5worlds; independent snapshot complete, next results excluded.','Fresh_media_receiver authors current28 custody dualseam helper only; no executionGO.','Media_resume_harness owns source-onlyF3a leaf; no native35/currentproduct adoption.','Earlier persistence anomalies unresolved, never replayed as a repair.']
assert scope=={k:d[k] for k in protected} and not d['full_release_qualified']
temp=R/'BUILD_STATUS.bounded.tmp';temp.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');os.replace(temp,p)
print(json.dumps({'bounded_receipt_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'ledger_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'protected_scope_unchanged':True,'whole_release':False}))
