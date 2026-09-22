import json, sqlite3, unittest
from kageyoni.situations.integration import KageyoniSituationAdapter

class FakeEngine:
    def __init__(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE situation_records(kind TEXT,record_key TEXT,payload_json TEXT,PRIMARY KEY(kind,record_key))")
        self.db.execute("CREATE TABLE events(id TEXT PRIMARY KEY,actor TEXT)")
        self.db.execute("CREATE TABLE artifacts(artifact_id TEXT PRIMARY KEY)")
        self.db.execute("CREATE TABLE method_revisions(method_id TEXT)")
        self.db.execute("CREATE TABLE pipeline_runs(pipeline_id TEXT PRIMARY KEY,payload_json TEXT)")
        self.db.execute("CREATE TABLE v11_execution_receipts(receipt_id TEXT PRIMARY KEY)")
        self.db.execute("CREATE TABLE node_method_assignments(node_id TEXT,method_id TEXT,qualification TEXT)")
        self.db.execute("CREATE TABLE node_bindings(node_id TEXT,character_id TEXT)")

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.e=FakeEngine(); self.a=KageyoniSituationAdapter(self.e)
    def test_resolves_only_existing_domain_evidence(self):
        self.e.db.execute("INSERT INTO events VALUES('ev1','sciel')")
        self.e.db.execute("INSERT INTO pipeline_runs VALUES('p1',?)",(json.dumps({"phase":"completed"}),))
        self.assertTrue(self.a.evidence("event:ev1"))
        self.assertTrue(self.a.evidence("pipeline:p1"))
        self.assertFalse(self.a.evidence("event:missing"))
    def test_participant_cannot_borrow_method(self):
        self.e.db.execute("INSERT INTO node_method_assignments VALUES('node-sciel','composition','experimental')")
        self.e.db.execute("INSERT INTO node_bindings VALUES('node-sciel','sciel')")
        self.assertTrue(self.a.participant_evidence("sciel","method:composition","s"))
        self.assertFalse(self.a.participant_evidence("alexandra","method:composition","s"))
    def test_service_uses_existing_connection(self):
        service=self.a.service()
        self.assertIs(service.store.conn,self.e.db)

if __name__=="__main__": unittest.main()
