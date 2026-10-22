"""One application-owned command/result boundary over a separate Kageyoni.

Every supported client supplies trusted CallerContext out of band. Only this
owner opens the mutable Engine. SQL here is operational persistence in the
engine-maintained migration, never a second world database.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import shutil
import time
import traceback
from uuid import uuid4

from kageyoni.application import Application
from kageyoni.engine import Rejected
from kageyoni.workspaces.resource_profiles import ResourceProfiles
from kageyoni.workspaces.resource_admission import ResourceAdmission
from kageyoni.emergence.action_dispatcher import EncounterActionDispatcher
from kageyoni.persistence.unit_of_work import UnitOfWork

from .content import definitions, work_template
from .handlers import EncounterHandler, TextWorkHandler
from .intake import Intake
from .properties import Properties
from .causality import Causality
from .extensions import Extensions
from .situation import Situation
from .practice import Practice
from .exploration import Exploration
from .sourcework import SourceWork
from .mediawork import MediaWork
from .contentsets import ContentSets
from .atlas import Atlas
from .equipment import Equipment
from .protocol import PROTOCOL, Fault, digest, encoded, error, frame, validate, runtime_fingerprint

TERMINAL = {'finished', 'failed', 'cancelled'}
OPERATIONS = {'doctor', 'workspace.view', 'activity.start', 'activity.status', 'activity.pause',
              'activity.resume', 'activity.cancel', 'activity.receive', 'artifact.read', 'artifact.fetch', 'artifact.submit'}
OPERATIONS.update({'intake.admit', 'intake.status', 'job.enqueue', 'job.status', 'job.reconcile'})
RESOURCE_OPERATIONS = {'resource.profile', 'resource.configure'}
OPERATIONS.update(RESOURCE_OPERATIONS)
OPERATIONS.add('practice.account')
PROPERTY_READS = {'property.catalog', 'property.select', 'property.inspect', 'change.preview', 'support.status'}
PROPERTY_WRITES = {'change.prepare', 'change.apply', 'change.withdraw', 'support.use', 'support.release', 'clock.advance'}
WORLD_READS={'world.status'}
WORLD_WRITES={'world.signal','world.step','world.resume'}
EXTENSION_READS={'extension.catalog','extension.preview'}
EXTENSION_WRITES={'extension.prepare','extension.activate','extension.disable','extension.replace','extension.retire','extension.delete'}
OPERATIONS.update(PROPERTY_READS | PROPERTY_WRITES | WORLD_READS | WORLD_WRITES | EXTENSION_READS | EXTENSION_WRITES)
CONTENT_WRITES = {'content.prepare','content.activate'}
CONTENT_READS = {'content.preview','content.available'}
CONTEST_WRITES = {'contest.open','contest.consent','contest.begin','contest.settle'}
CONTEST_READS = {'contest.inspect'}
OPERATIONS.update(CONTEST_WRITES | CONTEST_READS)
ATLAS_READS = {'atlas.view'}
ATLAS_WRITES = {'atlas.journey','equipment.release'}
OPERATIONS.update(CONTENT_WRITES | CONTENT_READS | ATLAS_READS | ATLAS_WRITES)
READS = {'resource.profile'} | CONTEST_READS | CONTENT_READS | ATLAS_READS | PROPERTY_READS | WORLD_READS | EXTENSION_READS | {'doctor', 'workspace.view', 'activity.status', 'artifact.read', 'artifact.fetch', 'intake.status', 'job.status'}


class _PropertyNamespace:
    """Declared semantic pins over the same application, not another engine."""
    def __init__(self, app):
        self._app = app

    @property
    def runtime_digest(self):
        return self._app.property_runtime_digest

    def __getattr__(self, name):
        return getattr(self._app, name)


@dataclass(frozen=True)
class CallerContext:
    binding_id: str
    principal_id: str
    workspace_id: str
    role: str
    character_id: str | None
    authority_epoch: int
    activity_id: str | None


class SamsaraApplication:
    def __init__(self, engine, workspace_id, root):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id
        self.branch, self.root = 'main', Path(root)
        self.runtime_digest = runtime_fingerprint()
        # Compatibility retains an audited property semantic namespace, never
        # an old executable runtime. All operations still reach this engine.
        metadata_path = self.root / 'workspace.json'
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        from .compatibility import validate_continuation
        validate_continuation(engine, metadata)
        self.property_runtime_digest = metadata.get('property_runtime_digest', self.runtime_digest)
        self.continuation_new_activity_admission = metadata.get('continuation_new_activity_admission', True)
        self.services = Application(engine)
        self.store = self.services.activities
        self.resource_profiles = ResourceProfiles(engine, workspace_id)
        self.resource_admission = ResourceAdmission(engine, workspace_id)
        # Constructors that install opt-in interfaces run outside command UoWs.
        self.dispatcher = EncounterActionDispatcher(engine, self.services.encounters)
        self.catalog = {x['id']: x for x in definitions()}
        encounter, work = EncounterHandler(), TextWorkHandler()
        self.handlers = {'battle': encounter, 'travel': encounter, 'life': encounter, 'study': work, 'research': work, 'real_work': work}
        self.transfers, self.cursors = {}, {}
        self.intake = Intake(self)
        self.properties = Properties(_PropertyNamespace(self))
        self.causality = Causality(self)
        self.extensions = Extensions(self)
        self.situation = Situation(self)
        self.practice = Practice(self)
        self.exploration = Exploration(self)
        self.source_work = SourceWork(self)
        self.media_work = MediaWork(self)
        self.content_sets = ContentSets(self)
        from .exhibitions import Exhibitions
        self.exhibitions = Exhibitions(self)
        self.atlas = Atlas(self)
        self.equipment = Equipment(self)
        self._reload_content()

    def _reload_content(self):
        # These caches derive solely from committed native artifacts/registry.
        # A rolled-back command must not leave an invented active catalog.
        self.catalog = {x['id']: x for x in definitions()}
        self.content_sets.reload()
        self.catalog.update(self.content_sets.definitions)
        self.atlas.reload()
        self.equipment.reload()

    def _resource_gate(self, method, *args):
        try:
            return getattr(self.resource_admission, method)(*args)
        except Rejected as exc:
            if exc.details.get('resource_capacity') is True:
                raise Fault('BUSY') from None
            raise

    def _resource_view(self, context, operation, request_id):
        if context.role != 'operator':
            raise Fault('UNAVAILABLE')
        if operation['name'] == 'resource.configure':
            try:
                self.resource_profiles.configure(
                    {'profile_id': operation['profile_id'], 'active_jobs': operation['active_jobs']},
                    self.key('resource-profile', context.principal_id, request_id), operation['expected_digest'])
            except Rejected as exc:
                if str(exc) == 'stale resource profile':
                    raise Fault('STALE') from None
                if str(exc) == 'configure resource profile before issued work':
                    raise Fault('DEPENDENCY') from None
                raise
        return {'kind': 'resources', 'profile': self.resource_profiles.get(),
                'usage': self.resource_admission.usage()}

    def _content_view(self, operation, value):
        details = encoded(value)
        if len(details.encode('utf-8')) > 200000:
            raise Fault('BUDGET')
        return {'kind':'content','operation':operation,'details':details}

    @staticmethod
    def key(*parts):
        return 'samsara:' + digest(list(parts))

    def revision(self):
        return self.engine.branch(self.branch)['revision']

    def bind(self, role='operator', character_id=None, activity_id=None):
        """Trusted launcher call. This is never a model-supplied Command."""
        if role not in ('operator', 'player', 'worker'):
            raise Fault('UNAVAILABLE')
        if role != 'operator':
            visible = {r['id']: r for r in self.engine.context(self.branch, viewer=character_id)['records']}
            if not self.content_sets.actor_admitted(character_id) or character_id not in visible:
                raise Fault('UNAVAILABLE')
            if role == 'worker' and not activity_id:
                raise Fault('UNAVAILABLE')
            if activity_id:
                activity = self.store.get(self.workspace_id, activity_id)
                if character_id not in activity['spec']['participants']:
                    raise Fault('UNAVAILABLE')
        principal = 'operator:' + str(os.getuid()) if role == 'operator' else 'character:' + character_id
        binding = self.key('binding', role, principal, activity_id)
        row = self.db.execute('SELECT * FROM activity_bindings WHERE binding_id=?', (binding,)).fetchone()
        epochs = self.db.execute('SELECT MAX(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?', (self.workspace_id, principal)).fetchone()
        epoch = epochs[0] or 1
        # Reactivating a revoked binding requires the explicit trusted launcher.
        grants = OPERATIONS if role == 'operator' else OPERATIONS - {'intake.admit'} - CONTENT_WRITES - {'content.preview','contest.open'} - RESOURCE_OPERATIONS
        if role == 'worker':
            grants = grants - CONTEST_READS - CONTEST_WRITES - PROPERTY_WRITES - WORLD_WRITES - ATLAS_WRITES - {'activity.pause', 'activity.resume', 'activity.cancel', 'job.reconcile'}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO activity_bindings VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(binding_id) DO UPDATE SET active=1,authority_epoch=excluded.authority_epoch',
                (binding, self.workspace_id, principal, role, character_id, epoch, 1, encoded(sorted(grants)), activity_id))
        context = CallerContext(binding, principal, self.workspace_id, role, character_id, epoch, activity_id)
        output_root = self.root / 'staging' / hashlib.sha256(binding.encode()).hexdigest()
        output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return context, output_root

    def revoke(self, binding_id):
        with UnitOfWork(self.db):
            self.db.execute('UPDATE activity_bindings SET active=0,authority_epoch=authority_epoch+1 WHERE binding_id=?', (binding_id,))

    def authorize(self, context):
        row = self.db.execute('SELECT * FROM activity_bindings WHERE binding_id=?', (context.binding_id,)).fetchone()
        if not row or not row['active'] or row['authority_epoch'] != context.authority_epoch or row['principal_id'] != context.principal_id or row['workspace_id'] != context.workspace_id or row['role'] != context.role or row['character_id'] != context.character_id or row['activity_id'] != context.activity_id:
            raise Fault('UNAVAILABLE')
        return row

    def in_scope(self, context, activity):
        if context.role == 'operator':
            return True
        if context.character_id not in activity['spec']['participants']:
            return False
        if context.role != 'worker':
            return True
        current = activity
        for _ in range(5):
            if current['activity_id'] == context.activity_id:
                return True
            if not current['parent_id']:
                return False
            current = self.store.get(self.workspace_id, current['parent_id'])
        return False

    def activity(self, context, activity_id):
        try:
            value = self.store.get(self.workspace_id, activity_id)
        except Rejected:
            raise Fault('UNAVAILABLE') from None
        if not self.in_scope(context, value):
            raise Fault('UNAVAILABLE')
        return value

    def grant(self, ref, principal, activity_id=None):
        self.db.execute('INSERT OR IGNORE INTO activity_artifact_grants VALUES(?,?,?,?,?)',
            (self.workspace_id, principal, ref['id'], ref['digest'], activity_id))
        self.properties.copy_grant(ref, principal)

    def put(self, content, media_type, request_id, principals=(), activity=None, *, recipients_override=None, source_refs_override=None, private_viewer=None):
        size = len(content.encode('utf-8') if isinstance(content, str) else content)
        used = self.db.execute('SELECT coalesce(sum(size),0) FROM artifacts WHERE workspace_id=?', (self.workspace_id,)).fetchone()[0]
        if used + size > 2147483648 or shutil.disk_usage(self.root).free < 1073741824:
            raise Fault('BUDGET')
        sources = list(activity['spec']['source_refs']) if activity and source_refs_override is None else list(source_refs_override or ())
        viewers = {private_viewer} if private_viewer is not None else set()
        for source in sources:
            audience = self.artifact_audience(source)
            if audience is not None:
                viewers.add(audience)
        if len(viewers) > 1:
            raise Fault('UNAVAILABLE')
        viewer = next(iter(viewers), None)
        # Caller/workspace authority and immutable artifact audience are distinct.
        meta = self.services.artifacts.put(content, media_type, request_id, workspace_id=self.workspace_id, viewer=None, recipient=viewer)
        ref = {'id': meta['artifact_id'], 'version': 1, 'digest': meta['digest']}
        recipients = set(principals) if recipients_override is None else set(recipients_override)
        if activity and recipients_override is None:
            recipients.update('character:' + x for x in activity['spec']['participants'])
            if activity['parent_id']:
                parent = self.store.get(self.workspace_id, activity['parent_id'])
                recipients.update('character:' + x for x in parent['spec']['participants'])
        for principal in recipients:
            self.grant(ref, principal, activity['activity_id'] if activity else None)
        self.properties.inherit(ref, recipients, sources)
        return ref

    def put_json(self, value, request_id, principals=(), activity=None, **projection):
        return self.put(encoded(value), 'application/json', request_id, principals, activity, **projection)

    def artifact_audience(self, ref):
        validate(ref, 'Reference')
        row = self.db.execute('SELECT viewer FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',
            (self.workspace_id, ref['id'], ref['digest'])).fetchone()
        if row is None or ref['version'] != 1:
            raise Fault('UNAVAILABLE')
        return row['viewer']

    def artifact_scope_for_actor(self, actor, ref, *, prospective=False):
        from types import SimpleNamespace
        viewer = self.artifact_audience(ref)
        if viewer is not None and viewer != actor:
            raise Fault('UNAVAILABLE')
        epoch = self.db.execute('SELECT MAX(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?',
            (self.workspace_id, 'character:' + actor)).fetchone()[0] or 1
        context = SimpleNamespace(role='player', principal_id='character:' + actor,
            authority_epoch=epoch, character_id=actor)
        if prospective:
            # A reviewed public projection may be shared before delivery. Its
            # actual C2 scopes still apply, even without a recipient grant yet.
            rows = self.db.execute('SELECT scope_json FROM property_read_grants WHERE workspace_id=? AND artifact_id=?',
                (self.workspace_id, ref['id'])).fetchall()
            scopes = {tuple(scope) for row in rows for scope in json.loads(row['scope_json'])}
            for eid, pid, version in scopes:
                self.properties.entity(context, eid)
                if pid is not None:
                    self.properties.require_property_access(context, eid, pid, version)
        else:
            self.properties.authorize_artifact(context, ref)
        self.causality.authorize_artifact(context, ref)

    def authorize_artifact(self, context, ref):
        self.authorize(context)
        validate(ref, 'Reference')
        row = self.db.execute('SELECT * FROM artifacts WHERE workspace_id=? AND artifact_id=?', (self.workspace_id, ref['id'])).fetchone()
        if not row or ref['version'] != 1 or row['digest'] != ref['digest']:
            raise Fault('UNAVAILABLE')
        if context.role != 'operator':
            if self.artifact_audience(ref) not in (None, context.character_id):
                raise Fault('UNAVAILABLE')
            grant = self.db.execute('SELECT * FROM activity_artifact_grants WHERE workspace_id=? AND principal_id=? AND artifact_id=? AND digest=?',
                (self.workspace_id, context.principal_id, ref['id'], ref['digest'])).fetchone()
            if not grant:
                raise Fault('UNAVAILABLE')
            if grant['activity_id']:
                activity = self.store.get(self.workspace_id, grant['activity_id'])
                # Parent recipients may read a child's returned component.
                if not self.in_scope(context, activity) and not (activity['parent_id'] and self.in_scope(context, self.store.get(self.workspace_id, activity['parent_id']))):
                    raise Fault('UNAVAILABLE')
        self.properties.authorize_artifact(context, ref)
        self.causality.authorize_artifact(context, ref)

    def artifact_bytes(self, context, ref):
        self.authorize_artifact(context, ref)
        # Native owner read follows product binding, grant, audience and C2 checks.
        return self.services.artifacts.read(ref['id'], viewer=None)['content']

    def artifact_bytes_for_actor(self, actor, ref):
        row = self.db.execute('SELECT * FROM activity_artifact_grants WHERE workspace_id=? AND principal_id=? AND artifact_id=? AND digest=?',
            (self.workspace_id, 'character:' + actor, ref['id'], ref['digest'])).fetchone()
        if not row or ref['version'] != 1:
            raise Fault('UNAVAILABLE')
        self.artifact_scope_for_actor(actor, ref)
        return self.services.artifacts.read(ref['id'], viewer=None)['content']

    def text_recipients(self, spec):
        """Current and graph-reachable downstream choosers of raw text work."""
        actors = set(spec['participants'])
        parent_id, seen = spec['parent_id'], set()
        while parent_id:
            if parent_id in seen or len(seen) >= 4:
                raise Fault('DEPENDENCY')
            seen.add(parent_id)
            parent = self.store.get(self.workspace_id, parent_id)
            definition = self.catalog[parent['spec']['definition']['id']]
            if definition['handler'] == 'text_work':
                actors.update(parent['spec']['participants'])
            else:
                native = self.services.encounters.inspect(self.branch, parent['native']['encounter_id'], viewer=None)
                bindings = native['participants']
                encounter = definition['encounter']
                pending, visited = [native['current_state']], set()
                while pending:
                    state = pending.pop()
                    if state in visited:
                        continue
                    visited.add(state)
                    for aid in encounter['states'][state]['actions']:
                        action = encounter['actions'][aid]
                        actors.add(bindings[action['actor_role']])
                        targets = [action['next_state']] if 'next_state' in action else list(action.get('next_by_outcome', {}).values())
                        if action['kind'] == 'judgment':
                            targets += [choice['next_state'] for choice in action['payload']['choices']]
                        pending.extend(targets)
            parent_id = parent['parent_id']
        return actors

    def text_sources(self, spec, extra=()):
        recipients = self.text_recipients(spec)
        for source in list(spec['source_refs']) + list(extra):
            for actor in recipients:
                self.artifact_scope_for_actor(actor, source, prospective=True)

    def text_input_sources(self, activity, prepared):
        value = self.packet(prepared)['input']
        pinned = (list(value.get('source_refs', [])) if self.media_work.enabled(activity)
                  else [item['source_ref'] for item in value.get('sources', [])]
                  if self.source_work.enabled(activity) else [])
        return ([ref for child in value.get('child_returns', []) for ref in child['result_refs']]
            + [item['reference'] for item in value.get('reconciled_returns', [])] + pinned)

    def text_outputs(self, activity, prepared, result, queue_fence):
        # Only actual current-job staged or fenced queue output is newly
        # produced. Borrowed refs need each future reader's existing authority.
        stages = self.db.execute('SELECT staging_ref FROM activity_staging WHERE job_id=? AND generation=? AND consumed=1',
            (prepared['job_id'], prepared['attempt_generation'])).fetchall()
        admitted = {self.key(row['staging_ref'], 'admit') for row in stages}
        if queue_fence is not None:
            admitted.add(self.key(prepared['job_id'], 'queue-output'))
        recipients = self.text_recipients(activity['spec'])
        for ref in result['output_refs'] + result['tool_receipt_refs']:
            row = self.db.execute('SELECT request_id FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',
                (self.workspace_id, ref['id'], ref['digest'])).fetchone()
            for actor in recipients:
                self.artifact_scope_for_actor(actor, ref, prospective=True)
                if row is None or row['request_id'] not in admitted:
                    self.artifact_bytes_for_actor(actor, ref)

    def artifact_view(self, context, ref):
        blob = self.artifact_bytes(context, ref)
        row = self.db.execute('SELECT media_type FROM artifacts WHERE artifact_id=?', (ref['id'],)).fetchone()
        text = None
        try:
            candidate = blob.decode('utf-8')
            if len(candidate) <= 262144 and len(candidate.encode()) <= 800000:
                text = candidate
        except UnicodeError:
            pass
        token = expires = None
        if text is None:
            token = 'transfer:' + uuid4().hex
            deadline = time.time() + 60
            self.transfers[token] = (context.principal_id, context.authority_epoch, ref, deadline)
            expires = datetime.fromtimestamp(deadline, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return {'kind': 'artifact', 'reference': ref, 'media_type': row['media_type'], 'availability': 'available',
                'text': text, 'transfer_ref': token, 'total_bytes': len(blob), 'transfer_expires_at': expires}

    def packet(self, prepared):
        row = self.db.execute('SELECT content FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',
            (self.workspace_id, prepared['input_ref']['id'], prepared['input_ref']['digest'])).fetchone()
        if not row:
            raise Fault('DEPENDENCY')
        return json.loads(bytes(row['content']).decode())

    def work_record(self, activity):
        ref = activity['native']['work_record_ref']
        return json.loads(self.services.artifacts.read(ref['id'], viewer=None)['content'])

    def handler_ref(self, kind):
        return {'id': 'samsara:handler:' + kind, 'version': 1, 'digest': digest([self.runtime_digest, kind])}

    def _prepare(self, activity, version):
        if activity['spec']['definition'] != self.catalog[activity['spec']['definition']['id']]['reference']:
            raise Fault('RECONCILE_REQUIRED')
        native, checkpoint = activity['native'], activity['checkpoint']
        # A deliberate new generation has a new dispatch identity. Historical
        # prepared jobs retain the handler they were actually issued with.
        checkpoint['handler'] = self.handler_ref(activity['spec']['kind'])
        generation = native.get('generation', 0) + 1
        job_id = self.key(activity['activity_id'], generation)
        prepared_input = self.handlers[activity['spec']['kind']].prepare(self, activity, job_id)
        if prepared_input is None:
            # A native controller with no offered actions can still be active.
            checkpoint.update(state='reconciling', outcome='unresolved',
                next={'actor':'recipient','operation':'activity.cancel','condition':'No native action is available; inspect, reconcile or cancel explicitly.'})
            return
        actor, value = prepared_input
        context_scope = value.pop('_scope_ids', [])
        expanded_sources = value.pop('_source_refs', [])
        # Child results are actual retained references. Delivering them wakes
        # the parent chooser, and never declares the parent purpose achieved.
        child_returns = []
        for message in self.db.execute("SELECT * FROM activity_outbox WHERE workspace_id=? AND parent_id=? AND status='pending' ORDER BY child_id,child_version", (self.workspace_id, activity['activity_id'])):
            payload = json.loads(message['payload_json'])
            for ref in payload['result_refs']:
                self.artifact_bytes_for_actor(actor, ref)
            child_returns.append({'child_id': message['child_id'], 'child_version': message['child_version'], **payload})
        if child_returns:
            value['child_returns'] = child_returns
        retained = []
        for returned in native.get('reconciled_returns', []):
            raw = self.artifact_bytes_for_actor(actor, returned)
            treatment = 'Recovered bytes from an interrupted job; no mechanical result or purpose was accepted.'
            if self.media_work.enabled(activity):
                row = self.db.execute('SELECT media_type FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',
                    (self.workspace_id, returned['id'], returned['digest'])).fetchone()
                if row is None:
                    raise Fault('UNAVAILABLE')
                retained.append({'reference': returned, 'media_type': row['media_type'],
                                 'bytes': len(raw), 'treatment': treatment})
            else:
                retained.append({'reference': returned, 'text': raw.decode('utf-8'), 'treatment': treatment})
        if retained:
            value['reconciled_returns'] = retained
        packet = {'activity_id': activity['activity_id'], 'job_id': job_id, 'attempt_generation': generation,
                  'branch_revision': self.revision(), 'input': value}
        projected = value.get('situation', {})
        prior_sources = [r['reference'] for r in projected.get('prior_practice', [])]
        prior_sources += [r['source_ref'] for r in projected.get('own_accounts', [])]
        prior_sources += [r['source_ref'] for r in projected.get('discoveries', [])]
        inherited = activity['spec']['source_refs'] + expanded_sources + prior_sources + native.get('reconciled_returns', []) + [r for child in child_returns for r in child['result_refs']]
        encounter = self.catalog[activity['spec']['definition']['id']]['handler'] == 'encounter'
        if not encounter:
            self.text_sources(activity['spec'], inherited)
        # Native chooser context is private; text audience follows actual inputs.
        ref = self.put_json(packet, self.key(job_id, 'input'), principals=['character:' + actor],
            source_refs_override=inherited, private_viewer=actor if encounter else None)
        self.properties.attach_entities(ref, ['character:' + actor], context_scope)
        self.db.execute('UPDATE activity_artifact_grants SET activity_id=? WHERE artifact_id=? AND workspace_id=?',
                        (activity['activity_id'], ref['id'], self.workspace_id))
        epoch_row = self.db.execute('SELECT MAX(authority_epoch) FROM activity_bindings WHERE principal_id=? AND workspace_id=?',
                                    ('character:' + actor, self.workspace_id)).fetchone()
        epoch = epoch_row[0] or 1
        prepared = {'dispatch_id': self.key(job_id, 'dispatch'), 'activity_id': activity['activity_id'], 'job_id': job_id,
            'attempt_generation': generation, 'handler': checkpoint['handler'], 'definition': activity['spec']['definition'],
            'input_ref': ref, 'read_set': {'complete': False, 'branch_revision': self.revision(), 'authority_epoch': epoch,
                'rows': [{'table':'activity_bindings','key':binding['binding_id'],'digest':digest({k:binding[k] for k in binding.keys() if k!='active'})}
                         for binding in self.db.execute('SELECT * FROM activity_bindings WHERE workspace_id=? AND principal_id=? ORDER BY binding_id',(self.workspace_id,'character:'+actor))], 'absences': [], 'predicates': [], 'definition_refs': [activity['spec']['definition']],
                'source_refs': activity['spec']['source_refs'], 'availability_refs': []},
            'authority_epoch': epoch, 'expected_revision': self.revision(), 'activity_version': version, 'job_version': 1,
            'reservations': [], 'budget': {'max_steps': 50, 'active_seconds': 900, 'model_turns': 4, 'input_tokens': 120000,
                'output_tokens': 16000, 'storage_bytes': 10000000, 'children': 8, 'depth': 4}}
        validate(prepared, 'Prepared')
        self.db.execute('INSERT INTO activity_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (job_id, self.workspace_id, activity['activity_id'], generation, 1, 'waiting', actor, encoded(prepared), digest(prepared), None, None))
        native.update(generation=generation, job_id=job_id, actor=actor, input_ref=ref)
        if child_returns:
            self.db.execute("UPDATE activity_outbox SET status='delivered' WHERE workspace_id=? AND parent_id=? AND status='pending'", (self.workspace_id, activity['activity_id']))
        dispatch = self.handlers[activity['spec']['kind']].dispatch(prepared)
        validate(dispatch, 'Dispatch')
        checkpoint.update(job_id=job_id, job_version=1, state='waiting', outcome='unresolved',
            next={'actor': 'worker', 'operation': 'activity.receive', 'condition': dispatch['resume_condition']},
            resume_condition=dispatch['resume_condition'])

    def _checkpoint_view(self, context, activity):
        cp = deepcopy(activity['checkpoint'])
        child_refs = []
        for message in self.db.execute('SELECT payload_json FROM activity_outbox WHERE workspace_id=? AND parent_id=? ORDER BY child_id,child_version', (self.workspace_id, activity['activity_id'])):
            child_refs.extend(json.loads(message[0])['result_refs'])
        refs = []
        for ref in cp['result_refs'] + child_refs:
            try:
                self.artifact_bytes(context, ref)
                if ref not in refs:
                    refs.append(ref)
            except Fault:
                continue
        if activity['native'].get('actor') == context.character_id or context.role == 'operator':
            ref = activity['native'].get('input_ref')
            if ref and activity['state'] == 'waiting':
                try:
                    self.authorize_artifact(context, ref)
                    refs = [ref] + refs
                except Fault:
                    pass
        cp['result_refs'] = refs
        return {'kind': 'activity', 'checkpoint': cp}

    def _start(self, context, op, *, _exhibition=None):
        if not self.continuation_new_activity_admission:
            raise Fault('DEPENDENCY')
        definition = self.catalog.get(op['definition']['id'])
        if not definition or definition['reference'] != op['definition'] or definition['kind'] != op['kind']:
            raise Fault('UNAVAILABLE')
        if self.db.execute('SELECT 1 FROM activity_runs WHERE workspace_id=? AND activity_id=?', (self.workspace_id, op['activity_id'])).fetchone():
            raise Fault('CONFLICT')
        if context.role != 'operator' and context.character_id not in op['participants']:
            raise Fault('UNAVAILABLE')
        if definition['participants'] is not None and op['participants'] != definition['participants']:
            raise Fault('INVALID')
        attachment = None
        if _exhibition is not None:
            attachment = self.exhibitions.attachment(context, op, _exhibition)
        if definition['id'].startswith('synthetic:f3a:repair:'):
            raise Fault('DEPENDENCY')
        if definition['id'].startswith('synthetic:f3a:exhibition:') and attachment is None:
            raise Fault('DEPENDENCY')
        if definition['handler'] == 'text_work' and (len(op['participants']) != 1 or not op['purpose']):
            raise Fault('INVALID')
        if any(not self.content_sets.actor_admitted(x) for x in op['participants']):
            raise Fault('UNAVAILABLE')
        if definition['handler'] == 'encounter':
            visible = {r['id']: r for r in self.engine.context(self.branch, viewer=context.character_id if context.role != 'operator' else None)['records']}
            location = definition.get('start_location', 'studio')
            if any(visible.get(actor, {}).get('data', {}).get('location') != location for actor in op['participants']):
                raise Fault('DEPENDENCY')
            self.practice.admit(context, definition, op['participants'])
            self.exploration.admit(definition, op['participants'], op['parent_id'])
        if context.role == 'worker' and (op['parent_id'] != context.activity_id or definition['handler'] != 'text_work' or op['participants'] != [context.character_id]):
            raise Fault('UNAVAILABLE')
        if op['parent_id']:
            parent = self.activity(context, op['parent_id'])
            if parent['state'] in TERMINAL or parent['state'] == 'paused':
                raise Fault('DEPENDENCY')
            count = self.db.execute('SELECT count(*) FROM activity_runs WHERE workspace_id=? AND parent_id=?', (self.workspace_id, op['parent_id'])).fetchone()[0]
            if count >= 8:
                raise Fault('BUDGET')
            depth, ancestor = 1, parent
            while ancestor['parent_id']:
                depth += 1
                ancestor = self.store.get(self.workspace_id, ancestor['parent_id'])
            if depth > 4:
                raise Fault('BUDGET')
        self._resource_gate('check_start')
        for ref in op['source_refs']:
            self.artifact_bytes(context, ref)
            for actor in op['participants']:
                self.artifact_bytes_for_actor(actor, ref)
        spec = {key: deepcopy(value) for key, value in op.items() if key != 'name'}
        validate(spec, 'ActivitySpec')
        if definition['handler'] == 'text_work':
            self.text_sources(spec)
        cp = {'activity_id': op['activity_id'], 'job_id': self.key(op['activity_id'], 'initial'), 'activity_version': 1,
            'state': 'preparing', 'outcome': 'unresolved', 'handler': self.handler_ref(op['kind']), 'pending_effects': [],
            'result_refs': [], 'next': {'actor': 'owner', 'operation': 'prepare', 'condition': ''}, 'job_version': 1,
            'reservations': [], 'resume_condition': '', 'parent_id': op['parent_id']}
        activity = {'workspace_id': self.workspace_id, 'activity_id': op['activity_id'], 'parent_id': op['parent_id'],
                    'spec': spec, 'native': {}, 'checkpoint': cp, 'version': 1, 'state': 'preparing'}
        if definition['handler'] == 'encounter':
            eid = 'encounter:' + digest([self.workspace_id, op['activity_id']])
            if attachment is None:
                self.services.encounters.start(self.branch, definition['id'], definition['version'], eid, self.key(context.principal_id, op['activity_id'], 'start'),
                    self.revision(), self.exploration.bindings(definition, op['participants']), viewer=None)
            else:
                eid = attachment['encounter_id']
                activity['native']['exhibition'] = self.exhibitions._tag(attachment)
            activity['native']['encounter_id'] = eid
            activity['native']['initiating_actor'] = context.character_id or op['participants'][0]
        else:
            record = work_template()
            record.update(record_type='work-record', project_id=op['activity_id'], objective=op['purpose'], version=1,
                integrating_owner=context.principal_id, authority={'scope': 'local component only', 'external_actions': False},
                sources=op['source_refs'], service_scope=op['kind'], next_action='An equipped host produces the requested component.')
            record['tasks'] = [{'id': op['acceptance_ref'], 'owner': op['participants'][0], 'purpose': op['purpose'],
                'input_versions': op['source_refs'], 'dependencies': [], 'allowed_actions': ['read admitted sources', 'return local bytes'],
                'return': 'Inspectable artifact with provenance and limitations', 'acceptance': 'Native recipient review remains required.',
                'state': 'waiting', 'output_refs': [], 'checks': [], 'next_action': 'Prepare and return the component.'}]
            activity['native']['work_record_ref'] = self.put_json(record, self.key(op['activity_id'], 'work-record'), activity=activity)
        # Insert before preparing so artifact grants may link back to this run.
        self.store.create(self.workspace_id, self.branch, spec, cp, activity['native'])
        self._prepare(activity, 1)
        validate(cp, 'Checkpoint')
        self.db.execute('UPDATE activity_runs SET state=?,outcome=?,checkpoint_json=?,native_json=? WHERE workspace_id=? AND activity_id=?',
            (cp['state'], cp['outcome'], encoded(cp), encoded(activity['native']), self.workspace_id, op['activity_id']))
        return self.store.get(self.workspace_id, op['activity_id'])

    def _receive(self, context, result, queue_fence=None):
        row = self.db.execute('SELECT * FROM activity_jobs WHERE workspace_id=? AND job_id=?', (self.workspace_id, result['job_id'])).fetchone()
        if not row:
            raise Fault('UNAVAILABLE')
        activity = self.activity(context, row['activity_id'])
        prepared = json.loads(row['prepared_json'])
        if prepared['handler'] != self.handler_ref(activity['spec']['kind']) or prepared['definition'] != self.catalog[activity['spec']['definition']['id']]['reference']:
            raise Fault('RECONCILE_REQUIRED')
        self.artifact_bytes_for_actor(row['actor_id'], prepared['input_ref'])
        if context.role != 'operator' and context.character_id != row['actor_id']:
            raise Fault('UNAVAILABLE')
        if result['dispatch_id'] != prepared['dispatch_id'] or result['attempt_generation'] != row['generation'] or result['input_digest'] != prepared['input_ref']['digest']:
            raise Fault('RECONCILE_REQUIRED')
        if row['result_json']:
            if json.loads(row['result_json']) != result:
                raise Fault('REQUEST_CONFLICT')
            return activity
        managed = self.runner.queue.row(row['job_id'])
        if managed:
            if queue_fence is None:
                raise Fault('RECONCILE_REQUIRED')
            try:
                self.runner.queue.assert_lease(row['job_id'], queue_fence, time.time())
            except Rejected:
                raise Fault('RECONCILE_REQUIRED') from None
        ancestor = activity
        while ancestor['parent_id']:
            ancestor = self.store.get(self.workspace_id, ancestor['parent_id'])
            if ancestor['state'] in TERMINAL or ancestor['state'] == 'paused':
                raise Fault('DEPENDENCY')
        if activity['native'].get('job_id') != row['job_id'] or activity['state'] != 'waiting' or row['state'] != 'waiting':
            raise Fault('RECONCILE_REQUIRED')
        if context.role != 'operator':
            frozen=next((r for r in prepared['read_set']['rows'] if r['table']=='activity_bindings' and r['key']==context.binding_id),None)
            binding=self.authorize(context)
            authority_digest=digest({k:binding[k] for k in binding.keys() if k!='active'})
            if (frozen and frozen['digest']!=authority_digest) or (not frozen and context.authority_epoch!=prepared['authority_epoch']):
                raise Fault('RECONCILE_REQUIRED')
        if self.revision() != prepared['expected_revision']:
            raise Fault('STALE')
        if context.role == 'worker' and queue_fence is None:
            root = activity
            while root['parent_id']:
                root = self.store.get(self.workspace_id, root['parent_id'])
            charged = self.db.execute('''WITH RECURSIVE tree(activity_id) AS (
                SELECT activity_id FROM activity_runs WHERE workspace_id=? AND activity_id=?
                UNION ALL SELECT a.activity_id FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)
                SELECT count(*) FROM activity_jobs j JOIN tree t ON j.activity_id=t.activity_id
                WHERE j.workspace_id=? AND j.result_json IS NOT NULL AND j.returned_by='worker'
                AND NOT EXISTS (SELECT 1 FROM activity_queue q WHERE q.job_id=j.job_id) ''',
                (self.workspace_id, root['activity_id'], self.workspace_id, self.workspace_id)).fetchone()[0]
            budget = self.db.execute('SELECT starts FROM activity_queue_roots WHERE workspace_id=? AND root_id=?',
                (self.workspace_id, root['activity_id'])).fetchone()
            if charged + (budget['starts'] if budget else 0) >= 4:
                raise Fault('BUDGET')
        if result['effect_refs'] or result['status'] == 'uncertain':
            raise Fault('RECONCILE_REQUIRED')
        if len(result['output_refs']) > 6:
            raise Fault('BUDGET')
        for ref in result['output_refs'] + result['tool_receipt_refs']:
            self.artifact_bytes(context, ref)
        handler = self.handlers[activity['spec']['kind']]
        if self.catalog[activity['spec']['definition']['id']]['handler'] == 'text_work':
            self.text_sources(activity['spec'], self.text_input_sources(activity, prepared))
            self.text_outputs(activity, prepared, result, queue_fence)
        cp, old_version = activity['checkpoint'], activity['version']
        if result['status'] == 'returned':
            proposal = handler.receive(self, activity, prepared, result, context)
            state, outcome, stop = handler.commit(self, activity, prepared, proposal, context)
        else:
            state, outcome, stop = ('cancelled' if result['status'] == 'cancelled' else 'failed'), 'unresolved', True
            if hasattr(handler, 'end') and 'ending' in self.catalog[activity['spec']['definition']['id']].get('encounter', {}):
                if result['status'] == 'cancelled':
                    handler.end(self, activity, context, result['job_id'] + ':cancelled')
                else:
                    # A failed controller attempt has made no participant
                    # decision. Keep the real pending geometry/cost for an
                    # explicit fresh resume or callable cancellation.
                    state = 'reconciling'
        self.db.execute('UPDATE activity_jobs SET state=?,version=version+1,result_json=?,returned_by=? WHERE job_id=?',
                        ('failed' if result['status'] == 'failed' else state if state in TERMINAL else 'finished', encoded(result), context.role, row['job_id']))
        for ref in result['output_refs']:
            for actor in activity['spec']['participants']:
                self.grant(ref, 'character:' + actor, activity['activity_id'])
            if activity['parent_id']:
                parent = self.store.get(self.workspace_id, activity['parent_id'])
                for actor in parent['spec']['participants']:
                    self.grant(ref, 'character:' + actor, activity['activity_id'])
        self.db.execute('DELETE FROM activity_staging WHERE job_id=?', (row['job_id'],))
        cp.update(state=state, outcome=outcome, activity_version=old_version + 1, job_version=row['version'] + 1,
            next={'actor': 'recipient' if state == 'finished' else 'operator', 'operation': 'artifact.read' if state == 'finished' else 'activity.resume',
                  'condition': 'A returned component does not automatically close its parent.'}, resume_condition='Explicit continuation is required.')
        if self.catalog[activity['spec']['definition']['id']]['handler'] == 'encounter':
            # Submitted replies remain in the job audit. Recipient/parent
            # returns contain accepted native consequences, not proposals or
            # another chooser's private prepared-context dependencies.
            cp['result_refs'] = activity['native'].get('accepted_result_refs', [])
        if state == 'waiting' and not stop:
            self._prepare(activity, old_version + 1)
        self.store.update(self.workspace_id, activity['activity_id'], old_version, cp, activity['native'])
        if state in TERMINAL and activity['parent_id']:
            self.db.execute("INSERT OR IGNORE INTO activity_outbox VALUES(?,?,?,?,?,'pending')",
                (self.workspace_id, activity['parent_id'], activity['activity_id'], cp['activity_version'], encoded({'outcome': outcome, 'result_refs': cp['result_refs']})))
        return self.store.get(self.workspace_id, activity['activity_id'])

    def _end_descendants(self, context, parent_id, request_id):
        """Cancel opted-in native child episodes before revoking their hosts."""
        rows = self.db.execute('''WITH RECURSIVE tree(activity_id,depth) AS (
            SELECT activity_id,1 FROM activity_runs WHERE workspace_id=? AND parent_id=?
            UNION ALL SELECT a.activity_id,t.depth+1 FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)
            SELECT activity_id FROM tree ORDER BY depth DESC,activity_id''',
            (self.workspace_id, parent_id, self.workspace_id)).fetchall()
        for row in rows:
            child = self.store.get(self.workspace_id, row[0])
            handler = self.handlers[child['spec']['kind']]
            if child['state'] in TERMINAL or not hasattr(handler, 'end'):
                continue
            if not handler.end(self, child, context, self.key(request_id, child['activity_id'])):
                continue
            version, cp = child['version'], child['checkpoint']
            cp.update(state='cancelled', outcome='unresolved', activity_version=version + 1,
                next={'actor': 'recipient', 'operation': 'artifact.read',
                    'condition': 'The parent was cancelled; accepted child costs and results remain.'})
            self.db.execute("UPDATE activity_jobs SET state='cancelled',version=version+1 WHERE job_id=? AND state='waiting'", (child['native'].get('job_id'),))
            self.db.execute('DELETE FROM activity_staging WHERE job_id=?', (child['native'].get('job_id'),))
            self.store.update(self.workspace_id, child['activity_id'], version, cp, child['native'])
            self.db.execute("INSERT OR IGNORE INTO activity_outbox VALUES(?,?,?,?,?,'pending')",
                (self.workspace_id, child['parent_id'], child['activity_id'], version + 1,
                 encoded({'outcome': 'unresolved', 'result_refs': cp['result_refs']})))

    def register_stage(self, context, fd, job_id, media_type, output_root):
        """Trusted host adapter supplies an actual regular-file FD, not a path command."""
        grant_row = self.authorize(context)
        if 'artifact.submit' not in json.loads(grant_row['grants_json']):
            raise Fault('UNAVAILABLE')
        row = self.db.execute('SELECT * FROM activity_jobs WHERE workspace_id=? AND job_id=?', (self.workspace_id, job_id)).fetchone()
        if not row:
            raise Fault('UNAVAILABLE')
        activity = self.activity(context, row['activity_id'])
        if self.runner.queue.row(job_id):
            raise Fault('RECONCILE_REQUIRED')
        if activity['state'] != 'waiting' or activity['native'].get('job_id') != job_id or (context.role != 'operator' and row['actor_id'] != context.character_id):
            raise Fault('UNAVAILABLE')
        if not isinstance(media_type, str) or not 0 < len(media_type) <= 128:
            raise Fault('INVALID')
        staged = self.db.execute('SELECT count(*),coalesce(sum(size),0) FROM activity_staging WHERE job_id=?', (job_id,)).fetchone()
        if staged[0] >= 8 or staged[1] >= 32000000 or row['state'] != 'waiting':
            raise Fault('BUDGET')
        try:
            path = Path(os.readlink('/proc/self/fd/' + str(fd)))
            relative = path.relative_to(output_root)
            if path.is_symlink() or any(p.is_symlink() for p in [path] + list(path.parents) if p != output_root.parent):
                raise Fault('UNAVAILABLE')
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 10000000 or before.st_size < 0:
                raise Fault('BUDGET')
            os.lseek(fd, 0, os.SEEK_SET)
            chunks, size = [], 0
            while True:
                block = os.read(fd, 262144)
                if not block:
                    break
                chunks.append(block); size += len(block)
                if size > 10000000:
                    raise Fault('BUDGET')
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or size != before.st_size:
                raise Fault('RECONCILE_REQUIRED')
            if size + staged[1] > 32000000 or shutil.disk_usage(self.root).free < 1073741824:
                raise Fault('BUDGET')
        except (OSError, ValueError):
            raise Fault('UNAVAILABLE') from None
        blob = b''.join(chunks); sha = hashlib.sha256(blob).hexdigest(); token = 'staging:' + uuid4().hex
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO activity_staging VALUES(?,?,?,?,?,?,?,?,0)',
                (token, context.binding_id, job_id, row['generation'], sha, len(blob), media_type, blob))
        return {'staging_ref': token, 'digest': sha, 'bytes': len(blob), 'media_type': media_type}

    def _submit(self, context, op):
        row = self.db.execute('SELECT * FROM activity_staging WHERE staging_ref=? AND binding_id=?', (op['staging_ref'], context.binding_id)).fetchone()
        if not row or row['consumed']:
            raise Fault('UNAVAILABLE')
        job = self.db.execute('SELECT * FROM activity_jobs WHERE job_id=?', (row['job_id'],)).fetchone()
        activity = self.activity(context, job['activity_id'])
        if self.runner.queue.row(job['job_id']):
            raise Fault('RECONCILE_REQUIRED')
        if activity['native'].get('job_id') != job['job_id'] or activity['state'] != 'waiting' or row['generation'] != job['generation']:
            raise Fault('UNAVAILABLE')
        if (op['digest'], op['bytes'], op['media_type']) != (row['digest'], row['size'], row['media_type']):
            raise Fault('INVALID')
        ref = self.put(bytes(row['content']), row['media_type'], self.key(row['staging_ref'], 'admit'),
            principals=[context.principal_id], activity=None,
            source_refs_override=activity['spec']['source_refs'] + [json.loads(job['prepared_json'])['input_ref']])
        self.db.execute('UPDATE activity_artifact_grants SET activity_id=? WHERE artifact_id=? AND principal_id=? AND workspace_id=?',
                        (activity['activity_id'], ref['id'], context.principal_id, self.workspace_id))
        self.db.execute('UPDATE activity_staging SET consumed=1 WHERE staging_ref=?', (row['staging_ref'],))
        return self.artifact_view(context, ref)

    def _view(self, context, op, previous_return=None):
        after = None
        if op['cursor']:
            previous = self.cursors.get(op['cursor'])
            scope = (context.principal_id, context.authority_epoch, context.binding_id)
            if (not isinstance(previous, tuple) or len(previous) != 5
                    or previous[:3] != scope or previous[3] < time.time()):
                raise Fault('UNAVAILABLE')
            after = previous[4]
        try:
            selected = self.store.page(self.workspace_id, after=after, limit=op['limit'] + 1,
                character_id=None if context.role == 'operator' else context.character_id,
                root_activity_id=context.activity_id if context.role == 'worker' else None)
        except Rejected:
            raise Fault('UNAVAILABLE') from None
        page = selected[:op['limit']]
        cursor = None
        has_more = len(selected) > len(page)
        if previous_return is not None:
            cursor = previous_return.get('cursor')
            if has_more != (cursor is not None):
                raise Fault('UNAVAILABLE')
            if cursor is not None:
                issued = self.cursors.get(cursor)
                if (not isinstance(issued, tuple) or len(issued) != 5
                        or issued[:3] != (context.principal_id, context.authority_epoch, context.binding_id)
                        or issued[3] < time.time() or issued[4] != page[-1]['activity_id']):
                    raise Fault('UNAVAILABLE')
        elif has_more:
            cursor = 'cursor:' + uuid4().hex
            self.cursors[cursor] = (context.principal_id, context.authority_epoch,
                                   context.binding_id, time.time() + 60, page[-1]['activity_id'])
        actor = context.character_id or 'visitor'
        records = self.situation.visible(actor)
        situation, _ = self.situation.snapshot(actor, records=records, activities=page)
        source_refs = []
        for row in self.db.execute('SELECT artifact_id,digest FROM activity_artifact_grants WHERE workspace_id=? AND principal_id=? AND activity_id IS NULL ORDER BY artifact_id', (self.workspace_id, context.principal_id)):
            ref = {'id': row[0], 'version': 1, 'digest': row[1]}
            try:
                self.authorize_artifact(context, ref)
            except Fault:
                continue
            source_refs.append(ref)
            if len(source_refs) == 16:break
        builtin = definitions()
        if context.role != 'operator' and context.character_id not in ('visitor','keeper'):
            builtin = [d for d in builtin if d['participants'] is None]
        available = self.content_sets.available(context, limit=32)['definitions']
        local_refs = [d['reference'] for d in builtin] + [d['reference'] for d in available]
        local_refs = list({(d['id'],d['version'],d['digest']):d for d in local_refs}.values())[:32]
        return {'kind': 'workspace', 'workspace_id': self.workspace_id, 'branch': self.branch, 'revision': self.revision(),
            'character_id': context.character_id, 'location': situation['place']['name'], 'description': situation['place']['description'],
            'situation': situation, 'recent_turns': situation['recent_turns'], 'more_turns': situation['more_turns'],
            'activities': [{'activity_id': a['activity_id'], 'title': self.catalog[a['spec']['definition']['id']]['title'], 'kind': a['spec']['kind'],
                'state': a['state'], 'outcome': a['outcome'], 'parent_id': a['parent_id'], 'active_actor': a['native'].get('actor') if a['state'] == 'waiting' and a['native'].get('actor') in records else None} for a in page],
            'cursor': cursor, 'definition_refs': local_refs, 'source_refs': source_refs,
            'atlas_region_ids': self.atlas.region_ids(actor,records)}

    def handle(self, context, request):
        request_id = request.get('request_id', 'invalid') if isinstance(request, dict) else 'invalid'
        if not isinstance(request_id, str) or not 0 < len(request_id) <= 128:
            request_id = 'invalid'
        name = None
        try:
            validate(request, 'Command'); binding = self.authorize(context)
            if request['workspace_id'] != self.workspace_id or request['branch'] != self.branch or context.workspace_id != self.workspace_id:
                raise Fault('UNAVAILABLE')
            op = request['operation']; name = op['name']
            if name not in OPERATIONS:
                raise Fault('UNSUPPORTED')
            if name not in json.loads(binding['grants_json']):
                raise Fault('UNAVAILABLE')
            sha = digest({'binding': context.binding_id, 'principal': context.principal_id, 'command': request})
            # File IO/extraction is bounded and completed before opening a UoW.
            intake_files = None
            reconciliation = None
            content_blob = None
            if name == 'job.reconcile':
                prior = self.db.execute('SELECT 1 FROM activity_messages WHERE workspace_id=? AND principal_id=? AND request_id=?',
                    (self.workspace_id, context.principal_id, request_id)).fetchone()
                if prior is None:
                    if request['expected_revision'] != self.revision():
                        raise Fault('STALE')
                    reconciliation = self.runner.prepare_reconciliation(context,
                        self.activity(context, op['activity_id']), op.get('disposition', 'discard'))
            if name == 'content.prepare':
                if context.role != 'operator': raise Fault('UNAVAILABLE')
                prior = self.db.execute('SELECT 1 FROM activity_messages WHERE workspace_id=? AND principal_id=? AND request_id=?', (self.workspace_id,context.principal_id,request_id)).fetchone()
                if prior is None:
                    if request['expected_revision'] != self.revision(): raise Fault('STALE')
                    from .intake import _read_at
                    content_blob = _read_at(self.root/'staging'/hashlib.sha256(context.binding_id.encode()).hexdigest(),op['relative_path'])
            if name == 'intake.admit':
                old = self.db.execute('SELECT 1 FROM activity_messages WHERE workspace_id=? AND principal_id=? AND request_id=?',
                    (self.workspace_id, context.principal_id, request_id)).fetchone()
                if old is None:
                    if request['expected_revision'] != self.revision():
                        raise Fault('STALE')
                    intake_files = self.intake.prepare(context, op)
            with UnitOfWork(self.db):
                old = self.db.execute('SELECT * FROM activity_messages WHERE workspace_id=? AND principal_id=? AND request_id=?', (self.workspace_id, context.principal_id, request_id)).fetchone()
                if name == 'artifact.fetch':
                    token = self.transfers.get(op['transfer_ref'])
                    if not token or token[:2] != (context.principal_id, context.authority_epoch) or token[2] != op['reference'] or token[3] <= time.time():
                        raise Fault('UNAVAILABLE')
                if old:
                    if old['request_digest'] != sha:
                        raise Fault('REQUEST_CONFLICT')
                    result = json.loads(old['receipt_json'])
                    for ref in result['result_refs']:
                        self.artifact_bytes(context, ref)
                    if name == 'artifact.read':
                        self.artifact_bytes(context, op['reference'])
                    if name.startswith('activity.') and name not in ('activity.start', 'activity.receive'):
                        self.activity(context, op['activity_id'])
                    if name == 'workspace.view' and digest(result['return']) != digest(self._view(context, op, previous_return=result['return'])):
                        raise Fault('UNAVAILABLE')
                    if name == 'resource.profile' and digest(result['return']) != digest(self._resource_view(context, op, request_id)):
                        raise Fault('UNAVAILABLE')
                    if name in CONTEST_READS | CONTEST_WRITES:
                        self.exhibitions.reauthorize_replay(context, op, result['return'])
                    if name in PROPERTY_READS | PROPERTY_WRITES:
                        self.properties.reauthorize_replay(context, op, result['return'])
                    if name in WORLD_READS | WORLD_WRITES:self.causality.view(context, op['root_id'])
                    if name in EXTENSION_READS | EXTENSION_WRITES:self.extensions.operator(context)
                    if name in CONTENT_WRITES | {'content.preview'} and context.role != 'operator':raise Fault('UNAVAILABLE')
                    if name == 'content.available' and digest(result['return']) != digest(self.content_sets.available(context,op['limit'],op['cursor'])):raise Fault('UNAVAILABLE')
                    if name == 'atlas.view' and digest(result['return']) != digest(self.atlas.view(context,op)):raise Fault('UNAVAILABLE')
                    result['replayed'] = True
                    return result
                before = self.revision()
                if name not in READS and request['expected_revision'] != before:
                    raise Fault('STALE')
                activity = None
                view = None
                if name == 'doctor':
                    lock_path = files('samsara').joinpath('data/engine-lock.json')
                    engine_ref = json.loads(lock_path.read_text())['reference']
                    view = {'kind': 'doctor', 'protocol': PROTOCOL, 'engine_ref': engine_ref,
                            'supported_operations': sorted(OPERATIONS), 'host_status': 'not_tested'}
                elif name == 'workspace.view':
                    view = self._view(context, op)
                elif name in CONTEST_READS | CONTEST_WRITES:
                    if name == 'contest.open':
                        value = self.exhibitions.open(context, op['activation_ref'], op['contest_id'], request_id)
                    elif name == 'contest.consent':
                        value = self.exhibitions.consent(context, op['contest_id'], op['choice'], request_id)
                    elif name == 'contest.begin':
                        value = self.exhibitions.begin(context, op['contest_id'], op['activity_id'])
                    elif name == 'contest.settle':
                        value = self.exhibitions.settle(context, op['contest_id'], request_id)
                    else:
                        value = self.exhibitions.inspect(context, op['contest_id'])
                    details = encoded(value)
                    if len(details.encode('utf-8')) > 200000: raise Fault('BUDGET')
                    view = {'kind':'contest','operation':name,'details':details}
                elif name == 'content.prepare':
                    ref = self.content_sets.prepare(context,op,content_blob,request_id)
                    view = {'kind':'content_preparation','preparation_ref':ref}
                elif name == 'content.preview':
                    view = self._content_view(name,self.content_sets.preview(context,op['preparation_ref']))
                elif name == 'content.activate':
                    value = self.content_sets.activate(context,op['preparation_ref'],op['actor_admissions'],request_id)
                    self._reload_content()
                    view = self._content_view(name,value)
                elif name == 'content.available':
                    view = self.content_sets.available(context,op['limit'],op['cursor'])
                elif name == 'atlas.view':
                    view = self.atlas.view(context,op)
                elif name == 'equipment.release':
                    activity = self._start(context,self.equipment.prepare(context,op,request_id))
                elif name == 'atlas.journey':
                    activity = self._start(context,self.atlas.prepare_journey(context,op,request_id))
                elif name == 'practice.account':
                    view = self.practice.account(context, op, request_id)
                elif name == 'intake.admit':
                    view = self.intake.admit(context, op, intake_files, request_id)
                elif name == 'intake.status':
                    view = self.intake.view(context, op['assignment_id'], op['revision'])
                elif name in ('job.enqueue', 'job.status', 'job.reconcile'):
                    activity = self.activity(context, op['activity_id'])
                    if name == 'job.enqueue':
                        view = self.runner.enqueue(context, activity, op['recipe'], op['parameters'], op['max_seconds'])
                    elif name == 'job.reconcile':
                        view = self.runner.reconcile(context, activity, op.get('disposition', 'discard'), reconciliation)
                    else:
                        view = self.runner.view(context, activity)
                    activity = None
                elif name == 'property.catalog':
                    view = self.properties.catalog(context)
                elif name == 'property.select':
                    view = self.properties.select(context, op['selector'])
                elif name == 'property.inspect':
                    view = self.properties.inspect(context, op['entity_id'], op['property_id'], op['definition_version'])
                elif name == 'change.prepare':
                    view = self.properties.prepare(context, op)
                elif name == 'change.preview':
                    view = self.properties.change_view(context, op['change_id'], op['digest'])
                elif name == 'change.apply':
                    view = self.properties.apply(context, op)
                elif name == 'change.withdraw':
                    view = self.properties.withdraw(context, op)
                elif name == 'support.use':
                    view = self.properties.support(context, op, request_id)
                elif name == 'support.status':
                    view = self.properties.support_view(context, op['support_id'])
                elif name == 'support.release':
                    view = self.properties.release(context, op['support_id'])
                elif name == 'clock.advance':
                    view = self.properties.advance(context, op, request_id)
                elif name == 'world.signal':
                    view = self.causality.signal(context, op)
                elif name == 'world.step':
                    view = self.causality.step(context, op)
                elif name == 'world.resume':
                    view = self.causality.resume(context, op)
                elif name == 'world.status':
                    view = self.causality.view(context, op['root_id'])
                elif name == 'extension.catalog':
                    view = self.extensions.catalog(context,op['version'])
                elif name == 'extension.prepare':
                    view = self.extensions.prepare(context,op)
                elif name in EXTENSION_READS | EXTENSION_WRITES:
                    view = self.extensions.control(context,op)
                elif name in RESOURCE_OPERATIONS:
                    view = self._resource_view(context, op, request_id)
                elif name == 'activity.start':
                    activity = self._start(context, op)
                elif name == 'activity.receive':
                    activity = self._receive(context, op['result'])
                elif name == 'activity.status':
                    activity = self.activity(context, op['activity_id'])
                elif name in ('activity.pause', 'activity.resume', 'activity.cancel'):
                    activity = self.activity(context, op['activity_id'])
                    if context.role == 'worker' and context.character_id != activity['native'].get('actor'):
                        raise Fault('UNAVAILABLE')
                    if activity['state'] in TERMINAL:
                        raise Fault('DEPENDENCY')
                    if name == 'activity.resume':
                        self._resource_gate('check_resume', activity['activity_id'])
                    elif name == 'activity.pause':
                        self._resource_gate('check_pause', activity['activity_id'])
                    version, cp = activity['version'], activity['checkpoint']
                    cp['activity_version'] = version + 1
                    self.db.execute("UPDATE activity_jobs SET state='cancelled',version=version+1 WHERE job_id=? AND state='waiting'", (activity['native'].get('job_id'),))
                    self.db.execute('DELETE FROM activity_staging WHERE job_id=?', (activity['native'].get('job_id'),))
                    if name == 'activity.resume':
                        managed = self.runner.queue.row(activity['native'].get('job_id'))
                        if managed and managed['state'] in ('running','reconciling'):
                            raise Fault('RECONCILE_REQUIRED')
                        if managed and managed['state'] in ('queued','paused'):
                            self.runner.discard_prepared(managed['job_id'],'explicit reprepare')
                        self._prepare(activity, version + 1)
                    else:
                        self.runner.control(activity['activity_id'], 'pause' if name == 'activity.pause' else 'cancel')
                        if name == 'activity.cancel':
                            self._end_descendants(context, activity['activity_id'], request_id)
                            handler = self.handlers[activity['spec']['kind']]
                            if hasattr(handler, 'end'):
                                ended = handler.end(self, activity, context, request_id)
                                if ended and activity['parent_id']:
                                    self.db.execute('INSERT OR REPLACE INTO activity_outbox VALUES(?,?,?,?,?,?)',
                                        (self.workspace_id, activity['parent_id'], activity['activity_id'], version + 1,
                                         encoded({'outcome': 'unresolved', 'result_refs': cp['result_refs']}), 'pending'))
                            self.db.execute('''WITH RECURSIVE tree(activity_id) AS (
                                SELECT activity_id FROM activity_runs WHERE workspace_id=? AND activity_id=?
                                UNION ALL SELECT a.activity_id FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)
                                UPDATE activity_bindings SET active=0,authority_epoch=authority_epoch+1
                                WHERE workspace_id=? AND role='worker' AND activity_id IN (SELECT activity_id FROM tree)''',
                                (self.workspace_id,activity['activity_id'],self.workspace_id,self.workspace_id))
                        cp.update(state='paused' if name == 'activity.pause' else 'cancelled',
                            next={'actor': 'operator', 'operation': 'activity.resume' if name == 'activity.pause' else 'inspect', 'condition': 'Accepted prior world events remain recorded.'})
                    self.store.update(self.workspace_id, activity['activity_id'], version, cp, activity['native'])
                    activity = self.store.get(self.workspace_id, activity['activity_id'])
                elif name == 'artifact.submit':
                    view = self._submit(context, op)
                elif name == 'artifact.read':
                    view = self.artifact_view(context, op['reference'])
                elif name == 'artifact.fetch':
                    token = self.transfers.get(op['transfer_ref'])
                    if not token or token[:2] != (context.principal_id, context.authority_epoch) or token[2] != op['reference'] or token[3] <= time.time():
                        raise Fault('UNAVAILABLE')
                    blob = self.artifact_bytes(context, op['reference'])
                    if op['offset'] > len(blob):
                        raise Fault('INVALID')
                    chunk = blob[op['offset']:op['offset'] + op['max_bytes']]
                    view = {'kind': 'artifact_chunk', 'reference': op['reference'], 'offset': op['offset'], 'total_bytes': len(blob), 'bytes': len(chunk),
                        'content_base64': base64.b64encode(chunk).decode(), 'chunk_digest': hashlib.sha256(chunk).hexdigest(),
                        'eof': op['offset'] + len(chunk) == len(blob)}
                if self.revision() != before:
                    self.properties.reconcile_supports(context, request_id)
                if activity:
                    view = self._checkpoint_view(context, activity)
                cp = view['checkpoint'] if view and view['kind'] == 'activity' else None
                refs = ([view['output_ref']] if view['output_ref'] else []) if view and view['kind'] == 'job' else cp['result_refs'] if cp else [view['reference']] if view and view['kind'] in ('artifact', 'artifact_chunk') else []
                if view and view['kind'] == 'intake':
                    refs = [view['manifest_ref']] + view['source_refs']
                if view and view['kind'] in ('property', 'change', 'support'):
                    refs = [view[{'property':'read_set_ref','change':'visible_diff_ref','support':'trace_ref'}[view['kind']]]]
                if view and view['kind']=='causal':refs=[x['trace_ref'] for x in view['deliveries'] if x['trace_ref']]
                if view and view['kind']=='extension':refs=[view['preview_ref'],view['ending_capsule_ref']]+([view['ending_trace_ref']] if view['ending_trace_ref'] else [])
                if view and view['kind']=='practice_account':refs=[view['account_ref']]
                if view and view['kind']=='content_preparation':refs=[view['preparation_ref']]
                if view and view['kind']=='contest':
                    details = json.loads(view['details'])
                    refs = [details['terms_ref']] + ([details['settlement_ref']] if 'settlement_ref' in details else [])  # Normal artifacts only.
                result = {'protocol': PROTOCOL, 'request_id': request_id, 'receipt_id': self.key(context.principal_id, request_id, 'receipt'),
                    'replayed': False, 'revision_before': before, 'revision_after': self.revision(), 'activity_version': cp['activity_version'] if cp else 0,
                    'state': cp['state'] if cp else 'finished', 'outcome': cp['outcome'] if cp else 'not_applicable', 'result_refs': refs,
                    'pending_refs': [cp['job_id']] if cp and cp['state'] == 'waiting' else [],
                    'next': cp['next'] if cp else {'actor': 'none', 'operation': 'none', 'condition': 'Projection was stale.' if request['expected_revision'] != before else ''},
                    'return': view}
                validate(result, 'Result'); frame(result)
                self.db.execute('INSERT INTO activity_messages VALUES(?,?,?,?,?,?)', (self.workspace_id, context.principal_id, request_id, context.binding_id, sha, encoded(result)))
                return result
        except Fault as exc:
            if name in CONTENT_WRITES | ATLAS_WRITES:
                self._reload_content()
            return error(request_id, exc.code)
        except Rejected:
            if name in CONTENT_WRITES | ATLAS_WRITES:
                self._reload_content()
            return error(request_id, 'INVALID')
        except Exception:
            if name in CONTENT_WRITES | ATLAS_WRITES:
                self._reload_content()
            with (self.root / 'owner-errors.log').open('a') as log:
                traceback.print_exc(file=log)
            return error(request_id, 'INTERNAL')
