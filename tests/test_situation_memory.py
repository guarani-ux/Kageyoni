import unittest
from kageyoni.situations.memory import *
from kageyoni.situations.studio import SituationStudio

class MemoryTests(unittest.TestCase):
 def test_dependency_relevance_can_beat_text_similarity(self):
  s=SituationMemoryStore(); s.remember(SituationMemory("recent","campaign","campaign","same words",dependency_keys=("other",))); s.remember(SituationMemory("old","old","research","different",dependency_keys=("audience-obligation",)))
  self.assertEqual("old",s.retrieve(dependency_keys=("audience-obligation",))[0].memory_id)
 def test_transfer_needs_destination_evidence(self):
  c=TransferCandidate("x","m","dest","relationships->campaign")
  self.assertEqual("untested",qualify_transfer(c).status)
  d=TransferCandidate("y","m","dest","relationships->campaign",destination_evidence_refs=("trial:1",))
  self.assertEqual("supported_in_destination",qualify_transfer(d).status)
 def test_studio_creates_required_family(self):
  st=SituationStudio(); x=st.new("production_brief","video",objective="launch",audience="members",deliverables=["video"],constraints=[]); self.assertEqual([],x.unknowns)

if __name__=="__main__": unittest.main()
