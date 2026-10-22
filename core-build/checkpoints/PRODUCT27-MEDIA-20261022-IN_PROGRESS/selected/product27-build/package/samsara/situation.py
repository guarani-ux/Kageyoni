"""Bounded participant views and accepted receipts over native world records.

These are derived views. Native records, their event history and encounter
receipts remain authoritative; reading this module never advances fiction.
"""
from copy import deepcopy
import json

from kageyoni.model import DOMAINS
from kageyoni.engine import Rejected
from .protocol import Fault, digest, validate


def reference(record):
    return {'id': record['id'], 'version': record['version'], 'digest': digest(record)}


def text(value):
    return value if isinstance(value, str) else ''


class Situation:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db

    def visible(self, actor):
        if not actor:
            raise Fault('UNAVAILABLE')
        return {r['id']: r for r in self.engine.context(self.app.branch, viewer=actor,
            include_properties=False, include_processes=False)['records']}

    def snapshot(self, actor, encounter_id=None, records=None, activities=(), source_refs=(), local_only=False, candidate=None):
        records = self.visible(actor) if records is None else records
        own = records.get(actor)
        if not own or own['domain'] != 'character':
            raise Fault('UNAVAILABLE')
        location_id = own['data'].get('location')
        place = records.get(location_id)
        present = [r for r in records.values() if r['domain'] == 'character'
            and (r['id'] == actor or (location_id is not None and r['data'].get('location') == location_id))]
        present.sort(key=lambda r: (r['id'] != actor, r['id']))
        ids = {r['id'] for r in present}
        scope = {actor}
        more = False

        def bounded(rows, limit):
            nonlocal more
            values = sorted(rows, key=lambda r: r['id'])
            more = more or len(values) > limit
            values = values[:limit]
            scope.update(r['id'] for r in values)
            return values

        people = []
        for person in bounded(present, 16):
            concerns = bounded([r for r in records.values() if r['domain'] == 'character_aspect'
                and r['data'].get('character') == person['id'] and r['data'].get('phase') == 'active'
                and r['data'].get('value_status') == 'known'
                and r['data'].get('kind') in ('drive', 'preference', 'pleasure', 'question', 'boundary')], 8)
            people.append({'reference': reference(person), 'name': text(person['data'].get('name')),
                'condition': text(person['data'].get('condition')),
                'concerns': [{'reference': reference(r), 'kind': r['data']['kind'],
                    'statement': text(r['data'].get('statement'))} for r in concerns]})
        relations = bounded([r for r in records.values() if r['domain'] == 'relationship'
            and r['data'].get('subject') in ids and r['data'].get('object') in ids], 32)
        promises = bounded([r for r in records.values() if r['domain'] == 'character_aspect'
            and r['data'].get('character') in ids and r['data'].get('kind') == 'commitment'
            and r['data'].get('phase') == 'active' and r['data'].get('value_status') == 'known'], 32)
        material = bounded([r for r in records.values() if r['domain'] == 'resource'
            and r['data'].get('holder') in ids | ({location_id} if place else set())], 32)
        source_ids = {d.get('scene_source_id') for d in self.app.catalog.values()}
        sources = bounded([r for r in records.values() if r['id'] in source_ids
            and r['domain'] == 'thread'], 4)
        equipment = []
        for loadout in bounded([r for r in records.values() if r['domain'] == 'loadout'
                and r['data'].get('holder') in ids and r['data'].get('item') in records], 32):
            item = records[loadout['data']['item']]
            if item['domain'] != 'item':
                continue
            scope.update((item['id'], loadout['data']['holder']))
            equipment.append({'reference': reference(item), 'loadout': reference(loadout),
                'holder_id': loadout['data']['holder'], 'name': item['data']['name'],
                'condition': text(item['data'].get('condition')),
                'equipped': loadout['data'].get('equipped') == 1,
                'slot': text(loadout['data'].get('slot'))})
        practice = []
        own_scene_ids = {r['data'].get('scene') for r in records.values()
            if r['domain']=='participation' and r['data'].get('character')==actor}
        for scene in bounded([r for r in records.values() if r['domain'] == 'scene'
                and (r['id'].endswith(':practice-scene') or r['id'] in own_scene_ids) and r['data'].get('location') == location_id
                and (r['data'].get('phase') != 'closed' or r['id'] in (str(encounter_id) + ':practice-scene', str(encounter_id) + ':scene'))], 16):
            positions = bounded([r for r in records.values() if r['domain'] == 'participation'
                and r['data'].get('scene') == scene['id'] and r['data'].get('character') in ids], 16)
            scope.update(r['data']['character'] for r in positions)
            practice.append({'reference': reference(scene), 'name': scene['data']['name'],
                'phase': scene['data']['phase'], 'context': text(scene['data'].get('context')),
                'positions': [{'reference': reference(r), 'character_id': r['data']['character'],
                    'position': text(r['data'].get('position')),
                    'active_effects': text(r['data'].get('active_effects')),
                    'actions_remaining': r['data'].get('actions_remaining', 0)} for r in positions]})
        accounts, account_scope = self.app.practice.accounts(actor, records)
        prior, prior_scope = self.app.practice.history(actor, records, source_refs)
        scope.update(account_scope | prior_scope)
        if place:
            scope.add(place['id'])
        for row in relations + promises + material:
            scope.update(row['data'][key] for key, kind in DOMAINS[row['domain']].items()
                if kind.startswith('ref:') and row['data'].get(key) in records)
        geography, geographic_scope = self.app.exploration.project(actor, records, local_only=local_only, candidate=candidate)
        atlas_geography, atlas_scope = self.app.atlas.project(actor, records)
        geographic_scope.update(atlas_scope)
        known_routes = {r['reference']['id'] for r in geography['routes']}
        geography['routes'].extend(r for r in atlas_geography['routes'] if r['reference']['id'] not in known_routes)
        if len(geography['routes']) > 8:
            more = True
            geography['routes'] = geography['routes'][:8]
        scope.update(geographic_scope)
        events = self.recent_events(records, scope, ids, actor)
        for item in events:
            scope.update(ref['id'] for ref in item['changed_refs'])
        turns = []
        more_turns = False
        for row in self.db.execute("SELECT r.id FROM records r JOIN events e ON e.id=r.updated_event WHERE r.branch=? AND r.domain='dialogue_turn' ORDER BY e.revision DESC,r.id DESC", (self.app.branch,)):
            r = records.get(row['id'])
            if not r:
                continue
            data = r['data']
            if data.get('speaker') not in ids or not (data.get('speaker') == actor or actor in data.get('listeners', [])):
                continue
            if len(turns) == 8:
                more_turns = True
                break
            scope.add(r['id'])
            scope.add(data['speaker'])
            scope.update(x for x in data.get('listeners', []) if x in records)
            turns.append({'speaker_id': data.get('speaker'), 'text': text(data.get('text'))})
        choices = []
        encounters = [(None, encounter_id)] if encounter_id else [(a['activity_id'], a['native'].get('encounter_id'))
            for a in activities if a['state'] == 'waiting' and a['native'].get('actor') == actor]
        for activity_id, eid in encounters[:32]:
            if not eid:
                continue
            try:
                view = self.app.services.encounters.inspect(self.app.branch, eid, viewer=actor)
            except Rejected:
                # An unavailable pending exchange must not reveal its hidden
                # participant or interrupt the rest of the workspace view.
                continue
            actions = [{'action_id': a['action_id'], 'label': a['label']} for a in view['next_actions']]
            if actions:
                choices.append({'activity_id': activity_id, 'actor_id': actor, 'actions': actions})
        value = {'perspective_id': actor,
            'place': {'reference': reference(place) if place else None,
                'name': text(place['data'].get('name')) if place else 'Unspecified place',
                'description': text(place['data'].get('geography')) if place else ''},
            'people': people,
            'relationships': [{'reference': reference(r), 'subject_id': r['data']['subject'],
                'object_id': r['data']['object'], 'kind': r['data']['kind'],
                'shared_history': text(r['data'].get('shared_history')),
                'obligation': text(r['data'].get('obligation'))} for r in relations],
            'commitments': [{'reference': reference(r), 'character_id': r['data']['character'],
                'statement': text(r['data'].get('statement')),
                'ending_condition': text(r['data'].get('ending_condition'))} for r in promises],
            'materials': [{'reference': reference(r), 'name': r['data']['name'],
                'holder_id': r['data']['holder'], 'quantity': r['data']['quantity'],
                'unit': r['data']['unit'], 'availability': text(r['data'].get('availability'))} for r in material],
            'equipment': equipment, 'practice': practice, 'own_accounts': accounts, 'prior_practice': prior,
            'recent_events': events, 'recent_turns': list(reversed(turns)), 'more_turns': more_turns,
            'choices': choices, 'source_refs': [reference(r) for r in sources],
            'additional_context': more}
        value.update(geography)
        validate(value, 'Situation')
        return value, sorted(scope)

    def recent_events(self, visible, selected, actors, perspective):
        """Filter complete public event images before selecting or counting.

        Narrative from an event with a hidden changed subject is not projected.
        Private observations and owner judgment are never copied into this view.
        """
        values = []
        # Only a native encounter receipt for a reviewed installed definition
        # supplies narrative here. An arbitrary owner event's narrative can
        # discuss private auxiliary facts even when its record changes are
        # public. Its wording is never a participant history source.
        for event in self.db.execute('''SELECT e.id,e.revision,e.actor,
                i.definition_id,i.definition_version,h.payload_json
            FROM encounter_events h JOIN encounter_instances i
                ON i.branch=h.branch AND i.encounter_id=h.encounter_id
            JOIN events e ON e.id=json_extract(h.receipt_json,'$.world_receipt.event_id')
            WHERE e.branch=? ORDER BY e.revision DESC''', (self.app.branch,)):
            if event['actor'] not in actors:
                continue
            definition = self.app.catalog.get(event['definition_id'])
            if not definition or definition['version'] != event['definition_version']:
                continue
            source = definition.get('scene_source_id')
            if source and source not in visible:
                continue
            action_id = json.loads(event['payload_json']).get('action_id')
            action = definition.get('encounter', {}).get('actions', {}).get(action_id)
            if not action:
                continue
            changes = list(self.db.execute('SELECT record_id,before_json,after_json FROM changes WHERE event_id=? ORDER BY ordinal', (event['id'],)))
            if not changes or not any(row['record_id'] in selected for row in changes):
                continue
            if any(row['record_id'] not in visible for row in changes):
                continue
            images = [json.loads(row[key]) for row in changes for key in ('before_json', 'after_json') if row[key]]
            if any(not self.engine._visible(image, perspective) for image in images):
                continue
            if any(image['data'].get(key) is not None and image['data'][key] not in visible
                for image in images for key, kind in DOMAINS[image['domain']].items() if kind.startswith('ref:')):
                continue
            values.append({'event_id': event['id'], 'revision': event['revision'],
                'actor_id': event['actor'], 'narrative': action['label'],
                'changed_refs': [reference(visible[row['record_id']]) for row in changes]})
            if len(values) == 8:
                break
        return list(reversed(values))

    def image(self, raw, visible, actor):
        if raw is None or not self.engine._visible(raw, actor):
            return None
        data = deepcopy(raw['data'])
        for key, kind in DOMAINS[raw['domain']].items():
            if kind.startswith('ref:') and data.get(key) not in visible:
                data[key] = None
        if raw['domain'] == 'dialogue_turn':
            data['listeners'] = [x for x in data.get('listeners', []) if x in visible]
        return {'id': raw['id'], 'domain': raw['domain'], 'version': raw['version'],
            'status': raw['status'], 'data': data}

    def accepted(self, activity, prepared, record, actor, perspective=None):
        """Expose real accepted native consequences, separately from proposal.

        Context grants track every included native subject. Parent outputs and
        derived work inherit them through the existing artifact grant route.
        """
        viewer = perspective or actor
        visible = self.visible(viewer)
        receipt = record.engine_receipt
        native = receipt.get('world_receipt') if receipt else None
        event_id = native.get('event_id') if native else None
        scope = {viewer}
        source = self.app.catalog[activity['spec']['definition']['id']].get('scene_source_id')
        if source:
            scope.add(source)
        definition = self.app.catalog[activity['spec']['definition']['id']]
        action_id = record.proposed_action.get('action_id')
        scope.update(definition.get('action_scope_ids', {}).get(action_id, []))
        changes = []
        if event_id:
            for row in self.db.execute('SELECT record_id,before_json,after_json FROM changes WHERE event_id=? ORDER BY ordinal', (event_id,)):
                scope.add(row['record_id'])
                before = json.loads(row['before_json']) if row['before_json'] else None
                after = json.loads(row['after_json'])
                item = {'record_id': row['record_id'], 'before': self.image(before, visible, viewer),
                    'after': self.image(after, visible, viewer)}
                for image in (item['before'], item['after']):
                    if image:
                        scope.update(image['data'][key] for key, kind in DOMAINS[image['domain']].items()
                            if kind.startswith('ref:') and image['data'].get(key) in visible)
                        if image['domain'] == 'dialogue_turn':
                            scope.update(image['data'].get('listeners', []))
                changes.append(item)
        action_id = record.proposed_action.get('action_id')
        definition = self.app.catalog[activity['spec']['definition']['id']]
        label = (definition['encounter']['ending']['label'] if action_id == '__end__'
            else definition['encounter']['actions'].get(action_id, {}).get('label', 'No action was chosen.'))
        disclosed_receipt = None
        if receipt:
            disclosed_receipt = {key: deepcopy(receipt[key]) for key in (
                'encounter_interface', 'branch', 'encounter_id', 'definition_id', 'definition_version',
                'state_revision', 'phase', 'outcome', 'state', 'world_revision', 'state_digest', 'replayed') if key in receipt}
            disclosed_receipt['receipt_digest'] = digest(receipt)
            disclosed_receipt['world_receipt'] = ({key: native[key] for key in (
                'event_id', 'branch', 'revision', 'request_id', 'event_hash', 'replayed', 'committed') if key in native} if native else None)
        value = {'kind': 'accepted_encounter', 'activity_id': activity['activity_id'],
            'definition': activity['spec']['definition'], 'actor_id': actor,
            'action_id': action_id, 'description': label,
            'validation_status': record.validation_status,
            'revision_before': record.revision_before, 'revision_after': record.revision_after,
            'native_event_id': event_id, 'native_receipt': disclosed_receipt, 'changes': changes,
            'boundary': 'Disclosed native receipt fields and permitted record images; no inferred feeling, mastery or whole-purpose completion.'}
        validate(value, 'EncounterTrace')
        ref = self.app.put_json(value, self.app.key(prepared['job_id'], 'accepted-consequence'), activity=activity,
            private_viewer=viewer if definition.get('exploration') else None)
        principals = [r[0] for r in self.db.execute('SELECT principal_id FROM activity_artifact_grants WHERE workspace_id=? AND artifact_id=?', (self.app.workspace_id, ref['id']))]
        self.app.properties.attach_entities(ref, principals, scope)
        # This is a trusted projection of the accepted public native result,
        # not free-form worker text derived from all of the chooser's context.
        # Unrelated private concerns are not disclosed and cannot deny the
        # recipient their own public consequence. Included subjects and the
        # activity's explicitly admitted sources remain scoped above/in put.
        return ref
