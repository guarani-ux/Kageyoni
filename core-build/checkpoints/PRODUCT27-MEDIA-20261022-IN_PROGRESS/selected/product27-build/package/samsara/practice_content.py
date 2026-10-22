"""An optional, explicitly synthetic two-exchange studio practice.

The native encounter definition is the rule. Native items, loadouts, resource
quantities and per-episode scene/participation records are its actual material.
No character rating, automatic learning, injury or private appraisal is awarded.
"""
from copy import deepcopy

SOURCE = 'studio-practice-source'
ITEMS = {role: role + '-practice-stick' for role in ('visitor', 'keeper')}
LOADOUTS = {role: role + '-practice-loadout' for role in ('visitor', 'keeper')}
EFFORT = {role: role + '-practice-effort' for role in ('visitor', 'keeper')}
EFFORT_UNIT = 'practice exertion'
SCENE = {'$encounter': 'practice-scene'}
PARTICIPATION = {role: {'$encounter': 'practice-' + role} for role in ('visitor', 'keeper')}

PRACTICE_TERMS = (
    'Optional marked studio practice with two sound padded sticks, separately held and equipped. '
    'A light sleeve touch ends the exercise without injury, payment, rank, mastery or relationship award. '
    'The initial material gives each person three practice exertions; a later practice keeps the current remaining quantity without refreshing it. A committed high advance, blade meeting, '
    'continued press, inside step, high turn or final touch costs its actor exactly one exertion; '
    'ordinary release, yielding the line, stepping away and calling stop cost zero. '
    'A declaration alone cannot touch while the other person has a response. '
    'First exchange: visitor advances high; keeper may give ground with no touch or meet the blade. '
    'Second exchange from actual contact: visitor may release with no touch, press and extend, '
    'or release the contact and step inside. Against a press, keeper may yield and turn outside '
    'the extended blade, then choose a countertouch or step away. Against the inside step, '
    'keeper may give ground or turn the stick high; that high response leaves a low opening '
    'which visitor must separately choose and pay to touch. Neither remembered approach guarantees a touch. '
    'Either participant may end practice; the current chooser always has an ordinary stop. '
    'At most two spatial exchanges, no injury or ongoing equipment reservation. '
    'Explicit fictional rest restores only the choosing person to three exertions after practice is closed; '
    'wall time, another person resting and retelling a result restore nothing.'
)
EVIDENCE = [{'note': 'Authored public R05b synthetic practice from studio-practice-source. New events only; not recovered canon, historical combat, mastery or inferred respect.'}]

OUTSIDE_VISITOR = 'Visitor on the near studio mark, outside sleeve-touch reach, stick held high.'
OUTSIDE_KEEPER = 'Keeper on the far studio mark, outside sleeve-touch reach, stick on the centre line.'
ADVANCED_VISITOR = 'Visitor has advanced along the high line to the edge of reach; no touch has landed.'
ADVANCED_KEEPER = 'Keeper still has the centre line and a separate response to the high advance.'
CONTACT_VISITOR = 'Visitor high blade is met; both sticks are in actual light contact at sleeve-touch reach.'
CONTACT_KEEPER = 'Keeper has met the high blade; both sticks are in actual light contact at sleeve-touch reach.'
EXTENDED_VISITOR = 'Visitor is pressing along the high contact with arm and weight extended; the outside line is exposed.'
EXTENDED_KEEPER = 'Keeper feels the continued high pressure and can yield or stop; no countertouch has landed.'
COUNTER_VISITOR = 'Visitor remains extended along the former contact line while keeper is outside that stick.'
COUNTER_KEEPER = 'Keeper has yielded the pressure and turned outside the extended blade, with a counter line open.'
INSIDE_VISITOR = 'Visitor has released blade contact and stepped to the inside at close range, stick below the high line.'
INSIDE_KEEPER = 'Keeper faces a close inside step after the contact was released; no touch has landed.'
OPENING_VISITOR = 'Visitor remains inside at close range, with a low sleeve opening after the keeper turned high.'
OPENING_KEEPER = 'Keeper has turned the stick high against the inside step, leaving the low sleeve opening.'


def _record(domain, rid, **data):
    return {'op': 'create', 'domain': domain, 'id': deepcopy(rid), 'data': data,
            'status': 'proposed', 'visibility': 'public', 'evidence': deepcopy(EVIDENCE)}


def _patch(rid, **data):
    return {'op': 'patch', 'id': deepcopy(rid), 'data': data, 'evidence': deepcopy(EVIDENCE)}


def _require(rid, field, value):
    return {'record_id': deepcopy(rid), 'field': field, 'equals': value}


def _present():
    return [_require(SOURCE, 'phase', 'open'), _require({'$role': 'visitor'}, 'location', 'studio'),
            _require({'$role': 'keeper'}, 'location', 'studio')]


def _equipped():
    requirements = []
    for role in ('visitor', 'keeper'):
        requirements.extend([
            _require(ITEMS[role], 'condition', 'sound'),
            _require(ITEMS[role], 'kind', 'padded studio practice stick'),
            _require(LOADOUTS[role], 'item', ITEMS[role]),
            _require(LOADOUTS[role], 'holder', {'$role': role}),
            _require(LOADOUTS[role], 'slot', 'practice hand'),
            _require(LOADOUTS[role], 'equipped', 1)])
    return requirements


def _geometry(visitor, keeper, turn):
    return [_patch(PARTICIPATION['visitor'], position=visitor,
                   active_effects='Marked practice; no touch yet.', actions_remaining=int(turn == 'visitor')),
            _patch(PARTICIPATION['keeper'], position=keeper,
                   active_effects='Marked practice; no touch yet.', actions_remaining=int(turn == 'keeper'))]


def _at_geometry(visitor, keeper):
    return [_require(SCENE, 'phase', 'active'),
            _require(PARTICIPATION['visitor'], 'position', visitor),
            _require(PARTICIPATION['keeper'], 'position', keeper)]


def _cleanup():
    # Shared equipment and effort are never reserved, restored or erased here.
    return [_patch(SCENE, phase='closed'),
            *[_patch(PARTICIPATION[role], position='Outside marked practice; no maintained position.', active_effects='', actions_remaining=0)
              for role in ('visitor', 'keeper')]]


def _closed_context(text):
    changes = _cleanup()
    changes[0]['data']['context'] = text
    return changes


def _event(aid, label, role, target, *, changes=(), requirements=(), speech=None):
    effects = deepcopy(list(changes))
    if speech is not None:
        effects.append(_record('dialogue_turn', {'$encounter': 'practice-turn-' + aid},
            speaker={'$role': role}, listeners=[{'$role': 'keeper' if role == 'visitor' else 'visitor'}],
            act=aid, text=speech, mode='spoken'))
    return {'label': label, 'actor_role': role, 'kind': 'event',
            'payload': {'changes': effects, 'observations': [{
                'id': {'$encounter': 'practice-choice-' + aid},
                'observer_id': {'$role': role}, 'subject_id': {'$role': role},
                'assertion': speech if speech is not None else label,
                'certainty': 'declared_choice', 'visibility': 'restricted', 'audience': [{'$role': role}]}]},
            'next_state': target, 'resolve_loops': [], 'requirements': deepcopy(list(requirements))}


def _charged(actions, stem, label, role, target, changes, positions):
    """Native equality guards and atomic fixed arithmetic, not a hidden purse.

    Only quantities 1, 2 and 3 admit an exertion. Each authored variant has a
    precise precondition and replacement, so missing, zero, negative, fractional
    or differently typed quantities cannot silently acquire a default budget.
    """
    ids = []
    for quantity in (1, 2, 3):
        aid = stem + '_' + str(quantity)
        actions[aid] = _event(aid, label + ' Cost: 1 of your practice exertions.', role, target,
            changes=[_patch(EFFORT[role], quantity=quantity - 1), *deepcopy(changes)],
            requirements=[*_present(), *_equipped(), *_at_geometry(*positions),
                _require(EFFORT[role], 'holder', {'$role': role}), _require(EFFORT[role], 'unit', EFFORT_UNIT),
                _require(EFFORT[role], 'quantity', quantity)])
        ids.append(aid)
    return ids


def _terminal(outcome):
    return {'phase': 'completed', 'outcome': outcome, 'actions': []}


def _practice_spec(rematch=False):
    offer = ('Offer another marked practice, keeping earlier results and current remaining exertions.'
             if rematch else 'Offer the optional marked practice; both people must separately consent.')
    actions = {
        'offer': _event('offer', offer + ' Terms: ' + PRACTICE_TERMS, 'visitor', 'consent',
            speech='Would you like a marked, nonlethal practice under these terms? You can decline; I can stop too.',
            requirements=_present()),
        'decline': _event('decline', 'Decline practice and leave the afternoon free. Cost: 0.', 'visitor', 'withdrawn',
            speech='Not now. I would rather keep the afternoon open.'),
        'keeper_decline': _event('keeper_decline', 'Decline the offered practice and keep drawing. Cost: 0.', 'keeper', 'withdrawn',
            speech='I will keep drawing today. There is nothing you owe me for asking.'),
        'accept': _event('accept', 'Separately accept these nonlethal terms and take the two outside marks. Cost: 0. Terms: ' + PRACTICE_TERMS,
            'keeper', 'outside', requirements=[*_present(), *_equipped()],
            speech='Yes, this marked exercise only, using our current remaining exertions without refreshing them. No injury or award, and either of us can stop.',
            changes=[_record('scene', SCENE, name='Marked studio stick practice', location='studio',
                phase='active', round=1,
                context='Both separately consented and took the outside marks. No declaration, expenditure or touch yet.',
                hazards='Padded sticks and light sleeve touches only; no injury, rank or automatic appraisal.'),
                _record('participation', PARTICIPATION['visitor'], scene=SCENE, character={'$role': 'visitor'},
                        position=OUTSIDE_VISITOR, actions_remaining=1, active_effects='Marked practice; no touch yet.'),
                _record('participation', PARTICIPATION['keeper'], scene=SCENE, character={'$role': 'keeper'},
                        position=OUTSIDE_KEEPER, actions_remaining=0, active_effects='Marked practice; no touch yet.')]),
    }
    for role in ('visitor', 'keeper'):
        aid = role + '_stop'
        actions[aid] = _event(aid, 'Call stop and release this marked practice without a touch. Cost: 0.', role, 'withdrawn',
            changes=_closed_context('The ' + role + ' called stop. Practice closed without a touch; accepted expenditures remain spent.'),
            speech='Stop there, please. I am leaving this practice.' )
    advance = _charged(actions, 'advance_high',
        'Advance from the outside mark along the high line; keeper still has a separate response.',
        'visitor', 'high_response',
        [_patch(SCENE, context='Visitor paid one exertion to advance high to the edge of reach. Keeper response is unresolved; no touch.'),
         *_geometry(ADVANCED_VISITOR, ADVANCED_KEEPER, 'keeper')], (OUTSIDE_VISITOR, OUTSIDE_KEEPER))
    meet = _charged(actions, 'meet_blade',
        'Meet the actual high advance with your padded stick, establishing light blade contact without a touch.',
        'keeper', 'contact',
        [_patch(SCENE, context='Keeper paid one exertion to meet the high advance. The sticks are in light contact; visitor can release, press or step inside. No touch.'),
         *_geometry(CONTACT_VISITOR, CONTACT_KEEPER, 'visitor')], (ADVANCED_VISITOR, ADVANCED_KEEPER))
    actions['give_ground_high'] = _event('give_ground_high', 'Give ground from the high advance, outside touch reach. Cost: 0.', 'keeper', 'no_touch',
        requirements=_at_geometry(ADVANCED_VISITOR, ADVANCED_KEEPER),
        changes=_closed_context('Keeper gave ground against the high advance. Practice ended outside reach with no touch; the visitor advance remains spent.'))
    actions['release_contact'] = _event('release_contact', 'Release the actual blade contact and step away without a touch. Cost: 0.', 'visitor', 'no_touch',
        requirements=_at_geometry(CONTACT_VISITOR, CONTACT_KEEPER),
        changes=_closed_context('Visitor released the light blade contact and stepped away. No touch; both accepted expenditures remain spent.'))
    press = _charged(actions, 'press',
        'Continue pressing along the met high blade; commit arm and weight, exposing the outside line.',
        'visitor', 'extended_response',
        [_patch(SCENE, round=2, context='Visitor paid one exertion to continue pressing the met high blade and is now extended. Keeper has the second exchange response; no touch.'),
         *_geometry(EXTENDED_VISITOR, EXTENDED_KEEPER, 'keeper')], (CONTACT_VISITOR, CONTACT_KEEPER))
    inside = _charged(actions, 'release_step_inside',
        'Release the actual blade contact and spend an exertion to step inside below the high line; wait for keeper response.',
        'visitor', 'inside_response',
        [_patch(SCENE, round=2, context='Visitor paid one exertion to release the contact and step inside below the high line. Keeper can give ground or turn high; no touch.'),
         *_geometry(INSIDE_VISITOR, INSIDE_KEEPER, 'keeper')], (CONTACT_VISITOR, CONTACT_KEEPER))
    actions['yield_turn'] = _event('yield_turn',
        'Yield the high pressure and turn outside the extended blade; this opens a counter line but lands no touch. Cost: 0.',
        'keeper', 'counter_opening', requirements=_at_geometry(EXTENDED_VISITOR, EXTENDED_KEEPER),
        changes=[_patch(SCENE, context='Keeper yielded the pressure and turned outside the extended visitor blade. The second exchange now offers keeper a separate countertouch or withdrawal; no touch yet.'),
                 *_geometry(COUNTER_VISITOR, COUNTER_KEEPER, 'keeper')])
    counter = _charged(actions, 'counter_touch',
        'Use the actual outside counter line for one light touch to the extended visitor sleeve, then close practice.',
        'keeper', 'keeper_touch',
        _closed_context('Keeper paid one exertion and touched the visitor sleeve from the outside counter line after the visitor pressed into extension. No injury. Practice closed; all accepted expenditures remain spent.'),
        (COUNTER_VISITOR, COUNTER_KEEPER))
    actions['back_out'] = _event('back_out', 'Leave the actual counter line and step away without touching. Cost: 0.', 'keeper', 'no_touch',
        requirements=_at_geometry(COUNTER_VISITOR, COUNTER_KEEPER),
        changes=_closed_context('Keeper chose to back out of the counter line instead of touching. Practice closed with no touch; accepted expenditures remain spent.'))
    actions['give_ground_inside'] = _event('give_ground_inside', 'Give ground against the inside step and leave sleeve-touch reach. Cost: 0.', 'keeper', 'no_touch',
        requirements=_at_geometry(INSIDE_VISITOR, INSIDE_KEEPER),
        changes=_closed_context('Keeper gave ground against the inside step. The remembered inside approach did not produce a touch. Practice closed; accepted expenditures remain spent.'))
    turn = _charged(actions, 'turn_high',
        'Turn the stick high against the close inside step; this leaves a low opening which visitor must separately choose to use.',
        'keeper', 'visitor_opening',
        [_patch(SCENE, context='Keeper paid one exertion to turn the stick high against the inside step. Visitor has a low sleeve opening but has not touched; a separate paid touch or ordinary release remains.'),
         *_geometry(OPENING_VISITOR, OPENING_KEEPER, 'visitor')], (INSIDE_VISITOR, INSIDE_KEEPER))
    touch = _charged(actions, 'touch_opening',
        'Choose the actual low opening for one light touch to keeper sleeve, then close practice.',
        'visitor', 'visitor_touch',
        _closed_context('Visitor paid one exertion and touched keeper sleeve through the low opening left by the high turn against the inside step. No injury. Practice closed; all accepted expenditures remain spent.'),
        (OPENING_VISITOR, OPENING_KEEPER))
    actions['release_opening'] = _event('release_opening', 'Leave the actual low opening unused and step away. Cost: 0.', 'visitor', 'no_touch',
        requirements=_at_geometry(OPENING_VISITOR, OPENING_KEEPER),
        changes=_closed_context('Visitor left the low opening unused and stepped away. Practice closed with no touch; accepted expenditures remain spent.'))
    states = {
        'arrival': ['offer', 'decline'], 'consent': ['accept', 'keeper_decline'],
        'outside': [*advance, 'visitor_stop'], 'high_response': ['give_ground_high', *meet, 'keeper_stop'],
        'contact': ['release_contact', *press, *inside, 'visitor_stop'],
        'extended_response': ['yield_turn', 'keeper_stop'],
        'counter_opening': [*counter, 'back_out', 'keeper_stop'],
        'inside_response': ['give_ground_inside', *turn, 'keeper_stop'],
        'visitor_opening': [*touch, 'release_opening', 'visitor_stop'],
        'visitor_touch': _terminal('achieved'), 'keeper_touch': _terminal('achieved'),
        'no_touch': _terminal('partly_achieved'), 'withdrawn': _terminal('not_achieved'),
    }
    return {'title': 'Another optional marked studio practice' if rematch else 'A marked studio practice with real response and counterplay',
            'roles': ['visitor', 'keeper'], 'visibility': 'public', 'initial_state': 'arrival',
            'max_steps': 12, 'loops': [],
            'states': {key: {'phase': 'active', 'outcome': 'unresolved', 'actions': value}
                       if isinstance(value, list) else value for key, value in states.items()},
            'actions': actions, 'ending': {'label': 'End only this marked practice and release its geometry; preserve accepted costs and result history.',
                                         'next_state': 'withdrawn', 'changes': _cleanup()}}


def _recovery_spec():
    actions = {}
    for role in ('visitor', 'keeper'):
        aid = role + '_rest'
        actions[aid] = _event(aid, 'Choose an explicit unhurried fictional rest for yourself; restore your practice exertions to 3. This does not rest the other person.',
            role, 'rested', changes=[_patch(EFFORT[role], quantity=3)],
            requirements=[_require(SOURCE, 'phase', 'open'), _require({'$role': role}, 'location', 'studio'),
                _require(EFFORT[role], 'holder', {'$role': role}), _require(EFFORT[role], 'unit', EFFORT_UNIT)])
        aid = role + '_skip_rest'
        actions[aid] = _event(aid, 'Leave without resting or restoring anyone\'s practice exertions. Cost: 0.', role, 'withdrawn')
    return {'title': 'Optional personal rest after marked practice', 'roles': ['visitor', 'keeper'],
            'visibility': 'public', 'initial_state': 'arrival', 'max_steps': 2, 'loops': [],
            'states': {'arrival': {'phase': 'active', 'outcome': 'unresolved', 'actions': list(actions)},
                       'rested': _terminal('achieved'), 'withdrawn': _terminal('not_achieved')},
            'actions': actions,
            'ending': {'label': 'Leave this optional rest without changing either person\'s effort.',
                       'next_state': 'withdrawn', 'changes': _cleanup()}}


def practice_definitions():
    """Root integrates these new immutable IDs; old authored IDs are untouched.

    Product admission owns the one-active-practice/recovery-per-person rule.
    In particular, a recovery may start only after that person's practice ends.
    Its independent entry is bound by the product to the actual initiating
    actor; no chooser is authorized to restore the other person's resource.
    """
    result = []
    for name, title, spec in (
        ('practice', 'An optional marked studio practice', _practice_spec()),
        ('practice_return', 'Return to marked practice with present resources', _practice_spec(rematch=True)),
        ('practice_recover', 'Choose your own fictional rest', _recovery_spec()),
    ):
        result.append({'id': 'synthetic:' + name, 'version': 1, 'kind': 'battle',
            'handler': 'encounter', 'title': title, 'encounter': spec,
            'participants': ['visitor', 'keeper'], 'start_location': 'studio',
            'scene_source_id': SOURCE, 'combat': True,
            **({'recovery': True, 'independent_entry': True} if name == 'practice_recover' else {}),
            **({'rematch': True} if name == 'practice_return' else {})})
    return result


def practice_records():
    """Public authored synthetic material, without a past practice or account."""
    records = [_record('thread', SOURCE, phase='open', question=PRACTICE_TERMS)]
    for role in ('visitor', 'keeper'):
        records.extend([
            _record('item', ITEMS[role], name=('Visitor' if role == 'visitor' else 'Keeper') + ' padded practice stick',
                kind='padded studio practice stick', condition='sound',
                effects='One permitted light sleeve touch; no injury or automatic improvement.',
                costs='The choosing participant pays one practice exertion for each committed exertion in the displayed rule.',
                origin='Authored public studio-practice-source synthetic fixture; no inherited campaign provenance.'),
            _record('loadout', LOADOUTS[role], item=ITEMS[role], holder=role, slot='practice hand', equipped=1),
            _record('resource', EFFORT[role], holder=role, name=('Visitor' if role == 'visitor' else 'Keeper') + ' remaining practice exertions',
                quantity=3, unit=EFFORT_UNIT,
                availability='Available to its holder for optional marked practice. Only that person\'s explicit fictional rest restores it; no money, task credit or computational capacity.')])
    return records
