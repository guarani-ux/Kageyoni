import os, sqlite3, tempfile, unittest
from kageyoni.situations.storage import SQLiteSituationStore
from kageyoni.situations.models import Situation

MIGRATION="CREATE TABLE situation_records(kind TEXT NOT NULL, record_key TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(kind,record_key))"

class SQLiteSituationStoreTests(unittest.TestCase):
 def test_unmigrated_database_is_rejected(self):
  c=sqlite3.connect(":memory:")
  with self.assertRaises(RuntimeError): SQLiteSituationStore(c)

 def test_restart_reopens_same_situation(self):
  fd,path=tempfile.mkstemp(); os.close(fd)
  try:
   c1=sqlite3.connect(path); c1.execute(MIGRATION)
   s1=SQLiteSituationStore(c1)
   x=Situation("s1","research","research","q",objects={"question":"q"}); s1.put("situation","s1",x); c1.commit(); c1.close()
   c2=sqlite3.connect(path); s2=SQLiteSituationStore(c2)
   y=s2.get("situation","s1"); self.assertEqual("q",y.objective); self.assertEqual({"question":"q"},y.objects); c2.close()
  finally: os.unlink(path)

if __name__=="__main__": unittest.main()
