"""Scoped views and provenance checks over native walking encounters.

This module owns no world facts. Discovery requires the actual native change,
accepted product receipt and current disclosure, rather than matching prose.
"""
import json

from .protocol import Fault, digest, validate
from .travel_content import (SOURCE, MARKER, CONDITIONS, BENCH, LOCAL_PATH,
    KNOWLEDGE, KNOWLEDGE_ASSERTION, KNOWLEDGE_BASIS)


def reference(record):
    return {'id': record['id'], 'version': record['version'], 'digest': digest(record)}


class Exploration:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db

    def bindings(self, definition, participants):
        roles = definition['encounter']['roles']
        bound = definition.get('role_bindings', {role: role for role in roles})
        if (set(bound) != set(roles) or len(set(bound.values())) != len(bound)
                or any(actor not in participants for actor in bound.values())):
            raise Fault('INVALID')
        return dict(bound)

    def movement_clear(self, actors):
        for actor in actors:
            for row in self.db.execute("SELECT id FROM records WHERE branch=? AND domain='participation'", (self.app.branch,)):
                data = self.engine.get(self.app.branch, row[0])['data']
                if data.get('character') != actor:
                    continue
                scene = self.engine.get(self.app.branch, data.get('scene'))
                if scene and scene['domain'] == 'scene' and scene['data'].get('phase') != 'closed':
                    raise Fault('BUSY')

    def moving_actors(self, definition, actions):
        actors = set()
        bound = self.bindings(definition, definition['participants'])
        for aid in actions:
            action = definition['encounter']['actions'].get(aid, {})
            for change in action.get('payload', {}).get('changes', []):
                if 'location' not in change.get('data', {}):
                    continue
                identity = change.get('id')
                if isinstance(identity, dict) and '$role' in identity:
                    identity = bound.get(identity['$role'])
                if identity in bound.values():
                    actors.add(identity)
        return actors

    def parent_clear(self, parent_id, actor):
        seen = set()
        while parent_id:
            if parent_id in seen or len(seen) >= 4:
                raise Fault('DEPENDENCY')
            seen.add(parent_id)
            parent = self.app.store.get(self.app.workspace_id, parent_id)
            definition = self.app.catalog[parent['spec']['definition']['id']]
            recipients = set(parent['spec']['participants'])
            if definition['handler'] == 'encounter':
                bound = self.bindings(definition, parent['spec']['participants'])
                recipients = {bound[a['actor_role']] for a in definition['encounter']['actions'].values()}
            if recipients != {actor}:
                raise Fault('UNAVAILABLE')
            parent_id = parent['parent_id']

    def admit(self, definition, participants, parent_id):
        self.bindings(definition, participants)
        movers = self.moving_actors(definition, definition['encounter']['actions'])
        self.movement_clear(movers)
        if not definition.get('exploration'):
            return
        actor = participants[0]
        self.parent_clear(parent_id, actor)
        for row in self.db.execute('SELECT activity_id FROM activity_runs WHERE workspace_id=?', (self.app.workspace_id,)):
            old = self.app.store.get(self.app.workspace_id, row[0])
            prior = self.app.catalog.get(old['spec']['definition']['id'], {})
            if not prior.get('exploration') or not set(participants) & set(old['spec']['participants']):
                continue
            native = self.app.services.encounters.inspect(self.app.branch, old['native']['encounter_id'], viewer=None)
            if native['phase'] not in ('completed', 'failed'):
                raise Fault('BUSY')
        visible = self.app.situation.visible(actor)
        if definition.get('scene_source_id') and definition['scene_source_id'] not in visible:
            raise Fault('UNAVAILABLE')
        if definition.get('requires_discovery') and self.proof(actor, visible) is None:
            raise Fault('DEPENDENCY')

    def proof(self, actor, records=None, candidate=None):
        records = self.app.situation.visible(actor) if records is None else records
        knowledge = records.get(KNOWLEDGE)
        required = {actor, KNOWLEDGE, MARKER, BENCH, LOCAL_PATH}
        if not required <= records.keys() or actor != 'visitor':
            return None
        expected = dict(holder=actor, subject=BENCH, attitude='knows',
            assertion=KNOWLEDGE_ASSERTION, basis=KNOWLEDGE_BASIS)
        if knowledge['domain'] != 'knowledge' or any(knowledge['data'].get(k) != v for k, v in expected.items()):
            return None
        row = self.db.execute('''SELECT r.updated_event,c.after_json,h.encounter_id,i.definition_id,i.definition_version,h.payload_json
            FROM records r JOIN changes c ON c.event_id=r.updated_event AND c.record_id=r.id
            JOIN encounter_events h ON json_extract(h.receipt_json,'$.world_receipt.event_id')=r.updated_event
            JOIN encounter_instances i ON i.branch=h.branch AND i.encounter_id=h.encounter_id
            WHERE r.branch=? AND r.id=? AND h.branch=?''',
            (self.app.branch, KNOWLEDGE, self.app.branch)).fetchone()
        if not row or row['definition_id'] != 'synthetic:garden_journey' or row['definition_version'] != 1:
            return None
        if json.loads(row['payload_json']).get('action_id') != 'observe_marker':
            return None
        after = json.loads(row['after_json'])
        if after['version'] != knowledge['version'] or after['data'] != knowledge['data']:
            return None
        candidates = [candidate] if candidate else []
        for old in self.db.execute('SELECT activity_id FROM activity_runs WHERE workspace_id=?', (self.app.workspace_id,)):
            candidates.append(self.app.store.get(self.app.workspace_id, old[0]))
        for activity in candidates:
            if not activity or activity['native'].get('encounter_id') != row['encounter_id']:
                continue
            if (activity['spec']['definition'] != self.app.catalog['synthetic:garden_journey']['reference']
                    or activity['spec']['participants'] != [actor]):
                continue
            for ref in activity['native'].get('accepted_result_refs', []):
                try:
                    trace = json.loads(self.app.artifact_bytes_for_actor(actor, ref))
                    validate(trace, 'EncounterTrace')
                except (Fault, ValueError):
                    continue
                if (trace['actor_id'] != actor or trace['action_id'] != 'observe_marker'
                        or trace['native_event_id'] != row['updated_event']):
                    continue
                image = next((c['after'] for c in trace['changes'] if c['record_id'] == KNOWLEDGE), None)
                if image and image['version'] == knowledge['version'] and image['data'] == knowledge['data']:
                    return {'reference': reference(knowledge), 'source_ref': ref,
                        'basis': reference(records[MARKER]), 'assertion': KNOWLEDGE_ASSERTION}
        return None

    def require_actions(self, activity, actions):
        definition = self.app.catalog[activity['spec']['definition']['id']]
        self.movement_clear(self.moving_actors(definition, actions))
        if set(actions) & set(definition.get('knowledge_actions', [])):
            if self.proof(activity['spec']['participants'][0], candidate=activity) is None:
                raise Fault('DEPENDENCY')

    def action_scope(self, activity, actions):
        definition = self.app.catalog[activity['spec']['definition']['id']]
        return sorted({rid for aid in actions for rid in definition.get('action_scope_ids', {}).get(aid, [])})

    def project(self, actor, records, *, local_only=False, candidate=None):
        own = records.get(actor)
        if not own:
            return {'routes': [], 'discoveries': [], 'cues': []}, set()
        here = own['data'].get('location')
        proof = None if local_only else self.proof(actor, records, candidate)
        scope, routes, cues = set(), [], []
        if here in ('studio', 'garden'):
            allowed = [('garden-path', 'garden' if here == 'studio' else 'studio')]
        else:
            allowed = []
        if here == BENCH or here == 'garden' and proof:
            allowed.append((LOCAL_PATH, 'garden' if here == BENCH else BENCH))
        for rid, destination in allowed:
            route, target = records.get(rid), records.get(destination)
            if not route or not target or route['domain'] != 'route':
                continue
            if {route['data'].get('origin'), route['data'].get('destination')} != {here, destination}:
                continue
            scope.update((rid, here, destination))
            condition = route['data'].get('conditions') or ''
            if rid == 'garden-path' and route['data'].get('access') == 'conditional' and CONDITIONS in records:
                scope.add(CONDITIONS)
                condition += ' Current terrain: ' + records[CONDITIONS]['data'].get('feature', 'unknown')
            routes.append({'reference': reference(route), 'destination': reference(target),
                'name': target['data'].get('name') or destination, 'access': route['data'].get('access') or 'unknown',
                'condition': condition})
        if here == 'garden' and not local_only and MARKER in records:
            scope.add(MARKER)
            cues.append({'reference': reference(records[MARKER]), 'question': records[MARKER]['data'].get('question') or ''})
        if proof:
            scope.update((actor, KNOWLEDGE, MARKER, BENCH, LOCAL_PATH))
        return {'routes': routes, 'discoveries': [proof] if proof else [], 'cues': cues}, scope
