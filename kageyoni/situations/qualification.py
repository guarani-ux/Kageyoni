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
 st=SituationStudio(); st.service.register_workflow(SCAR_WORKFLOW); out={}
 for family,(objective,data) in FAMILY_FIXTURES.items():
  s=st.new(family,objective,**data); recommended=st.service.templates[family].recommended_workflows[0]; st.service.bind_workflow(s.situation_id,recommended); out[family]={"unknowns":list(s.unknowns),"workflow":recommended,"workspace":s.workspace}
 return out
