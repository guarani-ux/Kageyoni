"""Explicit synthetic content admission; no executable discovery or new store.

Carrier bytes remain owner/operator-only. Participant discovery is computed
from current visible local records, never the full carrier identity or count.
"""
from copy import deepcopy
import hashlib
from importlib.resources import files
import json
import math

from kageyoni.engine import Rejected
from kageyoni.model import DOMAINS
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.world import _validate, _expand
from .protocol import Fault, digest, encoded, runtime_fingerprint

PREFIX = 'synthetic:f1:'
KIND = 'samsara_content'
ANCHORS = {'visitor': 'character', 'keeper': 'character', 'studio': 'location'}


def require(condition, code='INVALID'):
    if not condition:
        raise Fault(code)


def text(value, limit=2048):
    require(isinstance(value, str) and 0 < len(value) <= limit and bool(value.strip()))


def integer(value, minimum=1, maximum=100000):
    require(type(value) is int and minimum <= value <= maximum)


def shape(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional))


def parse(blob):
    require(type(blob) is bytes and 0 < len(blob) <= 10000000, 'BUDGET')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def bad(_):
        raise Fault('INVALID')
    try:
        value = json.loads(blob.decode('utf-8', errors='strict'),
                           object_pairs_hook=pairs, parse_constant=bad)
    except (ValueError, UnicodeError, RecursionError):
        raise Fault('INVALID') from None
    def depth(item, level=0):
        require(level <= 32)
        if isinstance(item, dict):
            for k, v in item.items():
                text(k, 1024)
                depth(v, level + 1)
        elif isinstance(item, list):
            for v in item:
                depth(v, level + 1)
        elif type(item) is float:
            require(math.isfinite(item))
    depth(value)
    return value


def validate_relational_uniqueness(records, existing=()):
    """Shared D6/F3 preflight; activation still uses native atomic constraints."""
    constrained = list(records) + list(existing)
    indexes = [('loadout', ('item',), False),
               ('loadout', ('holder', 'slot'), True),
               ('participation', ('scene', 'character'), False),
               ('capability', ('character', 'ability'), False)]
    for domain, keys, equipped_only in indexes:
        entries = set()
        for record in constrained:
            if record['domain'] != domain or (equipped_only and record['data'].get('equipped') != 1):
                continue
            key = tuple(record['data'].get(field) for field in keys)
            if None in key:
                continue
            require(key not in entries, 'CONFLICT')
            entries.add(key)


class ContentSets:
    def __init__(self, owner):
        self.app, self.engine, self.db = owner, owner.engine, owner.db
        self.sets, self.definitions, self.actors = {}, {}, set()
        from .exhibition_admission import ExhibitionAdmission
        self.exhibition_admission = ExhibitionAdmission(owner)

    def operator(self, context):
        self.app.authorize(context)
        require(context.role == 'operator', 'UNAVAILABLE')

    def pins(self):
        names = [('samsara', 'contentsets.py'), ('samsara', 'protocol.py'),
                 ('kageyoni', 'engine.py'), ('kageyoni', 'model.py'),
                 ('kageyoni', 'workspaces/world.py'),
                 ('kageyoni', 'contests.py'), ('kageyoni', 'data/migration_035.sql'),
                 ('samsara', 'exhibition_profiles.py'),
                 ('samsara', 'exhibition_admission.py'), ('samsara', 'practice.py'),
                 ('samsara', 'application.py'), ('samsara', 'handlers.py')]
        return {'runtime_digest': runtime_fingerprint(), 'payloads': {
            package + '/' + path: hashlib.sha256(files(package).joinpath(path).read_bytes()).hexdigest()
            for package, path in names}}

    def stable_id(self, content_id):
        return self.app.key('content-set', self.app.workspace_id, content_id)

    @staticmethod
    def compiled_spec(encounter):
        """Pin continuing physical presence in the authoritative native spec.

        Leaving does not reserve a whole ordinary-life episode. A later return
        can make the physical action available again. Only a bounded declined
        exit can remain remote: personal testimony and the episode's already
        declared cleanup, never resource, equipment or objective effects.
        """
        spec = _validate(encounter['spec'])
        ending_changes = spec.get('ending', {}).get('changes', [])
        for action in spec['actions'].values():
            terminal = spec['states'].get(action.get('next_state'), {})
            remote_exit = (action['kind'] == 'event'
                and terminal.get('phase') in ('completed', 'failed')
                and terminal.get('outcome') == 'not_achieved'
                and not any(action.get(k) for k in ('resolve_loops', 'detach_loops', 'cancel_loops'))
                and not action['payload'].get('observations'))
            for change in action['payload'].get('changes', []):
                own_report = (change.get('op') == 'create'
                    and change.get('domain') == 'historical_account'
                    and isinstance(change.get('id'), dict)
                    and set(change['id']) == {'$encounter'}
                    and change.get('data', {}).get('author') == {'$role': action['actor_role']}
                    and change.get('status') in ('reported', 'proposed'))
                own_cleanup = (change.get('op') == 'patch'
                    and isinstance(change.get('id'), dict)
                    and set(change['id']) == {'$encounter'}
                    and change in ending_changes)
                remote_exit = remote_exit and (own_report or own_cleanup)
            if not remote_exit:
                for role in spec['roles']:
                    requirement = {'record_id': {'$role': role}, 'field': 'location',
                                   'equals': encounter['site_id']}
                    if requirement not in action['requirements']:
                        action['requirements'].append(requirement)
        return _validate(spec)

    @staticmethod
    def wrapper(encounter):
        binding = encounter['binding']
        value = {'id': encounter['id'], 'version': encounter['version'],
                 'title': encounter['spec']['title'], 'kind': {'combat':'battle', 'social':'life',
                     'training_craft':'life', 'initiative':'life', 'equipment':'life'}.get(encounter['kind'], encounter['kind']),
                 'handler': 'encounter',
                 'participants': [binding[role] for role in encounter['spec']['roles']],
                 'start_location': encounter['site_id'], 'role_bindings': deepcopy(binding),
                 'encounter': ContentSets.compiled_spec(encounter)}
        if encounter.get('recovery', False):
            value['recovery'] = True
        value['reference'] = {'id': value['id'], 'version': value['version'], 'digest': digest(value)}
        return value

    def encounters(self, carrier):
        if carrier.get('format') == 'samsara-authored-exhibition/1':
            return self.exhibition_admission.definitions(carrier)
        return carrier['encounters']

    def validate(self, blob, *, conflicts=False, preparation_ref=None, activation=None):
        value = parse(blob)
        if isinstance(value, dict) and value.get('format') == 'samsara-authored-exhibition/1':
            return self.exhibition_admission.validate(blob, conflicts=conflicts,
                preparation_ref=preparation_ref, activation=activation)
        require(activation is None, 'DEPENDENCY')
        shape(value, ('format', 'id', 'version', 'canonical', 'provenance',
                      'native_records', 'atlas', 'encounters', 'opening_uses'))
        require(value['format'] == 'samsara-authored-region/1' and value['canonical'] is False)
        text(value['id']); require(value['id'].startswith(PREFIX))
        integer(value['version'], 1, 1000)
        require(isinstance(value['provenance'], dict) and value['provenance'].get('not_recovered_history') is True
                and value['provenance'].get('participant_authorlore') is False)
        require(isinstance(value['opening_uses'], dict))
        records = value['native_records']
        require(isinstance(records, list) and 1 <= len(records) <= 5000)
        byid = {}
        for record in records:
            shape(record, ('op', 'id', 'domain', 'data', 'status', 'visibility', 'evidence'), ('audience',))
            text(record['id']); require(record['id'].startswith(PREFIX) and record['id'] not in byid)
            require(record['op'] == 'create' and isinstance(record['data'], dict))
            record.setdefault('audience', [])
            prototype = dict(record, version=1, branch=self.app.branch, updated_event='content-validation')
            try:
                self.engine._validate_record(prototype)
            except (Rejected, KeyError, TypeError, ValueError):
                raise Fault('INVALID') from None
            if conflicts:
                require(self.engine.get(self.app.branch, record['id']) is None, 'CONFLICT')
            byid[record['id']] = record
        anchors = {rid: self.engine.get(self.app.branch, rid) for rid in ANCHORS}
        require(all(r and r['domain'] == ANCHORS[k] for k, r in anchors.items()), 'DEPENDENCY')
        pool = anchors | byid

        def references(record, pool=pool):
            for field, kind in DOMAINS[record['domain']].items():
                val = record['data'].get(field)
                if kind.startswith('ref:') and val is not None:
                    require(isinstance(val, str) and val in pool
                            and pool[val]['domain'] in kind[4:].split('|'))
            require(all(a in pool and pool[a]['domain'] == 'character' for a in record.get('audience', [])))
        for record in records:
            references(record)
            if record['domain'] == 'location':
                seen, parent = {record['id']}, record['data'].get('parent')
                while parent:
                    require(parent in pool and parent not in seen)
                    seen.add(parent); parent = pool[parent]['data'].get('parent')

        validate_relational_uniqueness(records, self.engine.state(self.app.branch) if conflicts else ())

        atlas = value['atlas']; shape(atlas, ('region', 'cells', 'routes'))
        region = atlas['region']; shape(region, ('id', 'label', 'columns', 'rows', 'clock_id'))
        require(region['columns'] == 15 and region['rows'] == 15)
        text(region['label']); require(region['id'] in byid and byid[region['id']]['domain'] == 'location')
        clock = byid.get(region['clock_id'])
        require(clock and clock['domain'] == 'clock' and clock['data'].get('unit') == 'minute'
                and type(clock['data'].get('tick')) in (int, float) and clock['data']['tick'] >= 0)
        cells = atlas['cells']; require(isinstance(cells, list) and len(cells) == 225)
        addresses, locations, developed, sites = set(), set(), set(), set()
        for cell in cells:
            shape(cell, ('address', 'location_id', 'knowledge', 'developed', 'political_refs', 'ecology_refs', 'site_ids'))
            require(isinstance(cell['address'], str) and cell['address'] not in addresses)
            addresses.add(cell['address'])
            rid = cell['location_id']; require(rid in byid and byid[rid]['domain'] == 'location' and rid not in locations)
            locations.add(rid)
            require(type(cell['developed']) is bool and cell['knowledge'] in ('known', 'unknown'))
            if cell['developed']:
                require(cell['knowledge'] == 'known' and byid[rid]['visibility'] == 'public'); developed.add(rid)
            else:
                require(cell['knowledge'] == 'unknown' and byid[rid]['visibility'] == 'gm')
            for key, domains in [('political_refs', ('political_claim', 'office', 'law', 'faction')),
                                 ('ecology_refs', ('environment', 'world_rule')),
                                 ('site_ids', ('location',))]:
                refs = cell[key]; require(isinstance(refs, list) and len(refs) == len(set(refs)))
                require((key == 'site_ids' or bool(refs)) and all(r in byid and byid[r]['domain'] in domains for r in refs))
            for site in cell['site_ids']:
                require(site not in sites and byid[site]['data'].get('parent') == rid)
                sites.add(site)
        require(addresses == {f'{c}{r}' for c in 'ABCDEFGHIJKLMNO' for r in range(1, 16)})
        require(len(developed) == 12 and len(sites) == 6)
        routes = atlas['routes']; require(isinstance(routes, list) and 1 <= len(routes) <= 2000)
        seen, edges = set(), {rid: set() for rid in developed}
        def requirement(req, candidates=pool):
            shape(req, ('record_id', 'field', 'equals'))
            record = candidates.get(req['record_id']); require(record is not None)
            kind = DOMAINS[record['domain']].get(req['field']); require(kind is not None)
            val = req['equals']
            if val is None:
                return
            if kind in ('integer', 'number'):
                require(type(val) in ((int,) if kind == 'integer' else (int, float)))
            elif kind == 'json':
                require(isinstance(val, (list, dict)))
            else:
                require(isinstance(val, str))
                if kind.startswith('enum:'): require(val in kind[5:].split('|'))
                if kind.startswith('ref:'):
                    require(val in candidates and candidates[val]['domain'] in kind[4:].split('|'))
        for route in routes:
            shape(route, ('id', 'origin', 'destination', 'bidirectional', 'access', 'duration', 'requires'))
            rid = route['id']; require(rid in byid and byid[rid]['domain'] == 'route' and rid not in seen); seen.add(rid)
            require(type(route['bidirectional']) is bool and route['origin'] != route['destination'])
            native = byid[rid]['data']
            require(all(route[k] == native.get(k) for k in ('origin', 'destination', 'access')))
            duration = route['duration']; shape(duration, ('value', 'unit', 'clock_id'))
            integer(duration['value'], 1, 100000)
            require(duration['unit'] == 'minute' and duration['clock_id'] == region['clock_id'])
            require(native.get('duration') == str(duration['value']) + ' minute')
            require(isinstance(route['requires'], list) and len(route['requires']) <= 64)
            for req in route['requires']: requirement(req)
            require(native.get('conditions', '') == (json.dumps(route['requires'], sort_keys=True) if route['requires'] else ''))
            if route['access'] == 'open' and route['origin'] in developed and route['destination'] in developed:
                edges[route['origin']].add(route['destination'])
                if route['bidirectional']: edges[route['destination']].add(route['origin'])
        reached, todo = set(), [next(iter(developed))]
        while todo:
            rid = todo.pop()
            if rid not in reached:
                reached.add(rid); todo.extend(edges[rid] - reached)
        require(reached == developed)

        encounters = value['encounters']; require(isinstance(encounters, list) and 1 <= len(encounters) <= 128)
        definition_ids = set()
        for encounter in encounters:
            shape(encounter, ('id', 'version', 'spec', 'binding', 'site_id', 'kind', 'ordinary_alternative', 'later_use'), ('qualification_limit', 'recovery'))
            require(isinstance(encounter['id'], str) and encounter['id'].startswith(PREFIX)
                    and encounter['id'] not in definition_ids); definition_ids.add(encounter['id'])
            integer(encounter['version'], 1, 1000)
            require(type(encounter.get('recovery', False)) is bool)

            require(encounter['kind'] in ('life', 'battle', 'travel', 'social', 'combat', 'training_craft', 'initiative', 'equipment') and encounter['site_id'] in sites | developed)
            try:
                spec = self.compiled_spec(encounter)
                bindings = encounter['binding']
                require(isinstance(bindings, dict) and set(bindings) == set(spec['roles']))
                if encounter.get('recovery', False):
                    require(encounter['kind'] == 'life' and len(spec['roles']) == 1)
                    require(len(bindings) == 1)
                require(len(set(bindings.values())) == len(bindings)
                        and all(a in pool and pool[a]['domain'] == 'character' for a in bindings.values()))
                expanded = _expand(spec, bindings, PREFIX + 'validation-episode')
                prototypes = deepcopy(pool)
                for act in expanded['actions'].values():
                    require(act['kind'] != 'will', 'UNSUPPORTED')
                    if act['kind'] == 'event':
                        shape(act['payload'], (), ('changes', 'observations'))
                        changes = act['payload'].get('changes', []); require(isinstance(changes, list) and len(changes) <= 256)
                        for change in changes:
                            require(change.get('op') in ('create', 'patch'), 'UNSUPPORTED')
                            if change['op'] == 'create':
                                shape(change, ('op', 'id', 'domain', 'data', 'status', 'visibility', 'evidence'), ('audience',))
                                require(isinstance(change['id'], str) and change['id'].startswith(PREFIX + 'validation-episode:'))
                                prototype = dict(change, audience=change.get('audience', []), version=1)
                                self.engine._validate_record(prototype); prototypes[change['id']] = prototype
                    elif act['kind'] == 'dialogue':
                        shape(act['payload'], ('text', 'act', 'mode', 'listener_roles'))
                        text(act['payload']['text'], 64000);text(act['payload']['act']);text(act['payload']['mode'])
                        require(isinstance(act['payload']['listener_roles'], list)
                                and all(r in bindings for r in act['payload']['listener_roles']))
                for act in expanded['actions'].values():
                    for req in act['requirements']: requirement(req, prototypes)
                    for change in act['payload'].get('changes', []):
                        if change['op'] == 'patch':
                            shape(change, ('op', 'id', 'data', 'evidence'), ('domain', 'expected_version'))
                            require(change['id'] in prototypes)
                            base = deepcopy(prototypes[change['id']]); require(isinstance(change['data'], dict))
                            if 'domain' in change: require(change['domain'] == base['domain'])
                            base['data'].update(change['data']); self.engine._validate_record(base); references(base, prototypes)
                        else:
                            references(prototypes[change['id']], prototypes)
                    observations = act['payload'].get('observations', [])
                    require(isinstance(observations, list) and len(observations) <= 256)
                    for obs in observations:
                        shape(obs, ('id', 'observer_id', 'subject_id', 'assertion', 'certainty', 'visibility'), ('audience',))
                        text(obs['id']);text(obs['assertion'], 64000);text(obs['certainty'])
                        require(obs['id'].startswith(PREFIX + 'validation-episode:'))
                        require(obs['observer_id'] in prototypes and prototypes[obs['observer_id']]['domain'] == 'character'
                                and obs['subject_id'] in prototypes)
                        require(obs['visibility'] in ('public', 'restricted', 'gm')
                                and isinstance(obs.get('audience', []), list)
                                and (obs['visibility'] != 'restricted' or bool(obs.get('audience'))))
                        require(all(a in prototypes and prototypes[a]['domain'] == 'character' for a in obs.get('audience', [])))
                old = self.db.execute('SELECT digest FROM encounter_definitions WHERE definition_id=? AND version=?',
                                      (encounter['id'], encounter['version'])).fetchone()
                if conflicts: require(old is None, 'CONFLICT')
            except (Rejected, KeyError, TypeError, ValueError):
                raise Fault('INVALID') from None
        return value

    def prepare(self, context, op, blob, request_id):
        self.operator(context)
        shape(op, ('digest', 'bytes'), ('name', 'relative_path'))
        require(type(blob) is bytes and op.get('bytes') == len(blob)
                and type(op.get('bytes')) is int and op.get('digest') == hashlib.sha256(blob).hexdigest())
        carrier = self.validate(blob)
        row = self.db.execute('SELECT source_hash FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',
                              (KIND, self.stable_id(carrier['id']), str(carrier['version']))).fetchone()
        if row: require(row['source_hash'] == op['digest'], 'CONFLICT')
        else: self.validate(blob, conflicts=True)
        with UnitOfWork(self.db):
            raw_ref = self.app.put(blob, 'application/json', self.app.key('content-raw', request_id),
                                   principals=[context.principal_id], private_viewer=context.principal_id)
            envelope = {'kind': 'content_preparation', 'raw_ref': raw_ref, 'consumer_pins': self.pins(),
                        'content_id': carrier['id'], 'version': carrier['version'],
                        'source_digest': op['digest']}
            return self.app.put_json(envelope, self.app.key('content-preparation', request_id),
                                     principals=[context.principal_id], private_viewer=context.principal_id)

    def _prepared(self, context, ref):
        self.operator(context)
        def read(reference):
            blob = self.app.artifact_bytes(context, reference)
            row = self.db.execute('SELECT viewer FROM artifacts WHERE artifact_id=? AND workspace_id=?',
                                  (reference['id'], self.app.workspace_id)).fetchone()
            require(row and row['viewer'] == context.principal_id, 'UNAVAILABLE')
            return blob
        envelope = parse(read(ref))
        shape(envelope, ('kind', 'raw_ref', 'consumer_pins', 'content_id', 'version', 'source_digest'))
        require(envelope['kind'] == 'content_preparation' and envelope['consumer_pins'] == self.pins(), 'DEPENDENCY')
        blob = read(envelope['raw_ref'])
        require(hashlib.sha256(blob).hexdigest() == envelope['source_digest'], 'DEPENDENCY')
        parsed = parse(blob)
        activation = None
        if isinstance(parsed, dict) and parsed.get('format') == 'samsara-authored-exhibition/1':
            prior = self.db.execute('SELECT locator,source_hash FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',
                (KIND, self.stable_id(envelope['content_id']), str(envelope['version']))).fetchone()
            if prior:
                require(prior['source_hash'] == envelope['source_digest'], 'DEPENDENCY')
                try: locator = json.loads(prior['locator'])
                except (ValueError, TypeError): raise Fault('DEPENDENCY') from None
                require(isinstance(locator, dict) and locator.get('preparation_ref') == ref
                    and locator.get('consumer_pins') == self.pins(), 'DEPENDENCY')
                activation = locator.get('native_activation')
                require(activation is not None, 'DEPENDENCY')
        carrier = self.validate(blob, preparation_ref=ref, activation=activation)
        require(carrier['id'] == envelope['content_id'] and carrier['version'] == envelope['version'], 'DEPENDENCY')
        return carrier, blob

    def preview(self, context, preparation_ref):
        carrier, blob = self._prepared(context, preparation_ref)
        # Inventory is trusted-operator only; no participant view calls here.
        return {'kind': 'content_preview', 'preparation_ref': preparation_ref,
                'content_id': carrier['id'], 'version': carrier['version'],
                'source_digest': hashlib.sha256(blob).hexdigest(), 'consumer_pins': self.pins(),
                'native_records': len(carrier['native_records']), 'encounters': len(self.encounters(carrier)),
                'cells': len(carrier.get('atlas', {}).get('cells', [])),
                'routes': len(carrier.get('atlas', {}).get('routes', []))}

    def activate(self, context, preparation_ref, actor_admissions, request_id):
        self.operator(context)
        with UnitOfWork(self.db):
            carrier, blob = self._prepared(context, preparation_ref)
            require(isinstance(actor_admissions, list) and len(actor_admissions) <= 64
                    and all(isinstance(a, str) for a in actor_admissions)
                    and len(actor_admissions) == len(set(actor_admissions)))
            records = {r['id']: r for r in carrier['native_records']}
            exhibition = carrier['format'] == 'samsara-authored-exhibition/1'
            if exhibition:
                # Anchored characters are selected explicitly and still must be
                # currently visible/admissible. Actor admission is not consent.
                for ref in carrier['existing_refs']:
                    current = self.engine.get(self.app.branch, ref['id'])
                    require(current and current['domain'] == ref['domain'], 'DEPENDENCY')
                    records[ref['id']] = current
            require(all(a in records and records[a]['domain'] == 'character'
                        and (records[a]['visibility'] == 'public' or
                             (records[a]['visibility'] == 'restricted' and a in records[a]['audience']))
                        for a in actor_admissions), 'UNAVAILABLE')
            admissions = sorted(actor_admissions); sha = hashlib.sha256(blob).hexdigest()
            stable = self.stable_id(carrier['id']); version = str(carrier['version'])
            prior = self.db.execute('SELECT * FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',
                                    (KIND, stable, version)).fetchone()
            if prior:
                self.reload(); old = self.sets.get((carrier['id'], carrier['version']))
                require(old is not None and prior['source_hash'] == sha
                        and old['preparation_ref'] == preparation_ref
                        and old['actor_admissions'] == admissions, 'CONFLICT')
                return {'kind': 'content_activation', 'content_id': carrier['id'], 'version': carrier['version'],
                        'preparation_ref': preparation_ref, 'activation_ref': old['activation_ref'],
                        'actor_admissions': admissions, 'replayed': True}
            self.validate(blob, conflicts=True)
            pins = self.pins()
            expected_revision = self.app.revision()
            native_receipt = self.engine.apply({'api_version': 3, 'branch': self.app.branch,
                'request_id': self.app.key('content-activate-records', preparation_ref),
                'expected_revision': expected_revision, 'actor': 'content-operator', 'kind': 'maintenance',
                'narrative': 'Activate explicitly authored synthetic content; preserve existing anchors and all prior history.',
                'changes': carrier['native_records']})
            for encounter in self.encounters(carrier):
                self.app.services.encounters.define(encounter['id'], encounter['version'], self.compiled_spec(encounter),
                    self.app.key('content-define', preparation_ref, encounter['id'], encounter['version']), viewer=None)
            payload = {'kind': 'content_activation', 'content_id': carrier['id'], 'version': carrier['version'],
                       'preparation_ref': preparation_ref, 'source_digest': sha,
                       'actor_admissions': admissions, 'consumer_pins': pins}
            if exhibition:
                payload['native_activation'] = self.exhibition_admission.provenance(
                    carrier, preparation_ref, expected_revision, native_receipt)
            activated = self.app.put_json(payload, self.app.key('content-activation', request_id),
                                          principals=[context.principal_id], private_viewer=context.principal_id)
            locator = payload | {'activation_ref': activated}
            self.engine.register_component(KIND, stable, version, encoded(locator), status='verified',
                readers=['samsara.contentsets'], writers=['content.activate'], compatibility={'format': carrier['format']},
                source_hash=sha, declared_by='samsara.contentsets')
            require(self.engine.validate_registry()['ok'], 'DEPENDENCY')
            self.reload()
            return {'kind': 'content_activation', 'content_id': carrier['id'], 'version': carrier['version'],
                    'preparation_ref': preparation_ref, 'activation_ref': activated,
                    'actor_admissions': admissions, 'replayed': False}

    def reload(self):
        sets, definitions, actors = {}, {}, set()
        for row in self.db.execute('SELECT * FROM registry_entries WHERE kind=? ORDER BY stable_id,version', (KIND,)):
            try: locator = json.loads(row['locator'])
            except (ValueError, TypeError): raise Fault('DEPENDENCY') from None
            if not isinstance(locator, dict) or locator.get('kind') != 'content_activation':
                raise Fault('DEPENDENCY')
            # The registry namespace is workspace-specific, not a public actor inventory.
            if row['stable_id'] != self.stable_id(locator.get('content_id')):
                continue
            shape(locator, ('kind', 'content_id', 'version', 'preparation_ref', 'source_digest',
                            'actor_admissions', 'consumer_pins', 'activation_ref'), ('native_activation',))
            require(row['status'] == 'verified' and row['version'] == str(locator['version'])
                    and row['source_hash'] == locator['source_digest']
                    and locator['consumer_pins'] == self.pins(), 'DEPENDENCY')
            def raw(ref):
                require(isinstance(ref, dict) and set(ref) == {'id', 'version', 'digest'} and ref['version'] == 1, 'DEPENDENCY')
                artifact = self.db.execute('SELECT * FROM artifacts WHERE artifact_id=? AND workspace_id=?',
                                           (ref['id'], self.app.workspace_id)).fetchone()
                require(artifact and artifact['viewer'] is not None and artifact['viewer'].startswith('operator:'), 'DEPENDENCY')
                blob = bytes(artifact['content'])
                require(hashlib.sha256(blob).hexdigest() == ref['digest'] == artifact['digest']
                        and len(blob) == artifact['size'], 'DEPENDENCY')
                grants = self.db.execute('SELECT principal_id FROM activity_artifact_grants WHERE workspace_id=? AND artifact_id=?',
                                         (self.app.workspace_id, ref['id'])).fetchall()
                require(all(g['principal_id'].startswith('operator:') for g in grants), 'DEPENDENCY')
                return blob
            preparation = parse(raw(locator['preparation_ref']))
            shape(preparation, ('kind', 'raw_ref', 'consumer_pins', 'content_id', 'version', 'source_digest'))
            require(preparation['kind'] == 'content_preparation'
                    and preparation['consumer_pins'] == locator['consumer_pins']
                    and preparation['content_id'] == locator['content_id']
                    and preparation['version'] == locator['version']
                    and preparation['source_digest'] == row['source_hash'], 'DEPENDENCY')
            source = raw(preparation['raw_ref']); require(hashlib.sha256(source).hexdigest() == row['source_hash'], 'DEPENDENCY')
            source_value = parse(source)
            if isinstance(source_value, dict) and source_value.get('format') == 'samsara-authored-exhibition/1':
                require(locator.get('native_activation') is not None, 'DEPENDENCY')
            carrier = self.validate(source, preparation_ref=locator['preparation_ref'],
                                    activation=locator.get('native_activation'))
            require(carrier['id'] == locator['content_id'] and carrier['version'] == locator['version'], 'DEPENDENCY')
            receipt = parse(raw(locator['activation_ref']))
            require(receipt == {k: v for k, v in locator.items() if k != 'activation_ref'}, 'DEPENDENCY')
            admissions = locator['actor_admissions']
            characters = {r['id'] for r in carrier['native_records'] if r['domain'] == 'character'}
            if carrier['format'] == 'samsara-authored-exhibition/1':
                characters.update(r['id'] for r in carrier['existing_refs'] if r['domain'] == 'character')
            require(isinstance(admissions, list) and len(admissions) == len(set(admissions))
                    and all(a in characters for a in admissions), 'DEPENDENCY')
            for record in carrier['native_records']:
                current = self.engine.get(self.app.branch, record['id'])
                require(current and current['domain'] == record['domain'], 'DEPENDENCY')
            for encounter in self.encounters(carrier):
                native = self.db.execute('SELECT digest,spec_json FROM encounter_definitions WHERE definition_id=? AND version=?',
                                         (encounter['id'], encounter['version'])).fetchone()
                compiled = self.compiled_spec(encounter)
                require(native and native['digest'] == digest(compiled)
                        and json.loads(native['spec_json']) == compiled, 'DEPENDENCY')
                definition = self.wrapper(encounter)
                if definition['id'] in definitions:
                    require(definitions[definition['id']] == definition, 'CONFLICT')
                definitions[definition['id']] = definition
            sets[(carrier['id'], carrier['version'])] = {'carrier': carrier,
                'activation_ref': locator['activation_ref'], 'preparation_ref': locator['preparation_ref'],
                'actor_admissions': admissions}
            actors.update(admissions)
        self.sets, self.definitions, self.actors = sets, definitions, actors
        return self

    def actor_admitted(self, actor):
        if not isinstance(actor, str): return False
        self.reload()
        if actor not in ANCHORS and actor not in self.actors: return False
        record = self.engine.get(self.app.branch, actor)
        if not record or record['domain'] != 'character': return False
        return record['visibility'] == 'public' or (record['visibility'] == 'restricted' and actor in record['audience'])

    def definition(self, reference):
        self.reload()
        require(isinstance(reference, dict), 'UNAVAILABLE')
        value = self.definitions.get(reference.get('id'))
        require(value and value['reference'] == reference, 'UNAVAILABLE')
        return deepcopy(value)

    def available(self, context, limit=16, cursor=None):
        self.app.authorize(context); integer(limit, 1, 32); self.reload()
        selected = []
        operator = context.role == 'operator'
        visible = None if operator else self.app.situation.visible(context.character_id)
        location = None if operator else visible.get(context.character_id, {}).get('data', {}).get('location')
        for definition in self.definitions.values():
            if not operator:
                if (context.character_id not in definition['participants']
                        or definition['start_location'] != location or definition['start_location'] not in visible
                        or definition['encounter']['visibility'] != 'public'
                        or not all(a in visible for a in definition['participants'])):
                    continue
                # Avoid a definition digest revealing currently hidden native records
                # through an otherwise local labelled choice.
                expanded = _expand(definition['encounter'], definition['role_bindings'], PREFIX + 'visible-episode')
                needed = set()
                world_ids = {r[0] for r in self.db.execute('SELECT id FROM records WHERE branch=?', (self.app.branch,))}
                def dependencies(item):
                    if isinstance(item, str) and item in world_ids:
                        needed.add(item)
                    elif isinstance(item, dict):
                        for val in item.values(): dependencies(val)
                    elif isinstance(item, list):
                        for val in item: dependencies(val)
                dependencies(expanded)
                for action in expanded['actions'].values():
                    needed.update(q['record_id'] for q in action['requirements'])
                    for change in action['payload'].get('changes', []):
                        if change['op'] == 'patch': needed.add(change['id'])
                if any(r not in visible and not r.startswith(PREFIX + 'visible-episode:') for r in needed):
                    continue
            selected.append({k: deepcopy(definition[k]) for k in ('reference', 'title', 'kind')})
        selected.sort(key=lambda x: (x['reference']['id'], x['reference']['version']))
        identity = digest([context.principal_id, context.authority_epoch, location, selected])
        offset = 0
        if cursor is not None:
            require(isinstance(cursor, str) and cursor in self.app.cursors, 'STALE')
            saved = self.app.cursors[cursor]
            require(isinstance(saved, dict) and saved.get('content_visible_identity') == identity, 'STALE'); offset = saved['offset']
        page = selected[offset:offset + limit]; next_cursor = None
        if offset + len(page) < len(selected):
            next_cursor = self.app.key('content-visible-cursor', identity, offset + len(page))
            self.app.cursors[next_cursor] = {'content_visible_identity': identity, 'offset': offset + len(page)}
        return {'kind': 'content_available', 'definitions': page, 'cursor': next_cursor}
