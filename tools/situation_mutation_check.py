from __future__ import annotations
import pathlib,shutil,subprocess,sys,tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
MUTATIONS=[
 ("borrowed-domain","kageyoni/situations/service.py","if self.participant_evidence_resolver is None or any(","if False and any(","test_situations.SituationArchitectureTests.test_domain_cannot_borrow_other_participant_evidence"),
 ("stage-evidence","kageyoni/situations/runtime.py","if not evidence_ref or self.evidence_resolver is None or not self.evidence_resolver(evidence_ref,run):","if False:","test_situation_runtime.RuntimeTests.test_stage_requires_engine_evidence"),
 ("transfer-evidence","kageyoni/situations/memory.py","if evidence_resolver is None or any(not evidence_resolver(ref,c.destination_situation_id) for ref in c.destination_evidence_refs):","if False:","test_situation_memory.MemoryTests.test_transfer_needs_destination_evidence"),
 ("promotion-evidence","kageyoni/situations/runtime.py","if self.evidence_resolver is None or any(not self.evidence_resolver(ref,None) for ref in repeated_outcome_refs):","if False:","test_situation_runtime.RuntimeTests.test_extension_promotion_requires_repeat_and_custody"),
]

def main():
 killed=[]; inconclusive=[]
 for name,path,old,new,test in MUTATIONS:
  with tempfile.TemporaryDirectory() as td:
   dst=pathlib.Path(td)/"repo"; shutil.copytree(ROOT,dst)
   p=dst/path; text=p.read_text()
   if old not in text: inconclusive.append((name,"anchor missing")); continue
   p.write_text(text.replace(old,new,1))
   env=dict(__import__("os").environ); env["PYTHONPATH"]=str(dst)
   cp=subprocess.run([sys.executable,"-m","unittest",test],cwd=dst/"tests",env=env,capture_output=True,text=True,timeout=30)
   if cp.returncode!=0: killed.append(name)
   else: inconclusive.append((name,"mutant survived"))
 print({"killed":killed,"inconclusive":inconclusive})
 return 0 if len(killed)==len(MUTATIONS) else 1
if __name__=="__main__": raise SystemExit(main())
