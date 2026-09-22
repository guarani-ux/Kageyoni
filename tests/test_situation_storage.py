import os, sqlite3, tempfile, unittest
from kageyoni.situations.storage import SQLiteSituationStore
from kageyoni.situations.models import Situation

class SQLiteSituationStoreTests(unittest.TestCase):
 def test_restart_reopens_same_situation(self):
  fd,path=tempfile.mkstemp(); os.close(fd)
  try:
   c1=sqlite3.connect(path); s1=SQLiteSituationStore(c1,{"situation":lambda p:Situation(**p)}); x=Situation("s1","research","research","q",objects={"question":"q"}); s1.put("situation","s1",x); c1.commit(); c1.close()
   c2=sqlite3.connect(path); s2=SQLiteSituationStore(c2,{"situation":lambda p:Situation(**p)}); y=s2.get("situation","s1"); self.assertEqual("q",y.objective); self.assertEqual({"question":"q"},y.objects); c2.close()
  finally: os.unlink(path)
 def test_store_uses_supplied_connection(self):
  c=sqlite3.connect(":memory:"); SQLiteSituationStore(c); self.assertIsNotNone(c.execute("SELECT name FROM sqlite_master WHERE name='situation_records'").fetchone())

if __name__=="__main__": unittest.main()
