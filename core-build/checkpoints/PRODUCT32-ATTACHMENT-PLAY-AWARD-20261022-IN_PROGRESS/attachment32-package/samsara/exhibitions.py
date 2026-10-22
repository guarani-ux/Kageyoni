"""Synthetic offer/own choice and private provenance-bound activity attachment.

Begin/live guards/native-derived settlement are source implemented here, not
installed or qualified. Helper repair and wider season remain outside this slice.
"""
from copy import deepcopy
import json

from kageyoni.contests import Contests, BOUNDARY, validate_resource, ContestValidationError
from kageyoni.engine import Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork
from .contentsets import shape, require, text, ContentSets
from .protocol import Fault, digest, encoded, runtime_fingerprint

KIND = 'samsara_exhibition_offer'
FORMAT = 'samsara-authored-exhibition/1'
PREFIX = 'synthetic:f3a:contest:'
# Owner preparation capability; never a participant JSON value or wire option.
_ACTIVITY_OWNER_VIEW = object()
LOCATOR = ('kind', 'workspace_id', 'contest_id', 'native_contest_id', 'encounter_id',
           'profile_activation_ref', 'definition_ref', 'terms_native_ref',
           'terms_receipt', 'terms_ref', 'runtime_digest')


class Exhibitions:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db
        self.native = Contests(self.engine)

    def _identity(self, contest_id):
        text(contest_id, 128)
        require(contest_id.startswith(PREFIX) and contest_id.strip() == contest_id)
        return self.app.key('exhibition-offer', self.app.workspace_id, contest_id)

    def _player(self, context):
        self.app.authorize(context)
        require(context.role == 'player' and type(context.character_id) is str,
                'UNAVAILABLE')
        require(self.app.content_sets.actor_admitted(context.character_id), 'UNAVAILABLE')

    def _profile(self, activation_ref):
        self.app.content_sets.reload()
        matches = [value['carrier'] for value in self.app.content_sets.sets.values()
                   if value['activation_ref'] == activation_ref
                   and value['carrier'].get('format') == FORMAT]
        require(len(matches) == 1, 'UNAVAILABLE')
        return matches[0]

    def _definition(self, carrier):
        # The exact authoring object has no caller-selectable kind. Use the
        # already adopted fixed battle/life projection before native wrapping.
        matches = [encounter for encounter in self.app.content_sets.encounters(carrier)
                   if encounter['id'] == carrier['exhibition']['id']]
        require(len(matches) == 1 and matches[0].get('kind') == 'battle', 'DEPENDENCY')
        return ContentSets.wrapper(matches[0])

    def _visible(self, carrier, actor):
        # Selected dependencies must actually be visible to this entrant.
        # Operator-only raw/preparation carriers are never a participant source.
        visible = self.app.situation.visible(actor)
        needed = {r['id'] for r in carrier['native_records']} | {
                  r['id'] for r in carrier['existing_refs']}
        require(all(rid in visible for rid in needed), 'UNAVAILABLE')

    def _load(self, context, contest_id, *, positive_inputs=True):
        # Internal readiness choice, never a wire parameter. Revocation keeps
        # genuine profile/native/artifact authority while not requiring every
        # unrelated future repair dependency to remain participant-visible.
        require(type(positive_inputs) is bool)
        owner_view = context is _ACTIVITY_OWNER_VIEW
        if not owner_view:
            self.app.authorize(context)
        stable = self._identity(contest_id)
        row = self.db.execute('SELECT * FROM registry_entries WHERE kind=? '
            'AND stable_id=? AND version=?', (KIND, stable, '1')).fetchone()
        require(row is not None, 'UNAVAILABLE')
        try: value = json.loads(row['locator'])
        except (TypeError, ValueError): raise Fault('DEPENDENCY') from None
        shape(value, LOCATOR)
        require(value['kind'] == KIND and value['workspace_id'] == self.app.workspace_id
                and value['contest_id'] == contest_id and row['status'] == 'verified'
                and row['source_hash'] == digest(value)
                and value['runtime_digest'] == runtime_fingerprint(), 'DEPENDENCY')
        carrier = self._profile(value['profile_activation_ref'])
        definition = self._definition(carrier)
        require(value['definition_ref'] == definition['reference'], 'DEPENDENCY')
        if not owner_view and context.role != 'operator':
            self._player(context)
            require(context.character_id in carrier['exhibition']['binding'].values(),
                    'UNAVAILABLE')
            if positive_inputs:
                self._visible(carrier, context.character_id)
        current = self.native.inspect(self.app.branch, value['native_contest_id'],
            viewer=None if owner_view or context.role == 'operator' else context.character_id)
        terms = current['terms']['data']['contract']
        require(current['references']['terms'] == value['terms_native_ref']
                and terms['encounter']['id'] == value['encounter_id']
                and terms['encounter']['definition_id'] == definition['id']
                and terms['encounter']['definition_version'] == definition['version']
                and terms['encounter']['definition_digest'] == digest(definition['encounter'])
                and terms['encounter']['participants'] == carrier['exhibition']['binding'],
                'DEPENDENCY')
        require(value['native_contest_id'] == PREFIX + self.app.key(
                    'exhibition-native', self.app.workspace_id, contest_id)
                and value['encounter_id'] == 'synthetic:f3a:episode:' + self.app.key(
                    'exhibition-episode', self.app.workspace_id, contest_id)
                and terms['pool']['id'] == carrier['award']['pool_id']
                and {role: ref['id'] for role, ref in terms['destinations'].items()}
                    == carrier['award']['destinations']
                and terms['amount'] == carrier['award']['amount']
                and terms['unit'] == carrier['award']['unit']
                and terms['eligible_actions'] == carrier['award']['eligible_actions'], 'DEPENDENCY')
        actual_receipt = self.native._event(self.app.branch, current['terms']['updated_event'])[2]
        require(actual_receipt == value['terms_receipt'], 'DEPENDENCY')
        # Normal artifact authority AND exact payload correspondence are separate
        # from a typed native reference or the registry's public source digest.
        expected = {'format': 'samsara-contest-offer/1', 'contest_id': contest_id,
            'native_reference': value['terms_native_ref'], 'native_receipt': actual_receipt,
            'terms': terms, 'boundary': BOUNDARY,
            'scope': 'New voluntary synthetic offer; no activity, acceptance or award yet.'}
        if owner_view:
            for actor in carrier['exhibition']['binding'].values():
                require(self.app.artifact_bytes_for_actor(actor, value['terms_ref'])
                        == encoded(expected).encode(), 'DEPENDENCY')
        else:
            require(self.app.artifact_bytes(context, value['terms_ref'])
                    == encoded(expected).encode(), 'DEPENDENCY')
        return value, carrier, current

    def reauthorize_replay(self, context, operation, returned):
        """Current read authority for an immutable historical message receipt.

        This never repeats consent, changes its old choice, or treats an old
        accepted receipt as a new acceptance after a later withdrawal.
        """
        shape(returned, ('kind', 'operation', 'details'))
        require(returned['kind'] == 'contest' and returned['operation'] == operation['name'], 'DEPENDENCY')
        try: historical = json.loads(returned['details'])
        except (TypeError, ValueError): raise Fault('DEPENDENCY') from None
        require(type(historical) is dict and historical.get('contest_id') == operation['contest_id'], 'DEPENDENCY')
        name = operation['name']
        if name == 'contest.inspect':
            # A cached projection must still be the current authorized view.
            current = self.inspect(context, operation['contest_id'])
            require(returned['details'] == encoded(current), 'UNAVAILABLE')
            return
        if name in ('contest.begin', 'contest.settle'):
            self._player(context)
            locator, _, _ = self._load(context, operation['contest_id'], positive_inputs=False)
            activity = self._linked(locator, historical.get('activity_id'))
            self.app.activity(context, activity['activity_id'])
            require(historical.get('terms_ref') == locator['terms_ref'], 'DEPENDENCY')
            if name == 'contest.begin':
                require(operation['activity_id'] == activity['activity_id']
                        and historical.get('native_reference') == locator['terms_native_ref'], 'DEPENDENCY')
            else:
                current = self.native.inspect(self.app.branch, locator['native_contest_id'],
                                              viewer=context.character_id)
                require(current['settlement'] is not None
                        and historical.get('native_reference') == current['settlement']['reference'], 'DEPENDENCY')
                self.app.artifact_bytes(context, historical['settlement_ref'])
            return
        if name == 'contest.open':
            self.app.authorize(context)
            require(context.role == 'operator', 'UNAVAILABLE')
            self.app.artifact_bytes(context, operation['activation_ref'])
        else:
            require(name == 'contest.consent')
            self._player(context)
        locator, _, _ = self._load(context, operation['contest_id'], positive_inputs=False)
        require(historical.get('terms_ref') == locator['terms_ref'], 'DEPENDENCY')
        if name == 'contest.open':
            require(locator['profile_activation_ref'] == operation['activation_ref']
                    and historical.get('native_reference') == locator['terms_native_ref'], 'DEPENDENCY')
        else:
            require(historical.get('choice') == operation['choice'], 'DEPENDENCY')
            receipt = historical.get('native_receipt')
            require(type(receipt) is dict, 'DEPENDENCY')
            try: actual = self.native._event(self.app.branch, receipt['event_id'])[2]
            except (Rejected, KeyError, TypeError, ValueError): raise Fault('DEPENDENCY') from None
            require(actual == receipt, 'DEPENDENCY')

    def _artifact(self, value, key, actors, subjects):
        principals = ['character:' + actor for actor in sorted(set(actors))]
        ref = self.app.put_json(value, key, recipients_override=principals,
                                source_refs_override=[])
        self.app.properties.attach_entities(ref, principals, subjects)
        return ref

    @staticmethod
    def _resource(image, unit, holder=None):
        try: validate_resource(image, unit, holder)
        except (ContestValidationError, KeyError, TypeError, ValueError):
            raise Fault('DEPENDENCY') from None

    def open(self, context, activation_ref, contest_id, request_id):
        self.app.authorize(context)
        require(context.role == 'operator', 'UNAVAILABLE')
        stable = self._identity(contest_id)
        with UnitOfWork(self.db):
            old = self.db.execute('SELECT 1 FROM registry_entries WHERE kind=? '
                'AND stable_id=? AND version=?', (KIND, stable, '1')).fetchone()
            if old:
                value, _, _ = self._load(context, contest_id)
                require(value['profile_activation_ref'] == activation_ref, 'CONFLICT')
                return {'contest_id': contest_id, 'terms_ref': value['terms_ref'],
                        'native_reference': value['terms_native_ref'], 'replayed': True}
            self.app.artifact_bytes(context, activation_ref)
            carrier = self._profile(activation_ref)
            encounter = carrier['exhibition']; binding = encounter['binding']
            definition = self._definition(carrier)
            require(all(self.app.content_sets.actor_admitted(a) for a in binding.values()),
                    'UNAVAILABLE')
            for actor in binding.values(): self._visible(carrier, actor)
            award = carrier['award']
            pool = self.engine.get(self.app.branch, award['pool_id'])
            self._resource(pool, award['unit'])
            destinations = {}
            for role, rid in award['destinations'].items():
                image = self.engine.get(self.app.branch, rid)
                self._resource(image, award['unit'], binding[role])
                require(image['data']['quantity'] == 0, 'DEPENDENCY')
                destinations[role] = {'id': rid, 'version': image['version']}
            # This initial slice cannot re-spend material already incorporated
            # or pretend an already repaired target is split again.
            for repair in carrier['repairs']:
                incorporated = self.engine.get(self.app.branch, repair['incorporated_id'])
                target = self.engine.get(self.app.branch, repair['target_id'])
                self._resource(incorporated, award['unit'])
                require(incorporated['data']['quantity'] == 0 and target
                        and target['domain'] == 'item'
                        and target['data']['condition'] == 'split', 'DEPENDENCY')
            native_id = PREFIX + self.app.key('exhibition-native', self.app.workspace_id, contest_id)
            eid = 'synthetic:f3a:episode:' + self.app.key(
                'exhibition-episode', self.app.workspace_id, contest_id)
            # Native instance creation is not an activity, physical event, job,
            # packet, cost, reservation or an entrant's acceptance.
            self.app.services.encounters.start(self.app.branch, definition['id'],
                definition['version'], eid, self.app.key('exhibition-open', stable),
                self.app.revision(), binding, viewer=None)
            terms = {'version': 1, 'contest_id': native_id,
                'new_synthetic_exhibition': True, 'boundary': BOUNDARY,
                'encounter': {'id': eid, 'definition_id': definition['id'],
                    'definition_version': definition['version'],
                    'definition_digest': digest(definition['encounter']),
                    'participants': deepcopy(binding)},
                'pool': {'id': pool['id'], 'version': pool['version']},
                'destinations': destinations, 'amount': award['amount'],
                'unit': award['unit'], 'eligible_actions': deepcopy(award['eligible_actions'])}
            fact = self.native.define(self.app.branch, native_id, terms,
                self.app.key('exhibition-terms', stable), self.app.revision(),
                context.principal_id, viewer=None)
            projected = {'format': 'samsara-contest-offer/1', 'contest_id': contest_id,
                'native_reference': fact['reference'], 'native_receipt': fact['native_receipt'],
                'terms': terms, 'boundary': BOUNDARY,
                'scope': 'New voluntary synthetic offer; no activity, acceptance or award yet.'}
            terms_ref = self._artifact(projected, self.app.key('exhibition-terms-artifact', stable),
                binding.values(), set(binding.values()) | {pool['id']} | set(award['destinations'].values()))
            locator = {'kind': KIND, 'workspace_id': self.app.workspace_id,
                'contest_id': contest_id, 'native_contest_id': native_id, 'encounter_id': eid,
                'profile_activation_ref': deepcopy(activation_ref),
                'definition_ref': definition['reference'], 'terms_native_ref': fact['reference'],
                'terms_receipt': fact['native_receipt'], 'terms_ref': terms_ref,
                'runtime_digest': runtime_fingerprint()}
            self.engine.register_component(KIND, stable, '1', encoded(locator), status='verified',
                readers=['samsara.exhibitions'], writers=['contest.open'],
                compatibility={'format': FORMAT}, source_hash=digest(locator),
                declared_by='samsara.exhibitions')
            require(self.engine.validate_registry()['ok'], 'DEPENDENCY')
            return {'contest_id': contest_id, 'terms_ref': terms_ref,
                    'native_reference': fact['reference'], 'replayed': False}

    def inspect(self, context, contest_id):
        self._player(context)
        locator, _, native = self._load(context, contest_id)
        # Deliberately bounded: native records/carriers do not become a wire dump.
        return {'contest_id': contest_id, 'state': native['state'],
            'terms_ref': locator['terms_ref'], 'native_reference': locator['terms_native_ref'],
            'consents': {actor: record['data']['choice'] if record else 'not_chosen'
                         for actor, record in native['consents'].items()},
            'settlement_native_ref': (native['settlement']['reference']
                                      if native['settlement'] else None),
            'boundary': BOUNDARY}

    def _submit_choice(self, context, contest_id, choice, request_id):
        require(choice in ('accepted', 'declined', 'withdrawn'))
        locator, _, _ = self._load(context, contest_id,
                                  positive_inputs=choice != 'withdrawn')
        # Native consent remains the authority for actual own accepted consent,
        # unchanged terms, allowed withdrawal state and immutable event replay.
        # No product-authored choice row or permissive fallback is introduced.
        fact = self.native.consent(self.app.branch, locator['native_contest_id'],
            context.character_id, choice, self.app.key('exhibition-consent',
                self.app.workspace_id, contest_id, context.principal_id, request_id), self.app.revision(),
            viewer=context.character_id)
        return {'contest_id': contest_id, 'terms_ref': locator['terms_ref'],
                'choice': choice, 'native_reference': fact['reference'],
                'native_receipt': fact['native_receipt'], 'replayed': fact['replayed']}

    def _withdrawal(self, context, contest_id, request_id):
        """Caller holds the ordinary command UoW; never an unguarded wire API."""
        self._player(context)
        return self._submit_choice(context, contest_id, 'withdrawn', request_id)

    def consent(self, context, contest_id, choice, request_id):
        self._player(context)
        require(choice in ('accepted', 'declined', 'withdrawn'))
        with UnitOfWork(self.db):
            if choice == 'withdrawn':
                return self._withdrawal(context, contest_id, request_id)
            return self._submit_choice(context, contest_id, choice, request_id)


    def _accepted(self, current):
        binding = current['terms']['data']['contract']['encounter']['participants']
        require(set(current['consents']) == set(binding.values())
                and all(record is not None and record['data']['choice'] == 'accepted'
                        for record in current['consents'].values()), 'DEPENDENCY')
        require(current['settlement'] is None, 'DEPENDENCY')

    def _tag(self, locator):
        return {'contest_id': locator['contest_id'], 'terms_ref': locator['terms_ref'],
                'terms_native_ref': locator['terms_native_ref']}

    def _linked(self, locator, activity_id=None):
        rows = self.db.execute("SELECT activity_id FROM activity_runs WHERE "
            "json_extract(native_json,'$.encounter_id')=?", (locator['encounter_id'],)).fetchall()
        require(len(rows) == 1, 'DEPENDENCY')
        activity = self.app.store.get(self.app.workspace_id, rows[0]['activity_id'])
        require(activity is not None and activity['workspace_id'] == self.app.workspace_id
                and activity['native'].get('exhibition') == self._tag(locator)
                and (activity_id is None or activity['activity_id'] == activity_id), 'DEPENDENCY')
        return activity

    def attachment(self, context, operation, contest_id):
        """Re-derive the only allowed existing episode, inside normal start UoW."""
        self._player(context)
        locator, carrier, current = self._load(context, contest_id)
        self._accepted(current)
        definition = self._definition(carrier)
        expected = self.start_operation(locator, definition, operation['activity_id'])
        require(operation == expected, 'DEPENDENCY')
        terms = current['terms']['data']['contract']
        try:
            self.native._pin(self.app.branch, terms, True)
            resources = self.native._resources(self.app.branch, terms)
        except Rejected:
            raise Fault('DEPENDENCY') from None
        require(resources['pool']['data']['quantity'] >= terms['amount'], 'DEPENDENCY')
        require(not self.db.execute("SELECT 1 FROM activity_runs WHERE "
            "json_extract(native_json,'$.encounter_id')=?", (locator['encounter_id'],)).fetchone(), 'CONFLICT')
        for actor in definition['participants']:
            self._visible(carrier, actor)
            self.app.artifact_bytes_for_actor(actor, locator['terms_ref'])
        view = self.app.services.encounters.inspect(self.app.branch, locator['encounter_id'], viewer=None)
        substantive = {choice['actor_id'] for choice in view['next_actions']
            if not self.app.practice.free_exit(
                {'native': {'encounter_id': locator['encounter_id']},
                 'spec': {'participants': definition['participants']}},
                definition, choice['action_id'], {})}
        require(substantive == {context.character_id}, 'UNAVAILABLE')
        return locator

    @staticmethod
    def start_operation(locator, definition, activity_id):
        return {'name': 'activity.start', 'activity_id': activity_id,
            'kind': definition['kind'], 'definition': definition['reference'],
            'parent_id': None, 'participants': list(definition['participants']),
            'purpose': 'A voluntary synthetic exhibition component; actual eligibility and award remain separate.',
            'source_refs': [locator['terms_ref']], 'acceptance_ref': 'synthetic:f3a:exhibition-component'}

    def begin(self, context, contest_id, activity_id):
        self._player(context)
        with UnitOfWork(self.db):
            locator, carrier, _ = self._load(context, contest_id)
            operation = self.start_operation(locator, self._definition(carrier), activity_id)
            activity = self.app._start(context, operation, _exhibition=contest_id)
            return {'contest_id': contest_id, 'activity_id': activity['activity_id'],
                    'terms_ref': locator['terms_ref'], 'native_reference': locator['terms_native_ref']}

    def guard(self, activity, action_id=None):
        """No new packet/nonfree native effect may outlive current consent."""
        tag = activity['native'].get('exhibition')
        definition = self.app.catalog[activity['spec']['definition']['id']]
        is_exhibition = definition['id'].startswith('synthetic:f3a:exhibition:')
        require(bool(tag) == is_exhibition, 'DEPENDENCY')
        if not tag:
            return
        if action_id is not None and self.app.practice.free_exit(activity, definition,
                action_id, self.app.practice.owned_geometry(activity)):
            # Actual native terminal refusal only; common end/cancel is separate.
            return
        locator, carrier, current = self._load(_ACTIVITY_OWNER_VIEW, tag['contest_id'])
        require(tag == self._tag(locator)
                and activity['native']['encounter_id'] == locator['encounter_id']
                and activity['spec']['definition'] == self._definition(carrier)['reference']
                and activity['spec']['participants'] == self._definition(carrier)['participants'], 'DEPENDENCY')
        self._accepted(current)
        for actor in activity['spec']['participants']:
            self._visible(carrier, actor)

    def settle(self, context, contest_id, request_id):
        self._player(context)
        with UnitOfWork(self.db):
            locator, carrier, _ = self._load(context, contest_id)
            activity = self._linked(locator)
            self.app.activity(context, activity['activity_id'])
            require(activity['state'] == 'finished', 'DEPENDENCY')
            fact = self.native.settle(self.app.branch, locator['native_contest_id'],
                context.character_id, self.app.key('exhibition-settle', self.app.workspace_id,
                    contest_id, context.principal_id, request_id), self.app.revision(),
                viewer=context.character_id)
            projected = {'format': 'samsara-contest-settlement/1', 'contest_id': contest_id,
                'native_reference': fact['reference'], 'native_receipt': fact['native_receipt'],
                'historical_resources': fact['historical_resources'], 'boundary': BOUNDARY}
            terms = fact['record']['data']
            artifact = self._artifact(projected, self.app.key('exhibition-settlement-artifact',
                self.app.workspace_id, contest_id), carrier['exhibition']['binding'].values(),
                {terms['pool'], terms['destination']})
            return {'contest_id': contest_id, 'activity_id': activity['activity_id'],
                'terms_ref': locator['terms_ref'], 'settlement_ref': artifact,
                'native_reference': fact['reference'], 'replayed': fact['replayed']}
