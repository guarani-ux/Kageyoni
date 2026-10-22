"""Visible authored geography and ordinary native walking.

The carrier supplies a declared atlas, never an alternative world store. All
current facts and elapsed minutes belong to the existing native engine.
"""
from copy import deepcopy
import hashlib
import json
import math
import os

from kageyoni.workspaces.world import _validate
from .protocol import Fault, digest, encoded

EVIDENCE = [{'note': 'Explicit optional synthetic atlas walking; no recovered history or canonical geography.'}]


def reference(record):
    return {'id': record['id'], 'version': record['version'], 'digest': digest(record)}


class Atlas:
    def __init__(self, owner):
        self.app, self.engine, self.db = owner, owner.engine, owner.db
        self.cursors = {}

    def _records(self, context, actor=None):
        if context.role != 'operator':
            if actor is not None and actor != context.character_id:
                raise Fault('UNAVAILABLE')
            actor = context.character_id
        if actor:
            if not self.app.content_sets.actor_admitted(actor):
                raise Fault('UNAVAILABLE')
            records = self.app.situation.visible(actor)
            if records.get(actor, {}).get('domain') != 'character':
                raise Fault('UNAVAILABLE')
        elif context.role == 'operator':
            records = {r['id']: r for r in self.engine.context(self.app.branch,
                viewer=None, include_properties=False, include_processes=False)['records']}
        else:
            raise Fault('UNAVAILABLE')
        return actor, records

    def _region(self, region_id):
        values = [v['carrier'] for _, v in sorted(self.app.content_sets.sets.items())
            if v['carrier'].get('format') == 'samsara-authored-region/1'
            and v['carrier']['atlas']['region']['id'] == region_id]
        if not values:
            raise Fault('UNAVAILABLE')
        return values[-1]

    def _known(self, carrier, records, operator):
        return {c['location_id']: c for c in carrier['atlas']['cells']
            if c['location_id'] in records and records[c['location_id']]['domain'] == 'location'
            and (operator or c['knowledge'] == 'known')}

    def _route(self, carrier, route, records, known, operator):
        row = records.get(route['id'])
        if not row or row['domain'] != 'route':
            return None
        endpoints = [route['origin'], route['destination']]
        sites = {s for c in known.values() for s in c.get('site_ids', [])}
        # Explicit legacy connection is data; containment never grants travel.
        allowed = set(known) | sites | {'studio'}
        if not operator and (route['duration']['clock_id'] not in records
                or records[route['duration']['clock_id']]['domain'] != 'clock'):
            return None
        if any(e not in records or records[e]['domain'] != 'location'
               or (not operator and e not in allowed) for e in endpoints):
            return None
        if any(row['data'].get(k) != route[k] for k in ('origin', 'destination')):
            return None
        if not operator:
            for requirement in route['requires']:
                visible = records.get(requirement['record_id'])
                field = requirement['field']
                if not visible or field not in visible['data']:
                    return None
                full = self.engine.get(self.app.branch, requirement['record_id'])
                if (not full or field not in full['data']
                        or encoded(full['data'][field]) != encoded(visible['data'][field])):
                    return None
        expected_conditions = json.dumps(route['requires'], sort_keys=True) if route['requires'] else ''
        if (row['data'].get('duration') != str(route['duration']['value']) + ' minute'
                or row['data'].get('conditions', '') != expected_conditions):
            return None
        return row

    def region_ids(self, actor, records):
        """Known visible regional entry points; no carrier inventory identity."""
        own = records.get(actor)
        if (not own or own['domain'] != 'character'
                or not self.app.content_sets.actor_admitted(actor)):
            return []
        regions = set()
        for value in self.app.content_sets.sets.values():
            carrier = value['carrier']
            if carrier.get('format') != 'samsara-authored-region/1':
                continue
            identity = carrier['atlas']['region']['id']
            row = records.get(identity)
            if row and row['domain'] == 'location' and self._known(carrier, records, False):
                regions.add(identity)
        return sorted(regions)

    def project(self, actor, records):
        """Local optional walking choices, derived without advancing fiction."""
        empty = {'routes': [], 'discoveries': [], 'cues': []}
        own = records.get(actor)
        if (not own or own['domain'] != 'character'
                or not self.app.content_sets.actor_admitted(actor)):
            return empty, set()
        here = own['data'].get('location')
        routes, scope = {}, set()
        for _, value in sorted(self.app.content_sets.sets.items()):
            carrier = value['carrier']
            if carrier.get('format') != 'samsara-authored-region/1':
                continue
            known = self._known(carrier, records, False)
            for route in carrier['atlas']['routes']:
                if here == route['origin']:
                    destination = route['destination']
                elif here == route['destination'] and route['bidirectional'] is True:
                    destination = route['origin']
                else:
                    continue
                row = self._route(carrier, route, records, known, False)
                if row is None:
                    continue
                target = records[destination]
                minutes = route['duration']['value']
                routes[row['id']] = {'reference': reference(row), 'destination': reference(target),
                    'name': target['data'].get('name') or destination,
                    'access': row['data'].get('access') or 'unknown',
                    'condition': 'Declared walking time: ' + str(minutes) + ' minute' + ('' if minutes == 1 else 's') + '.'}
                scope.update((actor, here, destination, row['id'], route['duration']['clock_id']))
        return {'routes': [routes[identity] for identity in sorted(routes)][:32],
                'discoveries': [], 'cues': []}, scope

    def view(self, context, op):
        self.app.authorize(context)
        actor, records = self._records(context, op.get('actor_id'))
        carrier = self._region(op['region_id'])
        region = records.get(op['region_id'])
        if not region or region['domain'] != 'location':
            raise Fault('UNAVAILABLE')
        operator = context.role == 'operator' and actor is None
        known = self._known(carrier, records, operator)
        items = []
        for identity, cell in sorted(known.items()):
            row = records[identity]
            items.append({'kind': 'cell', 'reference': reference(row), 'address': cell['address'],
                'name': row['data'].get('name') or identity, 'knowledge': cell['knowledge']})
            for site_id in sorted(cell.get('site_ids', [])):
                site = records.get(site_id)
                if site and site['domain'] == 'location':
                    items.append({'kind': 'site', 'reference': reference(site),
                        'parent_id': identity, 'name': site['data'].get('name') or site_id})
        for route in carrier['atlas']['routes']:
            row = self._route(carrier, route, records, known, operator)
            if row:
                items.append({'kind': 'route', 'reference': reference(row),
                    'origin': row['data']['origin'], 'destination': row['data']['destination'],
                    'bidirectional': route['bidirectional'], 'access': row['data'].get('access') or 'unknown',
                    'duration': deepcopy(route['duration'])})
        items.sort(key=lambda item: (item['kind'], item['reference']['id']))
        visible_digest = digest(items)
        scope = (context.principal_id, context.authority_epoch, actor, op['region_id'], visible_digest)
        offset = 0
        if op.get('cursor'):
            token = self.cursors.get(op['cursor'])
            if not token or token[:5] != scope:
                raise Fault('UNAVAILABLE')
            offset = token[5]
        limit = op.get('limit', 32)
        if type(limit) is not int or not 1 <= limit <= 64:
            raise Fault('INVALID')
        page = items[offset:offset + limit]
        cursor = None
        if offset + limit < len(items):
            token = (*scope, offset + limit)
            cursor = 'atlas:' + digest(list(token))
            self.cursors[cursor] = token
        own = records.get(actor, {}) if actor else {}
        clock = records.get(carrier['atlas']['region']['clock_id'])
        return {'kind': 'atlas', 'region_id': op['region_id'],
            'location_id': own.get('data', {}).get('location'), 'items': page, 'cursor': cursor,
            'clock': {'reference': reference(clock), 'tick': clock['data']['tick'],
                'unit': clock['data']['unit']} if clock and clock['domain'] == 'clock' else None}

    def prepare_journey(self, context, op, request_id):
        self.app.authorize(context)
        if context.role == 'worker':
            raise Fault('UNAVAILABLE')
        if self.db.execute('SELECT 1 FROM activity_runs WHERE workspace_id=? AND activity_id=?',
                (self.app.workspace_id, op['activity_id'])).fetchone():
            raise Fault('CONFLICT')
        actor, records = self._records(context, op.get('actor_id'))
        if not actor:
            raise Fault('UNAVAILABLE')
        own = records[actor]
        origin = own['data'].get('location')
        found = []
        for _, value in sorted(self.app.content_sets.sets.items()):
            carrier = value['carrier']
            if carrier.get('format') != 'samsara-authored-region/1':
                continue
            known = self._known(carrier, records, False)
            for route in carrier['atlas']['routes']:
                if route['id'] == op['route_id']:
                    row = self._route(carrier, route, records, known, False)
                    if row:
                        found.append((carrier, route, row))
        if not found:
            raise Fault('UNAVAILABLE')
        carrier, route, row = found[-1]
        if origin == route['origin']:
            destination = route['destination']
        elif origin == route['destination'] and route['bidirectional'] is True:
            destination = route['origin']
        else:
            raise Fault('UNAVAILABLE')
        if row['data'].get('access') not in ('open', 'conditional'):
            raise Fault('DEPENDENCY')
        requirements = deepcopy(route['requires'])
        if row['data'].get('access') == 'conditional' and not requirements:
            raise Fault('DEPENDENCY')
        for req in requirements:
            target = records.get(req['record_id'])
            if not target or req['field'] not in target['data']:
                raise Fault('UNAVAILABLE')
            if encoded(target['data'][req['field']]) != encoded(req['equals']):
                raise Fault('DEPENDENCY')
        duration = route['duration']
        minutes = duration['value']
        clock = records.get(duration['clock_id'])
        if (type(minutes) is not int or minutes <= 0 or duration['unit'] != 'minute'
                or not clock or clock['domain'] != 'clock'
                or clock['data'].get('unit') != 'minute'
                or type(clock['data'].get('tick')) not in (int, float)
                or not math.isfinite(clock['data']['tick'])):
            raise Fault('DEPENDENCY')
        tick = clock['data']['tick']
        next_tick = tick + minutes
        if not math.isfinite(next_tick) or next_tick <= tick or next_tick - tick != minutes:
            raise Fault('DEPENDENCY')
        if op.get('parent_id'):
            parent = self.app.activity(context, op['parent_id'])
            if parent['state'] in ('finished', 'failed', 'cancelled', 'paused'):
                raise Fault('DEPENDENCY')
        self.app.exploration.parent_clear(op.get('parent_id'), actor)
        self.app.exploration.movement_clear({actor})
        for target in (own, row, clock, records[origin], records[destination]):
            fields = {'location': origin} if target['id'] == actor else target['data']
            requirements.extend({'record_id': target['id'], 'field': field, 'equals': deepcopy(value)}
                for field, value in fields.items())
        snapshot = {'actor': reference(own), 'route': reference(row), 'clock': reference(clock),
            'requirements': requirements, 'origin': origin, 'destination': destination,
            'duration': deepcopy(duration), 'carrier_id': carrier['id'], 'carrier_version': carrier['version']}
        did = 'synthetic:journey:' + digest([self.app.workspace_id, snapshot])
        wrapper = self._compile(did, actor, snapshot)
        self.app.exploration.admit(wrapper, [actor], op.get('parent_id'))
        _validate(wrapper['encounter'])
        self._persist(wrapper, snapshot, request_id)
        return {'name': 'activity.start', 'activity_id': op['activity_id'], 'kind': 'travel',
            'definition': wrapper['reference'], 'parent_id': op.get('parent_id'),
            'participants': [actor], 'purpose': None, 'source_refs': [], 'acceptance_ref': 'native:encounter/1'}

    def _compile(self, did, actor, snapshot):
        def action(label, state, changes, requirements):
            return {'label': label, 'actor_role': 'traveller', 'kind': 'event',
                'payload': {'changes': changes}, 'next_state': state, 'resolve_loops': [],
                'requirements': deepcopy(requirements)}
        def choice(aid):
            return [{'op': 'create', 'domain': 'historical_account',
                'id': {'$encounter': 'choice-' + aid}, 'data': {'author': actor,
                    'assertion': 'I chose to ' + aid + ' here; no travel or elapsed minute is implied.'},
                'status': 'reported', 'visibility': 'restricted', 'audience': [actor], 'evidence': EVIDENCE}]
        walk = [{'op': 'patch', 'id': actor, 'expected_version': snapshot['actor']['version'],
            'data': {'location': snapshot['destination']}, 'evidence': EVIDENCE},
            {'op': 'patch', 'id': snapshot['clock']['id'], 'expected_version': snapshot['clock']['version'],
             'data': {'tick': next(r['equals'] for r in snapshot['requirements']
                 if r['record_id'] == snapshot['clock']['id'] and r['field'] == 'tick') + snapshot['duration']['value']},
             'evidence': EVIDENCE}]
        scope = sorted({actor, *(r['record_id'] for r in snapshot['requirements'])})
        spec = {'title': 'Walk the current authored route', 'roles': ['traveller'], 'visibility': 'public',
            'initial_state': 'initial', 'max_steps': 2, 'loops': [],
            'states': {'initial': {'phase': 'active', 'outcome': 'unresolved', 'actions': ['walk', 'remain', 'stop']},
                **{state: {'phase': 'completed', 'outcome': outcome, 'actions': []}
                    for state, outcome in [('arrived', 'achieved'), ('remained', 'partly_achieved'), ('stopped', 'not_achieved')]}},
            'actions': {'walk': action('Walk this exact route, advancing its declared walking minutes.', 'arrived', walk, snapshot['requirements']),
                'remain': action('Remain at the actual origin without walking.', 'remained', choice('remain'),
                    [{'record_id': actor, 'field': 'location', 'equals': snapshot['origin']}]),
                'stop': action('Stop at the last accepted place without a refund or return.', 'stopped', choice('stop'), [])},
            'ending': {'label': 'Stop at the last accepted place; no return or time refund.', 'next_state': 'stopped', 'changes': []}}
        wrapper = {'id': did, 'version': 1, 'title': spec['title'], 'kind': 'travel', 'handler': 'encounter',
            'participants': [actor], 'start_location': snapshot['origin'], 'role_bindings': {'traveller': actor},
            'exploration': True, 'action_scope_ids': {'walk': scope, 'remain': [actor], 'stop': [actor], '__end__': [actor]},
            'encounter': spec}
        wrapper['reference'] = {'id': did, 'version': 1, 'digest': digest(wrapper)}
        return wrapper

    def _persist(self, wrapper, snapshot, request_id):
        stable = self.app.key(self.app.workspace_id, wrapper['id'])
        old = self.db.execute("SELECT * FROM registry_entries WHERE kind='samsara_journey' AND stable_id=? AND version='1'", (stable,)).fetchone()
        payload = {'workspace_id': self.app.workspace_id, 'wrapper': wrapper, 'snapshot': snapshot}
        sha = digest(payload)
        if old:
            if old['source_hash'] != sha or old['status'] != 'verified':
                raise Fault('CONFLICT')
            self._load(old)
        else:
            if self.db.execute('SELECT 1 FROM encounter_definitions WHERE definition_id=? AND version=1',
                    (wrapper['id'],)).fetchone():
                raise Fault('CONFLICT')
            # Native immutable bytes are operator-only, never activity sources.
            principal = 'operator:' + str(os.getuid())
            ref = self.app.put_json(payload, 'journey-artifact:' + stable,
                principals=[principal], private_viewer=principal)
            self.app.services.encounters.define(wrapper['id'], 1, wrapper['encounter'], 'journey-definition:' + stable, viewer=None)
            self.engine.register_component('samsara_journey', stable, '1', encoded({'workspace_id': self.app.workspace_id, 'artifact_ref': ref}),
                status='verified', readers=['Samsara.Atlas'], writers=['Samsara.Atlas'],
                compatibility={'format': 'samsara_journey/1'}, source_hash=sha, declared_by='Samsara.Atlas')
        self.app.catalog[wrapper['id']] = wrapper

    def _load(self, row):
        try:
            locator = json.loads(row['locator'])
            if locator['workspace_id'] != self.app.workspace_id:
                return
            if row['version'] != '1':
                raise Fault('DEPENDENCY')
            ref = locator['artifact_ref']
            meta = self.app.services.artifacts.read(ref['id'], viewer=None)
            if (ref['version'] != 1 or meta['digest'] != ref['digest']
                    or not (self.app.artifact_audience(ref) or '').startswith('operator:')
                    or hashlib.sha256(meta['content']).hexdigest() != ref['digest']):
                raise Fault('DEPENDENCY')
            grants = self.db.execute('SELECT principal_id FROM activity_artifact_grants WHERE workspace_id=? AND artifact_id=?',
                (self.app.workspace_id, ref['id'])).fetchall()
            if any(not g['principal_id'].startswith('operator:') for g in grants):
                raise Fault('DEPENDENCY')
            payload = json.loads(meta['content'])
            if digest(payload) != row['source_hash'] or payload['workspace_id'] != self.app.workspace_id or row['status'] != 'verified':
                raise Fault('DEPENDENCY')
            wrapper = payload['wrapper']
            if wrapper['id'] != 'synthetic:journey:' + digest([self.app.workspace_id, payload['snapshot']]):
                raise Fault('DEPENDENCY')
            expected = self._compile(wrapper['id'], wrapper['participants'][0], payload['snapshot'])
            if wrapper != expected or row['stable_id'] != self.app.key(self.app.workspace_id, wrapper['id']):
                raise Fault('DEPENDENCY')
            native = self.app.services.encounters._definition(wrapper['id'], wrapper['version'])
            if native != _validate(wrapper['encounter']):
                raise Fault('DEPENDENCY')
            key = (payload['snapshot']['carrier_id'], payload['snapshot']['carrier_version'])
            if key not in self.app.content_sets.sets:
                raise Fault('DEPENDENCY')
            self.app.catalog[wrapper['id']] = wrapper
        except (KeyError, ValueError, TypeError):
            raise Fault('DEPENDENCY') from None

    def reload(self):
        # Also removes an uncommitted wrapper after an outer activity UoW rolls back.
        for identity in list(self.app.catalog):
            if identity.startswith('synthetic:journey:'):
                del self.app.catalog[identity]
        for row in self.db.execute("SELECT * FROM registry_entries WHERE kind='samsara_journey' ORDER BY stable_id,version"):
            self._load(row)
