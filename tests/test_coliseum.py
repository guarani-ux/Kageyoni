import tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine,Rejected
from kageyoni.workflows import Workflows
class ColiseumTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.path=Path(self.t.name)/'arena.sqlite';self.e=Engine(self.path);self.e.fork('main','arena',0);self.w=Workflows(self.e)
 def tearDown(self):self.e.close();self.t.cleanup()
 def setup_match(self,**defender):
  a=dict(health=10,stamina=6,power=4,speed=4,reaction=5,guard=2,mobile=1,guard_intact=1);b=dict(a);b.update(defender)
  self.w.coliseum_open(branch='arena',request_id='setup',match='pit',stats={'a':a,'b':b})
 def attack(self,defense='guard',intent='finisher',revision=None):
  return self.w.coliseum_exchange(branch='arena',request_id='exchange-'+str(self.e.branch('arena')['revision']),match='pit',attacker='a',defender='b',intent=intent,defense=defense,expected_revision=self.e.branch('arena')['revision'] if revision is None else revision)
 def test_mobile_dodge_changes_result(self):
  self.setup_match();r=self.attack('dodge');self.assertEqual((r['outcome'],r['damage']),('evaded',0))
 def test_restrained_dodge_rejects_without_cost_or_event(self):
  self.setup_match(mobile=0);before=self.e.state('arena');rev=self.e.branch('arena')['revision']
  with self.assertRaisesRegex(Rejected,'restraint'):self.attack('dodge')
  self.assertEqual(before,self.e.state('arena'));self.assertEqual(rev,self.e.branch('arena')['revision'])
 def test_guard_injury_persists_and_blocks_reuse_after_reload(self):
  self.setup_match();r=self.attack();self.assertEqual(r['damage'],4);self.e.close();self.e=Engine(self.path);self.w=Workflows(self.e)
  self.assertEqual(self.e.get('arena','b:guard_intact')['data']['quantity'],0)
  with self.assertRaisesRegex(Rejected,'injured'):self.attack()
  self.assertEqual(self.e.branch('main')['revision'],0);self.assertEqual(self.e.state('main'),[]);self.e.verify()
 def test_fast_attack_defeats_slow_dodge(self):
  self.setup_match(reaction=1);self.assertEqual(self.attack('dodge')['damage'],6)
 def test_unknown_will_cannot_be_invented(self):
  self.setup_match()
  with self.assertRaisesRegex(Rejected,'technique contract'):self.attack(intent='substitution')
 def test_incapacitation_closes_exchange(self):
  self.setup_match(health=2);self.assertEqual(self.attack('none')['outcome'],'incapacitated')
  with self.assertRaisesRegex(Rejected,'incapacitated'):self.attack('none')
 def test_missing_stamina_blocks_defense(self):
  self.setup_match(stamina=0)
  with self.assertRaisesRegex(Rejected,'stamina'):self.attack('dodge')
 def test_stale_retry_does_not_charge_twice(self):
  self.setup_match();rev=self.e.branch('arena')['revision'];self.attack('none');before=self.e.state('arena')
  with self.assertRaisesRegex(Rejected,'stale'):self.attack('none',revision=rev)
  self.assertEqual(before,self.e.state('arena'))
 def test_main_branch_is_protected(self):
  with self.assertRaisesRegex(Rejected,'isolated'):self.w.coliseum_open(branch='main',request_id='bad',match='pit',stats={})
 def test_out_of_reach_cannot_hit(self):
  self.setup_match();rec=self.e.get('arena','pit:distance')
  self.e.apply(dict(api_version=2,branch='arena',expected_revision=self.e.branch('arena')['revision'],request_id='distance',kind='action',actor='arena-gm',narrative='Synthetic separation',changes=[dict(op='patch',id=rec['id'],expected_version=rec['version'],data={'quantity':2},evidence=[{'note':'fixture'}])]))
  with self.assertRaisesRegex(Rejected,'reach'):self.attack()
