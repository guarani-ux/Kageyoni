from kageyoni.situations.studio import SituationStudio
from kageyoni.situations.scar import SCAR_WORKFLOW

FAMILY_FIXTURES={
 "research":("Investigate a claim",{"question":"What is supported?"}),
 "production_brief":("Plan a video",{"objective":"inform","audience":"members","deliverables":["video"],"constraints":[]}),
 "campaign":("Build a campaign",{"objective":"awareness","audience":"members"}),
 "writing":("Write a script",{"purpose":"explain","audience":"public"}),
 "repository_repair":("Repair a defect",{"objective":"fix failing behavior","repository":"fixture"}),
 "living_world":("Continue scene",{"scene":"fixture","participants":["a","b"]}),
}

def connected_family_check():
 st=SituationStudio(test_mode=True); st.service.register_workflow(SCAR_WORKFLOW); out={}
 for family,(objective,data) in FAMILY_FIXTURES.items():
  s=st.new(family,objective,**data)
  recommended=st.service.templates[family].recommended_workflows[0]
  st.service.bind_workflow(s.situation_id,recommended)
  out[family]={"unknowns":list(s.unknowns),"contradictions":list(getattr(s,"contradictions",[])),"workflow":recommended,"workspace":s.workspace}
 return out

def incomplete_genesis_check():
 st=SituationStudio(test_mode=True); out={}
 for family,(objective,data) in FAMILY_FIXTURES.items():
  required=st.service.templates[family].required
  if not required: continue
  incomplete=dict(data); incomplete.pop(required[0],None)
  s=st.new(family,objective,**incomplete)
  out[family]=list(s.unknowns)
 return out

def contradiction_check():
 st=SituationStudio(test_mode=True)
 s=st.new("campaign","c",objective="awareness",audience={"__alternatives__":["members","nonmembers"]})
 return {"unknowns":list(s.unknowns),"contradictions":list(getattr(s,"contradictions",[]))}
