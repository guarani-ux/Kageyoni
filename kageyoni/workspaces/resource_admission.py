"""Pure operational capacity gates over the sole native activity/queue state.

A gate never grants action authority or mutates a checkpoint. Final configured
usage is also checked inside native create/update to prevent a writer bypass.
"""
import hashlib
import json

from ..engine import require
from ..resources import schema_path
from .resource_profiles import ResourceProfiles

TERMINAL = ('finished', 'failed', 'cancelled')


def _identifier(value):
    require(isinstance(value, str) and bool(value), 'invalid activity id')


def _capacity(condition):
    require(condition, 'resource activity capacity exceeded',
            rejection_class='TEMPORARY_STATE_BLOCK', details={'resource_capacity': True})


class ResourceAdmission:
    def __init__(self, engine, workspace_id):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id

    def _facts(self):
        return [dict(row) for row in self.db.execute('''
            SELECT a.activity_id,a.state,
             CASE WHEN json_type(a.native_json,'$.encounter_id') IS NOT NULL
                   AND json_type(a.native_json,'$.encounter_id')!='null' THEN 1 ELSE 0 END AS physical,
             EXISTS(SELECT 1 FROM activity_jobs j JOIN activity_queue q ON q.job_id=j.job_id
              WHERE j.workspace_id=a.workspace_id AND j.activity_id=a.activity_id
               AND q.workspace_id=a.workspace_id AND
                (q.state='running' OR (q.state='reconciling' AND q.process_json IS NOT NULL))) AS live
            FROM activity_runs a WHERE a.workspace_id=? AND a.state NOT IN ('finished','failed','cancelled')
            ''', (self.workspace_id,))]

    def _usage(self, profile, facts):
        reserved = sum(row['state']=='paused' and not row['physical'] for row in facts)
        if profile['profile_id']=='legacy':
            active, dormant = len(facts), 0
        else:
            dormant = sum(row['state']=='paused' and not row['physical'] and not row['live'] for row in facts)
            active = len(facts)-dormant
        return dict(profile_digest=profile['digest'], total_nonterminal=len(facts),
                    active=active, dormant=dormant, paused_capacity_reserved=reserved)

    def usage(self):
        profile = ResourceProfiles(self.engine, self.workspace_id).get()
        return self._usage(profile, self._facts())

    @staticmethod
    def _check(profile, usage):
        _capacity(usage['total_nonterminal']<=profile['total_nonterminal_limit']
                  and usage['active']<=profile['active_activity_limit']
                  and usage['paused_capacity_reserved']<=profile['inactive_activity_limit'])
        return usage

    def check_start(self):
        profile = ResourceProfiles(self.engine, self.workspace_id).get()
        usage = self._usage(profile, self._facts())
        usage['total_nonterminal']+=1
        usage['active']+=1
        return self._check(profile, usage)

    def _target(self, activity_id):
        _identifier(activity_id)
        row=self.db.execute('SELECT state FROM activity_runs WHERE workspace_id=? AND activity_id=?',
                            (self.workspace_id,activity_id)).fetchone()
        require(row is not None and row['state'] not in TERMINAL, 'activity unavailable')

    def check_resume(self, activity_id):
        self._target(activity_id)
        profile=ResourceProfiles(self.engine,self.workspace_id).get()
        facts=self._facts()
        for row in facts:
            if row['activity_id']==activity_id:
                row['state']='waiting'
                break
        return self._check(profile,self._usage(profile,facts))

    def check_pause(self, activity_id):
        self._target(activity_id)
        profile=ResourceProfiles(self.engine,self.workspace_id).get()
        facts=self._facts()
        for row in facts:
            if row['activity_id']==activity_id:
                row['state']='paused'
                break
        projected=self._usage(profile,facts)
        return projected if profile['profile_id']=='legacy' else self._check(profile,projected)


def _validate_configured_usage(engine, workspace_id):
    profile=ResourceProfiles(engine,workspace_id).get()
    if profile['profile_id']!='legacy':
        admission=ResourceAdmission(engine,workspace_id)
        admission._check(profile,admission._usage(profile,admission._facts()))


def verify_resource_admission(engine):
    db=engine.db
    row=db.execute("SELECT version FROM engine_versions WHERE component='resource_admission_interface'").fetchone()
    if not row:
        return {'installed':False}
    require(row[0]=='1','unsupported resource admission interface')
    check=db.execute('SELECT checksum FROM migration_checks WHERE version=32').fetchone()
    require(check and check[0]==hashlib.sha256(schema_path('migration_032.sql').read_bytes()).hexdigest(),
            'resource admission migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(),'resource admission foreign key failure')
    from .activities import verify_activity_membership
    verify_activity_membership(engine)
    for row in db.execute('SELECT workspace_id FROM operational_workspaces'):
        _validate_configured_usage(engine,row['workspace_id'])
    return {'installed':True,'interface':'1'}
