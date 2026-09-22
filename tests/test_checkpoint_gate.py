import subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from kageyoni.engine import Engine
class CheckpointGateTests(unittest.TestCase):
 def test_real_corruption_is_rejected_before_publication(self):
  with tempfile.TemporaryDirectory() as td:
   e=Engine(Path(td)/'live.sqlite');dest=Path(td)/'delivered.sqlite';real=subprocess.run
   def corrupt_then_verify(args,**kwargs):
    Path(args[3]).write_bytes(b'broken database')
    return real(args,**kwargs)
   with patch('kageyoni.checkpoint.subprocess.run',side_effect=corrupt_then_verify):
    with self.assertRaises(subprocess.CalledProcessError):e.backup(dest)
   self.assertFalse(dest.exists());self.assertFalse(list(Path(td).glob('.kageyoni-check-*')));e.verify();e.close()
 def test_rejected_existing_destination_keeps_bytes(self):
  with tempfile.TemporaryDirectory() as td:
   e=Engine(Path(td)/'live.sqlite');dest=Path(td)/'keep.sqlite';dest.write_bytes(b'keep')
   with self.assertRaises(Exception):e.backup(dest)
   self.assertEqual(dest.read_bytes(),b'keep');e.close()
