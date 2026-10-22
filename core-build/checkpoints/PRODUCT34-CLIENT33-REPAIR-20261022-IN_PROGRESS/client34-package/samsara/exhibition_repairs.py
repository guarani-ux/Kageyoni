"""SOURCE_ONLY unreserved repair invitations over genuine native history.

Root must wire private attachment/live guards, fingerprint this module and
qualify a new build. No SQL/native consent, payout or mutable choice store is
introduced. Normal artifacts and native instance receipts stay distinct.
"""
from copy import deepcopy
import json

from kageyoni.engine import Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.world import verify_encounters, _expand, _same_value
from .contentsets import ContentSets, shape, require, text
from .exhibitions import _ACTIVITY_OWNER_VIEW
from .protocol import Fault, digest, encoded, runtime_fingerprint

KIND = 'samsara_exhibition_repair'
PREFIX = 'synthetic:f3a:repair-offer:'
LOCATOR = ('kind', 'workspace_id', 'contest_id', 'offer_id', 'encounter_id',
           'profile_activation_ref', 'definition_ref', 'settlement_native_ref',
           'settlement_ref', 'start_receipt', 'terms_ref', 'runtime_digest')


class ExhibitionRepairs:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db
        self.exhibitions = app.exhibitions
        self.encounters = app.services.encounters
        self.history = self.exhibitions.native

    def _identity(self, contest_id, offer_id):
        self.exhibitions._identity(contest_id)
        text(offer_id, 128)
        require(offer_id.startswith(PREFIX) and offer_id.strip() == offer_id)
        return self.app.key('repair-offer', self.app.workspace_id, contest_id, offer_id)

    def _artifact_ref(self, key):
        row = self.db.execute('SELECT artifact_id,digest FROM artifacts WHERE '
            'workspace_id=? AND request_id=?', (self.app.workspace_id, key)).fetchone()
        require(row is not None, 'UNAVAILABLE')
        return {'id': row['artifact_id'], 'version': 1, 'digest': row['digest']}

    def _normal(self, context, ref, expected, actors):
        if context is _ACTIVITY_OWNER_VIEW:
            for actor in actors:
                require(self.app.artifact_bytes_for_actor(actor, ref) == encoded(expected).encode(), 'DEPENDENCY')
        else:
            require(self.app.artifact_bytes(context, ref) == encoded(expected).encode(), 'DEPENDENCY')

    def _base(self, context, contest_id, *, positive_inputs=True):
        locator, carrier, current = self.exhibitions._load(context, contest_id,
            positive_inputs=positive_inputs)
        fact = current['settlement']
        require(fact is not None, 'DEPENDENCY')  # Native inspect verified the actual award provenance.
        data = fact['record']['data']; binding = carrier['exhibition']['binding']
        matches = [r for r in carrier['repairs']
                   if binding[r['beneficiary_role']] == data['beneficiary']]
        require(len(matches) == 1, 'DEPENDENCY'); repair = matches[0]
        require(data['destination'] == repair['award_id']
                and data['amount'] == carrier['award']['amount']
                and data['unit'] == carrier['award']['unit'], 'DEPENDENCY')
        definitions = [e for e in self.app.content_sets.encounters(carrier)
                       if e['id'] == repair['encounter']['id']]
        require(len(definitions) == 1 and definitions[0]['kind'] == 'life', 'DEPENDENCY')
        definition = ContentSets.wrapper(definitions[0])
        settlement_ref = self._artifact_ref(self.app.key('exhibition-settlement-artifact',
            self.app.workspace_id, contest_id))
        projected = {'format': 'samsara-contest-settlement/1', 'contest_id': contest_id,
            'native_reference': fact['reference'], 'native_receipt': fact['native_receipt'],
            'historical_resources': fact['historical_resources'], 'boundary': current['scope']}
        # Canonical parent loader returns native Contests.inspect, whose
        # exact scope is the BOUNDARY used by the parent's settlement artifact.
        self._normal(context, settlement_ref, projected, binding.values())
        return locator, carrier, repair, definition, fact, settlement_ref

    def _positive(self, carrier, repair, definition):
        """New invitation/acceptance only; native action CAS remains the writer."""
        binding = repair['encounter']['binding']; unit = carrier['award']['unit']
        for actor in binding.values():
            require(self.app.content_sets.actor_admitted(actor), 'UNAVAILABLE')
            self.exhibitions._visible(carrier, actor)
        get = lambda rid: self.engine.get(self.app.branch, rid)
        award, incorporated = get(repair['award_id']), get(repair['incorporated_id'])
        target, target_loadout = get(repair['target_id']), get(repair['target_loadout_id'])
        tool, tool_loadout = get(repair['tool_id']), get(repair['tool_loadout_id'])
        beneficiary, helper = binding[repair['beneficiary_role']], binding[repair['helper_role']]
        self.exhibitions._resource(award, unit, beneficiary)
        require(target and target['domain'] == 'item' and target['data']['condition'] == 'split'
                and target_loadout and target_loadout['domain'] == 'loadout'
                and target_loadout['data']['item'] == target['id']
                and target_loadout['data']['holder'] in (beneficiary, definition['start_location']), 'DEPENDENCY')
        self.exhibitions._resource(incorporated, unit, target_loadout['data']['holder'])
        require(award['data']['quantity'] == carrier['award']['amount']
                and incorporated['data']['quantity'] == 0, 'DEPENDENCY')
        require(tool and tool['domain'] == 'item' and tool_loadout
                and tool_loadout['domain'] == 'loadout' and tool_loadout['data']['item'] == tool['id']
                and tool_loadout['data']['holder'] == helper
                and tool_loadout['data']['equipped'] == 1, 'DEPENDENCY')
        # Check only the selected current material/tool rows here. Geometry and
        # co-presence remain ordinary begin/native-action requirements, not a
        # physical reservation or compelled travel before a helper chooses.
        selected = {r['id']: r for r in (award, incorporated, target, target_loadout, tool, tool_loadout)}
        material = definition['encounter']['actions'][repair['material_action']]
        for requirement in _expand(material['requirements'], binding, 'repair-readiness-only'):
            image = selected.get(requirement['record_id'])
            if image is not None:
                require(requirement['field'] in image['data'] and _same_value(
                    image['data'][requirement['field']], requirement['equals']), 'DEPENDENCY')

    def _episode(self, locator, definition, repair):
        """Use existing full native history verifier, then exact product pins.

        Global readonly verification is the deliberate bounded fallback, not a
        copied partial native validator or a claimed constant-cost operation.
        """
        binding = repair['encounter']['binding']
        verified = verify_encounters(self.engine)
        require(type(verified) is dict and set(verified) == {'installed', 'interface', 'encounters', 'profiles'}
                and verified['installed'] is True and verified['interface'] == '1'
                and type(verified['encounters']) is int and verified['encounters'] >= 1
                and type(verified['profiles']) is int and verified['profiles'] >= 0, 'DEPENDENCY')
        row, spec, actual_binding, _ = self.encounters._instance(self.app.branch, locator['encounter_id'], None)
        require(row['definition_id'] == definition['id'] and row['definition_version'] == definition['version']
                and spec == definition['encounter'] and actual_binding == binding, 'DEPENDENCY')
        entries = self.db.execute('SELECT * FROM encounter_events WHERE branch=? '
            'AND encounter_id=? ORDER BY revision', (self.app.branch, locator['encounter_id'])).fetchall()
        require(entries and len(entries) == row['revision'], 'DEPENDENCY')
        start = entries[0]; start_payload = json.loads(start['payload_json'])
        initial = json.loads(start['after_json']); receipt = json.loads(start['receipt_json'])
        stable = self._identity(locator['contest_id'], locator['offer_id'])
        expected = {'branch': self.app.branch, 'definition_id': definition['id'],
            'definition_version': definition['version'], 'encounter_id': locator['encounter_id'],
            'request_id': self.app.key('repair-start', stable), 'expected_revision': receipt['world_revision'],
            'participants': binding, 'viewer': binding[repair['beneficiary_role']],
            'continuation_of': None, 'evidence_refs': []}
        require(start['revision'] == 1 and start['before_json'] is None and start_payload == expected
                and receipt == locator['start_receipt'] and receipt['world_receipt'] is None
                and receipt['replayed'] is False and initial['steps'] == 0
                and initial['current_state'] == spec['initial_state'] and initial['phase'] == 'active'
                and initial['pending'] is None, 'DEPENDENCY')
        return row, spec, entries

    def _choice_proof(self, locator, definition, repair, entries):
        if len(entries) == 1:
            return None
        entry = entries[1]; payload = json.loads(entry['payload_json'])
        if payload.get('operation') == 'end':
            return None  # A genuine pre-choice cancellation is never acceptance.
        action_id = payload.get('action_id')
        choices = {repair['helper_accept_action']: 'accepted', repair['helper_decline_action']: 'declined'}
        require(action_id in choices, 'DEPENDENCY')
        action = definition['encounter']['actions'][action_id]
        binding = repair['encounter']['binding']; helper = binding[repair['helper_role']]
        before = json.loads(entry['before_json']); after = json.loads(entry['after_json'])
        receipt = json.loads(entry['receipt_json']); world = receipt['world_receipt']
        require(type(world) is dict, 'DEPENDENCY')
        event, command, actual = self.history._event(self.app.branch, world['event_id'])
        expected_payload = {'branch': self.app.branch, 'encounter_id': locator['encounter_id'],
            'action_id': action_id, 'request_id': entry['request_id'],
            'expected_revision': payload.get('expected_revision'), 'fields': {},
            'viewer': helper, 'expected_encounter_revision': 1}
        require(payload == expected_payload and before['current_state'] == definition['encounter']['initial_state']
                and before['phase'] == 'active' and before['steps'] == 0 and before['pending'] is None
                and entry['revision'] == 2 and after['steps'] == 1 and after['pending'] is None
                and after['current_state'] == action['next_state']
                and after['phase'] == definition['encounter']['states'][action['next_state']]['phase']
                and after['outcome'] == definition['encounter']['states'][action['next_state']]['outcome']
                and action['kind'] == 'event' and action['actor_role'] == repair['helper_role']
                and receipt['world_receipt'] == actual and event['revision'] == payload['expected_revision'] + 1
                and after['world_revision'] == event['revision']
                and command['request_id'] == 'encounter-action:' + entry['request_id']
                and command['actor'] == helper and command['kind'] == 'action', 'DEPENDENCY')
        authored = _expand(action['payload'], binding, locator['encounter_id'])
        require(command['changes'] == authored.get('changes', [])
                and not authored.get('observations'), 'DEPENDENCY')
        return {'choice': choices[action_id], 'action_id': action_id,
                'native_receipt': receipt, 'helper': helper}

    def _offer_payload(self, locator, parent, repair, definition, fact):
        binding = repair['encounter']['binding']
        return {'format': 'samsara-repair-offer/1', 'contest_id': locator['contest_id'],
            'offer_id': locator['offer_id'], 'definition': definition['reference'],
            'beneficiary': binding[repair['beneficiary_role']], 'helper': binding[repair['helper_role']],
            'settlement_native_ref': fact['reference'], 'settlement_ref': locator['settlement_ref'],
            'contest_terms_ref': parent['terms_ref'], 'native_receipt': locator['start_receipt'],
            'boundary': 'Unreserved invitation only; no helper acceptance, activity, repair, refund or mastery.'}

    def _choice_payload(self, locator, proof):
        return {'format': 'samsara-repair-choice/1', 'contest_id': locator['contest_id'],
            'offer_id': locator['offer_id'], **deepcopy(proof),
            'boundary': 'Actual bounded helper choice; no activity, material use or mastery.'}

    def _load(self, context, contest_id, offer_id, *, positive_inputs=True):
        owner = context is _ACTIVITY_OWNER_VIEW
        if not owner: self.exhibitions._player(context)
        stable = self._identity(contest_id, offer_id)
        parent, carrier, repair, definition, fact, settlement_ref = self._base(context, contest_id,
            positive_inputs=positive_inputs)
        row = self.db.execute('SELECT * FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',
            (KIND, stable, '1')).fetchone()
        require(row is not None, 'UNAVAILABLE')
        try: locator = json.loads(row['locator'])
        except (TypeError, ValueError): raise Fault('DEPENDENCY') from None
        shape(locator, LOCATOR)
        require(locator['kind'] == KIND and locator['workspace_id'] == self.app.workspace_id
                and locator['contest_id'] == contest_id and locator['offer_id'] == offer_id
                and locator['encounter_id'] == 'synthetic:f3a:repair-episode:' + stable
                and locator['profile_activation_ref'] == parent['profile_activation_ref']
                and locator['definition_ref'] == definition['reference']
                and locator['settlement_native_ref'] == fact['reference']
                and locator['settlement_ref'] == settlement_ref and locator['runtime_digest'] == runtime_fingerprint()
                and row['status'] == 'verified' and row['source_hash'] == digest(locator), 'DEPENDENCY')
        native_row, _, entries = self._episode(locator, definition, repair)
        proof = self._choice_proof(locator, definition, repair, entries)
        actors = repair['encounter']['binding'].values()
        self._normal(context, locator['terms_ref'], self._offer_payload(locator, parent, repair, definition, fact), actors)
        choice_ref = None
        if proof:
            choice_ref = self._artifact_ref(self.app.key('repair-choice-artifact', stable, proof['native_receipt']['state_revision']))
            self._normal(context, choice_ref, self._choice_payload(locator, proof), actors)
        if positive_inputs:
            for actor in actors:self.exhibitions._visible(carrier, actor)
        return locator, carrier, repair, definition, native_row, proof, choice_ref

    def _linked(self, locator, *, required=False, activity_id=None):
        rows = self.db.execute('SELECT activity_id FROM activity_runs WHERE workspace_id=? '
            "AND json_extract(native_json,'$.encounter_id')=?", (self.app.workspace_id, locator['encounter_id'])).fetchall()
        require(len(rows) <= 1, 'DEPENDENCY')
        if not rows:
            require(not required, 'DEPENDENCY');return None
        activity = self.app.store.get(self.app.workspace_id, rows[0]['activity_id'])
        require(activity['native'].get('exhibition_repair') == self._tag(locator)
                and (activity_id is None or activity['activity_id'] == activity_id), 'DEPENDENCY')
        return activity

    @staticmethod
    def _tag(locator):
        return {key: deepcopy(locator[key]) for key in ('contest_id', 'offer_id', 'terms_ref', 'settlement_native_ref')}

    def _return(self, locator, proof=None, choice_ref=None):
        result = {'contest_id': locator['contest_id'], 'offer_id': locator['offer_id'],
            'terms_ref': locator['terms_ref'], 'settlement_ref': locator['settlement_ref'],
            'settlement_native_ref': locator['settlement_native_ref']}
        if proof:result.update(choice=proof['choice'], native_receipt=proof['native_receipt'])
        if choice_ref:result['choice_ref'] = choice_ref
        return result

    def offer(self, context, contest_id, offer_id, request_id):
        self.exhibitions._player(context)
        stable = self._identity(contest_id, offer_id)
        with UnitOfWork(self.db):
            old = self.db.execute('SELECT 1 FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',
                (KIND, stable, '1')).fetchone()
            if old:
                locator, _, repair, _, _, proof, choice_ref = self._load(context, contest_id, offer_id, positive_inputs=False)
                require(context.character_id == repair['encounter']['binding'][repair['beneficiary_role']], 'UNAVAILABLE')
                return dict(self._return(locator, proof, choice_ref), replayed=True)
            parent, carrier, repair, definition, fact, settlement_ref = self._base(context, contest_id)
            binding = repair['encounter']['binding']
            require(context.character_id == binding[repair['beneficiary_role']], 'UNAVAILABLE')
            self._positive(carrier, repair, definition)
            for actor in binding.values():
                self.app.artifact_bytes_for_actor(actor, settlement_ref)
                self.app.artifact_bytes_for_actor(actor, parent['terms_ref'])
            eid = 'synthetic:f3a:repair-episode:' + stable
            receipt = self.encounters.start(self.app.branch, definition['id'], definition['version'], eid,
                self.app.key('repair-start', stable), self.app.revision(), binding, viewer=context.character_id)
            locator = {'kind': KIND, 'workspace_id': self.app.workspace_id, 'contest_id': contest_id,
                'offer_id': offer_id, 'encounter_id': eid, 'profile_activation_ref': parent['profile_activation_ref'],
                'definition_ref': definition['reference'], 'settlement_native_ref': fact['reference'],
                'settlement_ref': settlement_ref, 'start_receipt': receipt, 'terms_ref': None,
                'runtime_digest': runtime_fingerprint()}
            ref = self.exhibitions._artifact(self._offer_payload(locator, parent, repair, definition, fact),
                self.app.key('repair-offer-artifact', stable), binding.values(),
                set(binding.values()))
            locator['terms_ref'] = ref
            self.engine.register_component(KIND, stable, '1', encoded(locator), status='verified',
                readers=['samsara.exhibition_repairs'], writers=['contest.repair_offer'],
                compatibility={'format': 'samsara-repair-offer/1'}, source_hash=digest(locator),
                declared_by='samsara.exhibition_repairs')
            require(self.engine.validate_registry()['ok'], 'DEPENDENCY')
            self._load(context, contest_id, offer_id)
            return dict(self._return(locator), native_receipt=receipt, replayed=False)

    def inspect(self, context, contest_id, offer_id):
        locator, _, _, _, row, proof, choice_ref = self._load(context, contest_id, offer_id)
        state = json.loads(row['state_json']); activity = self._linked(locator)
        return dict(self._return(locator, proof, choice_ref), phase=state['phase'],
            state=state['current_state'], activity_id=activity['activity_id'] if activity else None,
            boundary='Native choice/state only; no inferred willingness, repair quality or mastery.')

    def choice(self, context, contest_id, offer_id, choice, request_id):
        require(choice in ('accepted', 'declined'))
        with UnitOfWork(self.db):
            locator, carrier, repair, definition, row, proof, choice_ref = self._load(context,
                contest_id, offer_id, positive_inputs=choice == 'accepted')
            helper = repair['encounter']['binding'][repair['helper_role']]
            require(context.character_id == helper, 'UNAVAILABLE')
            require(self._linked(locator) is None, 'DEPENDENCY')
            if proof:
                require(proof['choice'] == choice, 'CONFLICT')
                return dict(self._return(locator, proof, choice_ref), replayed=True)
            state = json.loads(row['state_json'])
            require(row['revision'] == 1 and state['phase'] == 'active' and state['steps'] == 0
                    and state['pending'] is None, 'DEPENDENCY')
            if choice == 'accepted':self._positive(carrier, repair, definition)
            action = repair['helper_accept_action'] if choice == 'accepted' else repair['helper_decline_action']
            self.encounters.act(self.app.branch, locator['encounter_id'], action,
                self.app.key('repair-choice', self.app.workspace_id, contest_id, offer_id, context.principal_id, request_id),
                self.app.revision(), fields={}, viewer=context.character_id, expected_encounter_revision=1)
            _, _, entries = self._episode(locator, definition, repair)
            proof = self._choice_proof(locator, definition, repair, entries)
            require(proof is not None and proof['choice'] == choice, 'DEPENDENCY')
            choice_ref = self.exhibitions._artifact(self._choice_payload(locator, proof),
                self.app.key('repair-choice-artifact', self._identity(contest_id, offer_id), 2),
                repair['encounter']['binding'].values(), set(repair['encounter']['binding'].values()))
            return dict(self._return(locator, proof, choice_ref), replayed=False)

    def start_operation(self, locator, definition, activity_id, choice_ref):
        require(choice_ref is not None, 'DEPENDENCY')
        return {'name': 'activity.start', 'activity_id': activity_id, 'kind': definition['kind'],
            'definition': definition['reference'], 'parent_id': None,
            'participants': list(definition['participants']),
            'purpose': 'A later voluntary bounded repair using the genuinely awarded finite material.',
            'source_refs': [locator['terms_ref'], locator['settlement_ref'], choice_ref],
            'acceptance_ref': 'synthetic:f3a:conserving-repair'}

    def attachment(self, context, ordinary_start_operation, contest_id, offer_id):
        locator, carrier, repair, definition, row, proof, choice_ref = self._load(context, contest_id, offer_id)
        require(context.character_id == repair['encounter']['binding'][repair['beneficiary_role']], 'UNAVAILABLE')
        require(proof is not None and proof['choice'] == 'accepted', 'DEPENDENCY')
        state = json.loads(row['state_json'])
        require(row['revision'] == 2 and state['steps'] == 1 and state['phase'] == 'active'
                and state['pending'] is None and self._linked(locator) is None, 'DEPENDENCY')
        require(ordinary_start_operation == self.start_operation(locator, definition,
            ordinary_start_operation['activity_id'], choice_ref), 'DEPENDENCY')
        self._positive(carrier, repair, definition)
        for actor in definition['participants']:
            self.app.artifact_bytes_for_actor(actor, locator['terms_ref'])
            self.app.artifact_bytes_for_actor(actor, locator['settlement_ref'])
            self.app.artifact_bytes_for_actor(actor, choice_ref)
        return locator

    def begin(self, context, contest_id, offer_id, activity_id):
        with UnitOfWork(self.db):
            locator, _, repair, definition, _, proof, choice_ref = self._load(context, contest_id, offer_id)
            require(context.character_id == repair['encounter']['binding'][repair['beneficiary_role']], 'UNAVAILABLE')
            require(proof is not None and proof['choice'] == 'accepted', 'DEPENDENCY')
            operation = self.start_operation(locator, definition, activity_id, choice_ref)
            activity = self.app._start(context, operation, _repair=(contest_id, offer_id))
            return dict(self._return(locator, proof, choice_ref), activity_id=activity['activity_id'])

    def guard(self, activity, action_id=None):
        tag = activity['native'].get('exhibition_repair')
        definition = self.app.catalog[activity['spec']['definition']['id']]
        require(bool(tag) == definition['id'].startswith('synthetic:f3a:repair:'), 'DEPENDENCY')
        if not tag:return
        if action_id is not None and self.app.practice.free_exit(activity, definition, action_id,
                self.app.practice.owned_geometry(activity)):
            return  # Exact native own terminal refusal; ordinary cancel/end remains separate.
        locator, carrier, repair, actual_definition, row, proof, choice_ref = self._load(_ACTIVITY_OWNER_VIEW,
            tag['contest_id'], tag['offer_id'])
        require(tag == self._tag(locator) and activity['native']['encounter_id'] == locator['encounter_id']
                and activity['spec']['definition'] == actual_definition['reference']
                and activity['spec']['participants'] == actual_definition['participants']
                and proof is not None and proof['choice'] == 'accepted', 'DEPENDENCY')
        state = json.loads(row['state_json'])
        require(state['phase'] == 'active' and state['pending'] is None, 'DEPENDENCY')
        self._linked(locator, required=True, activity_id=activity['activity_id'])
        for actor in definition['participants']:
            for ref in (locator['terms_ref'], locator['settlement_ref'], choice_ref):
                self.app.artifact_bytes_for_actor(actor, ref)
            self.exhibitions._visible(carrier, actor)

    def cancel(self, context, contest_id, offer_id, request_id):
        with UnitOfWork(self.db):
            locator, _, repair, definition, row, proof, choice_ref = self._load(context,
                contest_id, offer_id, positive_inputs=False)
            require(self._linked(locator) is None, 'DEPENDENCY')
            receipt = self.encounters.end(self.app.branch, locator['encounter_id'], context.character_id,
                self.app.key('repair-cancel', self.app.workspace_id, contest_id, offer_id, context.principal_id, request_id),
                self.app.revision(), viewer=context.character_id, expected_encounter_revision=row['revision'])
            projected = {'format': 'samsara-repair-ending/1', 'contest_id': contest_id, 'offer_id': offer_id,
                'actor': context.character_id, 'native_receipt': receipt,
                'boundary': 'Explicit unreserved native ending; no material refund or erased history.'}
            ending_ref = self.exhibitions._artifact(projected,
                self.app.key('repair-ending-artifact', self._identity(contest_id, offer_id), receipt['state_revision']),
                repair['encounter']['binding'].values(), set(repair['encounter']['binding'].values()))
            return dict(self._return(locator, proof, choice_ref), ending_ref=ending_ref, native_receipt=receipt)

    def reauthorize_replay(self, context, operation, returned):
        shape(returned, ('kind', 'operation', 'details'))
        require(returned['kind'] == 'contest' and returned['operation'] == operation['name'], 'DEPENDENCY')
        try:value = json.loads(returned['details'])
        except (TypeError, ValueError):raise Fault('DEPENDENCY') from None
        require(type(value) is dict and value.get('contest_id') == operation['contest_id']
                and value.get('offer_id') == operation['offer_id'], 'DEPENDENCY')
        name = operation['name']
        if name == 'contest.repair_inspect':
            require(returned['details'] == encoded(self.inspect(context, operation['contest_id'], operation['offer_id'])), 'UNAVAILABLE')
            return
        require(name in ('contest.repair_offer','contest.repair_choice','contest.repair_begin','contest.repair_cancel'))
        locator, _, repair, definition, row, proof, choice_ref = self._load(context,
            operation['contest_id'], operation['offer_id'], positive_inputs=False)
        require(value.get('terms_ref') == locator['terms_ref']
                and value.get('settlement_ref') == locator['settlement_ref'], 'DEPENDENCY')
        if name == 'contest.repair_offer':
            require(context.character_id == repair['encounter']['binding'][repair['beneficiary_role']], 'UNAVAILABLE')
        elif name == 'contest.repair_choice':
            require(context.character_id == repair['encounter']['binding'][repair['helper_role']], 'UNAVAILABLE')
            require(proof is not None and value.get('choice') == operation['choice'] == proof['choice']
                    and value.get('native_receipt') == proof['native_receipt']
                    and value.get('choice_ref') == choice_ref, 'DEPENDENCY')
        elif name == 'contest.repair_begin':
            require(context.character_id == repair['encounter']['binding'][repair['beneficiary_role']], 'UNAVAILABLE')
            activity = self._linked(locator, required=True, activity_id=operation['activity_id'])
            self.app.activity(context, activity['activity_id'])
            require(value.get('activity_id') == activity['activity_id'], 'DEPENDENCY')
        else:
            receipt = value.get('native_receipt');require(type(receipt) is dict, 'DEPENDENCY')
            entry = self.db.execute('SELECT * FROM encounter_events WHERE branch=? AND encounter_id=? AND revision=?',
                (self.app.branch, locator['encounter_id'], receipt.get('state_revision'))).fetchone()
            require(entry is not None and json.loads(entry['receipt_json']) == receipt, 'DEPENDENCY')
            payload = json.loads(entry['payload_json'])
            require(payload.get('operation') == 'end' and payload.get('actor') == context.character_id
                    and payload.get('viewer') == context.character_id, 'DEPENDENCY')
        for key in ('terms_ref','settlement_ref','choice_ref','ending_ref'):
            if value.get(key) is not None:self.app.artifact_bytes(context, value[key])
