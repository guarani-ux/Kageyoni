"""Selected practice admission and optional fallible own accounts.

Native encounters, geometry, resources, knowledge and history are authoritative.
An account can inform a later choice; it never changes the combat rules.
"""
from .protocol import Fault, validate
from .situation import reference
from .practice_content import SOURCE

ACCOUNT_PREFIX = 'practice-account:'
READINGS = {
    'pressure': ('believes', 'Pressing at blade contact may work for me next time. This is my present reading, not a new power or guarantee.'),
    'release': ('suspects', 'Releasing contact and changing the line may help next time. The other participant can still give ground or counter.'),
    'uncertain': ('unknown', 'I am leaving this exchange open to further observation rather than claiming a lesson.')}


class Practice:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db

    def physical_combat(self, definition):
        """Classify physical admission from legacy flags and exact admitted effects."""
        if definition.get('combat'):
            return True
        admitted = self.app.content_sets.definitions.get(definition.get('id'))
        return (admitted is not None and admitted == definition
                and admitted.get('handler') == 'encounter'
                and (admitted.get('kind') == 'battle' or admitted.get('recovery') is True
                     or self.scene_producer(admitted)))

    def scene_producer(self, definition):
        """Inspect actual compiled effects, never role names or ID prefixes.

        Called for authenticated ContentSets wrappers only. Encounter-local
        patches are covered by their corresponding typed create payloads;
        literal patches need the existing native record's actual domain.
        """
        for action in definition['encounter']['actions'].values():
            for change in action.get('payload', {}).get('changes', []):
                if change.get('op') == 'create' and change.get('domain') in ('scene', 'participation'):
                    return True
                if change.get('op') != 'patch' or not isinstance(change.get('id'), str):
                    continue
                record = self.engine.get(self.app.branch, change['id'])
                if not record:
                    continue
                data = change.get('data', {})
                if record['domain'] == 'scene' and set(data) & {'location', 'clock', 'phase', 'round', 'context', 'hazards'}:
                    return True
                if record['domain'] == 'participation' and set(data) & {'scene', 'character', 'position', 'initiative', 'actions_remaining', 'active_effects'}:
                    return True
        return False

    def admitted_recovery(self, definition):
        admitted = self.app.content_sets.definitions.get(definition.get('id'))
        return (admitted is not None and admitted == definition
                and admitted.get('handler') == 'encounter'
                and admitted.get('recovery') is True)

    def touched_actors(self, definition, participants, encounter_id, actions):
        """Bound actors plus actual members/old-new attachments of touched geometry."""
        from kageyoni.workspaces.world import _expand
        expanded = _expand(definition['encounter'],
            self.app.exploration.bindings(definition, participants), encounter_id)
        actors = set(participants)
        for aid in actions:
            for change in expanded['actions'].get(aid, {}).get('payload', {}).get('changes', []):
                if change.get('op') not in ('create', 'patch'):
                    continue
                record = self.engine.get(self.app.branch, change.get('id'))
                domain = record['domain'] if record else change.get('domain')
                data = change.get('data', {})
                if domain == 'scene':
                    for row in self.db.execute('SELECT character FROM participation WHERE branch=? AND scene=?',
                            (self.app.branch, change['id'])):
                        actors.add(row[0])
                if domain == 'participation':
                    previous = record['data'] if record else {}
                    for actor in (previous.get('character'), data.get('character', previous.get('character'))):
                        if actor:
                            actors.add(actor)
        return actors

    def reservation_clear(self, actors, exclude_own_activity=None):
        """Shared admission/commit guard, released by native terminal phase only."""
        actors = set(actors)
        for row in self.db.execute('SELECT activity_id FROM activity_runs WHERE workspace_id=?', (self.app.workspace_id,)):
            if row[0] == exclude_own_activity:
                continue
            old = self.app.store.get(self.app.workspace_id, row[0])
            prior = self.app.catalog.get(old['spec']['definition']['id'], {})
            if not self.physical_combat(prior):
                continue
            eid = old['native'].get('encounter_id')
            affected = self.touched_actors(prior, old['spec']['participants'],
                                          eid or ('unprepared:' + prior['id']),
                                          prior['encounter']['actions'])
            if not actors & affected:
                continue
            if not eid:
                raise Fault('RECONCILE_REQUIRED')
            native = self.app.services.encounters.inspect(self.app.branch, eid, viewer=None)
            if native['phase'] not in ('completed', 'failed'):
                raise Fault('BUSY')

    def admit(self, context, definition, participants):
        if not self.physical_combat(definition):
            return
        if self.admitted_recovery(definition) and len(participants) != 1:
            raise Fault('INVALID')
        if definition.get('combat'):
            actor = context.character_id or participants[0]
            records = self.app.situation.visible(actor)
            if SOURCE not in records:
                raise Fault('UNAVAILABLE')
            if definition.get('rematch') and not self.history(actor, records)[0]:
                raise Fault('DEPENDENCY')
        actors = self.touched_actors(definition, participants, 'admission:' + definition['id'],
                                    definition['encounter']['actions'])
        self.app.exploration.movement_clear(actors)
        self.reservation_clear(actors)

    def owned_geometry(self, activity):
        return {row['record_id']: row['domain'] for row in self.db.execute("""SELECT c.record_id,
            json_extract(c.after_json,'$.domain') AS domain
            FROM encounter_events h JOIN events e
              ON e.id=json_extract(h.receipt_json,'$.world_receipt.event_id')
            JOIN changes c ON c.event_id=e.id
            WHERE h.branch=? AND e.branch=? AND h.encounter_id=?
              AND c.before_json IS NULL
              AND json_extract(c.after_json,'$.domain') IN ('scene','participation')""",
            (self.app.branch, self.app.branch, activity['native']['encounter_id']))}

    def free_exit(self, activity, definition, action_id, owned):
        """Real terminal refusal with own report/exact native ending cleanup only."""
        from kageyoni.workspaces.world import _expand
        raw = definition['encounter']
        action = raw['actions'].get(action_id)
        if not action:
            return False
        terminal = raw['states'].get(action.get('next_state'), {})
        if (action.get('kind') != 'event' or terminal.get('phase') not in ('completed', 'failed')
                or terminal.get('outcome') != 'not_achieved'
                or any(action.get(k) for k in ('resolve_loops', 'detach_loops', 'cancel_loops'))):
            return False
        observations = action.get('payload', {}).get('observations', [])
        if observations:
            # The retained built-in personal rest records the chooser's own
            # explicit decision. That is not another physical effect or a
            # claim about somebody else's perception. Keep its immutable spec
            # and require the exact self-only declaration shape; arbitrary
            # authored observations are not a free-exit exemption.
            from .practice_content import _recovery_spec
            if not (definition.get('combat') and definition.get('recovery')
                    and definition.get('independent_entry') and len(observations) == 1
                    and definition.get('id') == 'synthetic:practice_recover'
                    and raw == _recovery_spec()):
                return False
            own = {'$role': action['actor_role']}
            for observation in observations:
                if (set(observation) != {'id', 'observer_id', 'subject_id', 'assertion',
                        'certainty', 'visibility', 'audience'}
                        or not isinstance(observation['id'], dict)
                        or set(observation['id']) != {'$encounter'}
                        or observation['observer_id'] != own or observation['subject_id'] != own
                        or observation['audience'] != [own] or observation['visibility'] != 'restricted'
                        or observation['certainty'] != 'declared_choice'
                        or observation['assertion'] != action['label']):
                    return False
        expanded = _expand(raw, self.app.exploration.bindings(definition, activity['spec']['participants']),
                           activity['native']['encounter_id'])
        expanded_changes = expanded['actions'][action_id]['payload'].get('changes', [])
        raw_changes = action.get('payload', {}).get('changes', [])
        ending = raw.get('ending', {}).get('changes', [])
        for change, current in zip(raw_changes, expanded_changes):
            own_report = (change.get('op') == 'create' and change.get('domain') == 'historical_account'
                and isinstance(change.get('id'), dict) and set(change['id']) == {'$encounter'}
                and change.get('data', {}).get('author') == {'$role': action['actor_role']}
                and change.get('status') in ('reported', 'proposed'))
            speech = change.get('data', {})
            listeners = speech.get('listeners')
            own_spoken_exit = (change.get('op') == 'create'
                and change.get('domain') == 'dialogue_turn'
                and isinstance(change.get('id'), dict) and set(change['id']) == {'$encounter'}
                and set(speech) == {'speaker', 'listeners', 'act', 'text', 'mode'}
                and speech['speaker'] == {'$role': action['actor_role']}
                and speech['mode'] == 'spoken'
                and isinstance(listeners, list)
                and all(isinstance(listener, dict) and set(listener) == {'$role'}
                        and listener['$role'] in raw['roles'] for listener in listeners)
                and change.get('status') in ('reported', 'proposed'))
            # Spoken refusal remains subject to the compiled native presence
            # requirements for every speaker/listener. This bypasses only a
            # competing physical reservation, never presence or material costs.
            cleanup_domain = owned.get(current.get('id'))
            data = current.get('data', {})
            lowers_geometry = ((cleanup_domain == 'scene' and data.get('phase') == 'closed'
                    and set(data) <= {'phase', 'context'})
                or (cleanup_domain == 'participation' and data.get('actions_remaining') == 0
                    and set(data) <= {'position', 'actions_remaining', 'active_effects'}
                    and data.get('active_effects', '') in ('', None)))
            own_cleanup = (change.get('op') == 'patch' and change in ending and lowers_geometry)
            if not (own_report or own_spoken_exit or own_cleanup):
                return False
        return len(raw_changes) == len(expanded_changes)

    def guard(self, activity, action_id):
        """Guard every non-free physical continuation before dispatcher writes."""
        definition = self.app.catalog[activity['spec']['definition']['id']]
        if not self.physical_combat(definition) or action_id not in definition['encounter']['actions']:
            return
        owned = self.owned_geometry(activity)
        if self.free_exit(activity, definition, action_id, owned):
            return
        from kageyoni.workspaces.world import _expand
        bound = self.app.exploration.bindings(definition, activity['spec']['participants'])
        expanded = _expand(definition['encounter'], bound, activity['native']['encounter_id'])
        action = expanded['actions'][action_id]
        recovery = (self.admitted_recovery(definition)
                    or (definition.get('combat') and definition.get('recovery')))
        if recovery:
            chooser = bound.get(action.get('actor_role'))
            actors = self.touched_actors(definition, activity['spec']['participants'],
                                        activity['native']['encounter_id'], [action_id])
            if definition.get('combat') and definition.get('recovery'):
                # Trusted legacy rest actions have only own quantity effects.
                actors = {chooser} if chooser else set()
            for change in action.get('payload', {}).get('changes', []):
                record = self.engine.get(self.app.branch, change.get('id'))
                domain = record['domain'] if record else change.get('domain')
                if domain != 'resource' or change.get('op') not in ('create', 'patch'):
                    continue
                previous = record['data'] if record else {}
                holder = change.get('data', {}).get('holder', previous.get('holder'))
                if (not chooser or holder != chooser or (record and previous.get('holder') != holder)
                        or (self.admitted_recovery(definition) and activity['spec']['participants'] != [chooser])):
                    raise Fault('UNAVAILABLE')
            # Legacy recovery binds both people, but only the chosen person's
            # actual rest effect is checked; no compelled other-person rest.
        else:
            actors = self.touched_actors(definition, activity['spec']['participants'],
                                        activity['native']['encounter_id'], [action_id])
        self.reservation_clear(actors, exclude_own_activity=activity['activity_id'])
        for actor in actors:
            for row in self.db.execute("""SELECT s.id FROM participation p
                JOIN scene s ON s.branch=p.branch AND s.id=p.scene
                JOIN records pr ON pr.branch=p.branch AND pr.id=p.id AND pr.domain='participation'
                JOIN records sr ON sr.branch=s.branch AND sr.id=s.id AND sr.domain='scene'
                WHERE p.branch=? AND p.character=? AND s.phase!='closed'""",
                (self.app.branch, actor)):
                if owned.get(row[0]) != 'scene':
                    raise Fault('BUSY')

    def history(self, actor, records, source_refs=()):
        """Deliver actual earlier native results independently of own belief.

        Producer membership, native receipt and scene creation are checked;
        user-authored JSON claiming to be an accepted result is not history.
        Current permission filtering precedes the four-result output bound.
        """
        import json
        if SOURCE not in records:
            return [], set()
        requested = {r['id'] for r in source_refs}
        candidates = []
        for row in self.db.execute('SELECT activity_id FROM activity_runs WHERE workspace_id=?', (self.app.workspace_id,)):
            activity = self.app.store.get(self.app.workspace_id, row[0])
            definition = self.app.catalog.get(activity['spec']['definition']['id'], {})
            if actor not in activity['spec']['participants'] or not definition.get('combat') or definition.get('recovery'):
                continue
            eid = activity['native'].get('encounter_id')
            scene = records.get(str(eid) + ':practice-scene')
            if not scene or scene['domain'] != 'scene' or scene['data'].get('phase') != 'closed':
                continue
            for ref in reversed(activity['native'].get('accepted_result_refs', [])):
                try:
                    value = json.loads(self.app.artifact_bytes_for_actor(actor, ref))
                except (Fault, ValueError):
                    continue
                receipt = value.get('native_receipt') or {}
                if value.get('kind') != 'accepted_encounter' or receipt.get('phase') not in ('completed', 'failed'):
                    continue
                event_id = value.get('native_event_id')
                native = self.db.execute('''SELECT 1 FROM encounter_events h
                    WHERE h.branch=? AND h.encounter_id=?
                    AND json_extract(h.receipt_json,'$.world_receipt.event_id')=?''',
                    (self.app.branch, eid, event_id)).fetchone()
                created = self.db.execute('''SELECT 1 FROM encounter_events h JOIN changes c
                    ON c.event_id=json_extract(h.receipt_json,'$.world_receipt.event_id')
                    WHERE h.branch=? AND h.encounter_id=? AND c.record_id=?
                    AND c.before_json IS NULL LIMIT 1''', (self.app.branch, eid, scene['id'])).fetchone()
                if not native or not created:
                    continue
                candidates.append((value['revision_after'], ref, value, scene))
                break
        candidates.sort(key=lambda x: (x[1]['id'] in requested, x[0], x[1]['id']), reverse=True)
        values, scope = [], set()
        for _, ref, value, scene in candidates[:4]:
            image = next((c['after'] for c in value['changes'] if c['record_id'] == scene['id'] and c['after']), None)
            if image is None or image['domain'] != 'scene':
                continue
            values.append({'reference': ref, 'scene': reference(scene),
                'description': value['description'], 'native_event_id': value['native_event_id'],
                'result': image['data'].get('context') or ''})
            scope.update((actor, SOURCE, scene['id']))
        return values, scope

    def prior(self, context, activity_id):
        if context.role != 'player' or not context.character_id:
            raise Fault('UNAVAILABLE')
        activity = self.app.activity(context, activity_id)
        definition = self.app.catalog.get(activity['spec']['definition']['id'], {})
        if not definition.get('combat') or definition.get('recovery') or definition.get('reference') != activity['spec']['definition']:
            raise Fault('UNAVAILABLE')
        eid = activity['native'].get('encounter_id')
        state = self.app.services.encounters.inspect(self.app.branch, eid, viewer=context.character_id)
        if state['phase'] not in ('completed', 'failed'):
            raise Fault('DEPENDENCY')
        records = self.app.situation.visible(context.character_id)
        scene = records.get(eid + ':practice-scene')
        participant = records.get(eid + ':practice-' + context.character_id)
        if SOURCE not in records or not scene or scene['domain'] != 'scene' or not participant or participant['domain'] != 'participation' or participant['data'].get('scene') != scene['id'] or participant['data'].get('character') != context.character_id:
            raise Fault('UNAVAILABLE')
        # Before-consent refusal and arbitrary finished activities supply no
        # basis. Require the reviewed native encounter's actual scene creation.
        created = self.db.execute('''SELECT e.id FROM changes c JOIN events e ON e.id=c.event_id
            JOIN encounter_events h ON json_extract(h.receipt_json,'$.world_receipt.event_id')=e.id
            WHERE e.branch=? AND h.branch=? AND h.encounter_id=? AND c.record_id=? AND c.before_json IS NULL
            AND json_extract(c.after_json,'$.domain')='scene' LIMIT 1''',
            (self.app.branch, self.app.branch, eid, scene['id'])).fetchone()
        if not created:
            raise Fault('UNAVAILABLE')
        result_ref = None
        for ref in reversed(activity['native'].get('accepted_result_refs', [])):
            import json
            value = json.loads(self.app.artifact_bytes(context, ref))
            if value.get('kind') == 'accepted_encounter' and value.get('native_event_id') and any(c['record_id'] == scene['id'] and c['after'] is not None for c in value['changes']):
                result_ref = ref
                break
        if result_ref is None:
            raise Fault('UNAVAILABLE')
        return activity, records, scene, result_ref

    def accounts(self, actor, records):
        account = records.get(ACCOUNT_PREFIX + actor)
        if not account or account['domain'] != 'knowledge' or account['data'].get('holder') != actor or SOURCE not in records:
            return [], set()
        scene = records.get(account['data'].get('subject'))
        if not scene or scene['domain'] != 'scene':
            return [], set()
        # Native knowledge.subject/basis are text, so neither generic native
        # ref scrubbing nor an entity-only scope replaces this source check.
        # The authorized native context deliberately omits owner metadata.
        # Read only this already-visible own record's provenance, then check
        # the referenced artifact as the participant; never copy its evidence.
        provenance = self.engine.get(self.app.branch, account['id'])
        source = next((e.get('source_ref') for e in provenance.get('evidence', [])
            if isinstance(e, dict) and isinstance(e.get('source_ref'), dict)), None)
        if source is None:
            return [], set()
        try:
            validate(source, 'Reference')
            import json
            prior = json.loads(self.app.artifact_bytes_for_actor(actor, source))
            validate(prior, 'EncounterTrace')
        except (Fault, ValueError):
            return [], set()
        image = next((c['after'] for c in prior.get('changes', [])
            if c['record_id'] == scene['id'] and c['after']), None)
        if image is None or image['domain'] != 'scene':
            return [], set()
        value = {'reference': reference(account), 'prior_scene': reference(scene),
            'assertion': account['data']['assertion'], 'attitude': account['data']['attitude'],
            'basis': account['data'].get('basis') or '', 'prior_result': image['data'].get('context') or '',
            'source_ref': source}
        return [value], {actor, account['id'], scene['id'], SOURCE}

    def account(self, context, operation, request_id):
        activity, records, scene, result_ref = self.prior(context, operation['activity_id'])
        actor = context.character_id
        if operation['interpretation'] != 'unchanged':
            attitude, assertion = READINGS[operation['interpretation']]
            rid = ACCOUNT_PREFIX + actor
            old = self.engine.get(self.app.branch, rid)
            if old and (old['domain'] != 'knowledge' or old['data'].get('holder') != actor):
                raise Fault('DEPENDENCY')
            data = {'holder': actor, 'subject': scene['id'], 'assertion': assertion, 'attitude': attitude,
                'basis': 'My optional fallible reading of this actual native practice scene; it grants no bonus or cooperation.'}
            change = {'op': 'patch' if old else 'create', 'id': rid, 'data': data,
                'visibility': 'restricted', 'audience': [actor],
                'evidence': [{'note': 'Participant selected an interpretation after an actual consented native practice.',
                    'activity_id': activity['activity_id'], 'scene_id': scene['id'], 'source_ref': result_ref}]}
            if old:
                change['expected_version'] = old['version']
            else:
                change.update(domain='knowledge', status='reported')
            self.engine.apply({'api_version': 3, 'branch': self.app.branch,
                'request_id': self.app.key(context.principal_id, request_id, 'practice-account'),
                'expected_revision': self.app.revision(), 'kind': 'action', 'actor': actor,
                'narrative': 'Record an optional private fallible practice account.', 'changes': [change]})
            records = self.app.situation.visible(actor)
        accounts, scope = self.accounts(actor, records)
        scope.update((actor, scene['id'], SOURCE))
        value = {'kind': 'practice_account_record', 'activity_id': activity['activity_id'],
            'account': accounts[0] if accounts else None, 'interpretation_changed': operation['interpretation'] != 'unchanged',
            'prior_result_ref': result_ref,
            'boundary': 'An optional own belief or uncertainty; no mastery, bonus, consent, opponent knowledge or completed purpose follows.'}
        ref = self.app.put_json(value, self.app.key(context.principal_id, request_id, 'account-record'), principals=[context.principal_id], source_refs_override=[result_ref], private_viewer=actor)
        self.app.properties.attach_entities(ref, [context.principal_id], scope)
        self.app.properties.inherit(ref, [context.principal_id], [result_ref])
        result = {'kind': 'practice_account', 'account_ref': ref, 'account': value['account'],
            'interpretation_changed': value['interpretation_changed']}
        validate(result, 'PracticeAccountView')
        return result
