"""Additive, explicitly synthetic walking, observation and later local use.

Native route/location/knowledge records and accepted encounter events own the
facts. Product wiring separately proves discovery provenance and current
disclosure. Reading public geography is not a personal discovery.
"""
from copy import deepcopy

SOURCE = 'garden-walk-source'
MARKER = 'garden-marker'
CONDITIONS = 'garden-path-conditions'
BENCH = 'garden-shelter'
LOCAL_PATH = 'garden-shelter-path'
KNOWLEDGE = 'visitor-garden-discovery'
CONDITION_TOKEN = 'synthetic:dry-garden-path@1'
KNOWLEDGE_ASSERTION = 'The sheltered bench is reached by the short side path from the garden.'
KNOWLEDGE_BASIS = MARKER

RULES = (
    'Authored synthetic walking rule, not an imported atlas or old journey. '
    'The existing studio-to-garden garden-path is one physical path that may be crossed in either direction, '
    'always reading its actual studio origin, garden destination and current access. '
    'Open permits a crossing; blocked and unknown do not. Conditional permits a crossing only for '
    'the exact synthetic:dry-garden-path@1 token while garden-path-conditions is actually dry at garden. '
    'No text condition is executed. Local paths likewise need their actual current endpoints and access. '
    'Arrival, looking around, rest and refresh do not read a marker or create personal discovery. '
    'A deliberate observation may be remembered and used on a later journey, but it never opens a blocked path. '
    'A return follows the current physical path without requiring a remembered marker. '
    'Walking has unmeasured fictional duration and zero clock, effort, food or money charge in this expression. '
    'There is no automatic weather change, recovery, growth or bonus. Stopping leaves the traveler at the last accepted place; it is not return travel.'
)
EVIDENCE = [{'note': 'New authored R05c synthetic garden-walk-source content. No canonical coordinate, recovered journey, prior discovery or inherited history.'}]
TRAVELER = {'$role': 'traveler'}


def _create(domain, identity, **data):
    return {'op': 'create', 'domain': domain, 'id': deepcopy(identity), 'data': data,
            'status': 'proposed', 'visibility': 'public', 'evidence': deepcopy(EVIDENCE)}


def _patch(identity, **data):
    return {'op': 'patch', 'id': deepcopy(identity), 'data': data, 'evidence': deepcopy(EVIDENCE)}


def _require(identity, field, value):
    return {'record_id': deepcopy(identity), 'field': field, 'equals': deepcopy(value)}


def _place(place):
    values = [_require(TRAVELER, 'location', place),
              _require(place, 'kind', 'region' if place == 'garden' else 'room')]
    if place == BENCH:
        values.append(_require(BENCH, 'parent', 'garden'))
    return values


def _event(label, target, changes, requirements):
    return {'label': label, 'actor_role': 'traveler', 'kind': 'event',
            'payload': {'changes': deepcopy(changes)}, 'next_state': target,
            'resolve_loops': [], 'requirements': deepcopy(requirements)}


def _add(actions, scopes, identity, label, target, changes, requirements, scope):
    actions[identity] = _event(label, target, changes, requirements)
    scopes[identity] = sorted(set(['visitor', *scope]))


def _choice(actions, scopes, identity, label, target, place=None, assertion=None, extra_requirements=(), extra_scope=()):
    # Every finite action has a unique per-episode record. A chosen pause or
    # inquiry records that choice, not a discovery, answer, healing or reward.
    changes = [_create('historical_account', {'$encounter': 'travel-choice-' + identity},
        author=TRAVELER, assertion=assertion or label,
        interpretation='A declared present choice only; no new factual answer, discovery, resource recovery or achievement is inferred.')]
    _add(actions, scopes, identity, label, target, changes,
         [*(_place(place) if place else []), *extra_requirements],
         [*([place] if place else []), *extra_scope])


def _main_crossings(actions, scopes, *, outward, target, source=False):
    origin, destination = ('studio', 'garden') if outward else ('garden', 'studio')
    stem = 'walk' if outward else 'return'
    common = [*_place(origin), _require(destination, 'kind', 'region' if destination == 'garden' else 'room'),
              _require('garden-path', 'origin', 'studio'), _require('garden-path', 'destination', 'garden')]
    scope = [origin, destination, 'garden-path']
    if source:
        common.append(_require(SOURCE, 'phase', 'open'))
        scope.append(SOURCE)
    for access in ('open', 'conditional'):
        requirements = [*common, _require('garden-path', 'access', access)]
        current_scope = list(scope)
        if access == 'conditional':
            requirements.extend([_require('garden-path', 'conditions', CONDITION_TOKEN),
                _require(CONDITIONS, 'location', 'garden'), _require(CONDITIONS, 'feature', 'dry')])
            current_scope.append(CONDITIONS)
        label = ('Walk to the garden' if outward else 'Walk the same physical path back to the studio')
        label += ' while it is open.' if access == 'open' else ' under the exact current dry-path condition.'
        label += ' Unmeasured fictional walking time; no clock or effort charge.'
        _add(actions, scopes, stem + '_' + access, label, target,
             [_patch(TRAVELER, location=destination)], requirements, current_scope)


def _known_requirements():
    return [_require(KNOWLEDGE, 'holder', TRAVELER), _require(KNOWLEDGE, 'attitude', 'knows'),
            _require(KNOWLEDGE, 'subject', BENCH), _require(KNOWLEDGE, 'assertion', KNOWLEDGE_ASSERTION),
            _require(KNOWLEDGE, 'basis', KNOWLEDGE_BASIS), _require(MARKER, 'phase', 'answered')]


def _local_crossing(actions, scopes, *, outward, target):
    origin, destination = ('garden', BENCH) if outward else (BENCH, 'garden')
    requirements = [*_place(origin), _require(destination, 'kind', 'room' if destination == BENCH else 'region'),
        _require(BENCH, 'parent', 'garden'), _require(LOCAL_PATH, 'origin', 'garden'),
        _require(LOCAL_PATH, 'destination', BENCH), _require(LOCAL_PATH, 'access', 'open')]
    scope = [origin, destination, LOCAL_PATH]
    if outward:
        requirements.extend([_require(SOURCE, 'phase', 'open'), *_known_requirements()])
        scope.extend([SOURCE, MARKER, KNOWLEDGE])
    label = 'Follow the now-known garden side path to its learned place.' if outward else 'Walk this same local path back to the garden.'
    label += ' Unmeasured fictional walking time; no clock or effort charge.'
    _add(actions, scopes, 'follow_known_path' if outward else 'back_to_garden', label, target,
         [_patch(TRAVELER, location=destination)], requirements, scope)


def _linger(actions, scopes, prefix, place, target, *, route=None):
    rest, inquire = 'rest_' + prefix, 'inquire_' + prefix
    _choice(actions, scopes, rest, 'Rest here by choice without reading a marker or recovering resources.', target, place,
        assertion='I chose to rest at this actual place. I did not acquire a specified new fact or restore any resource.')
    requirements, scope = [], []
    if route:
        start, end = ('studio', 'garden') if route == 'garden-path' else ('garden', BENCH)
        requirements = [_require(route, 'origin', start), _require(route, 'destination', end)]
        scope = [route, start, end]
    _choice(actions, scopes, inquire, 'Inquire about the current local path without assuming an answer or permission to cross.', target, place,
        assertion='I chose to inquire about the local path and remained here. No answer, permission or discovery has been established by that choice.',
        extra_requirements=requirements, extra_scope=scope)
    return [rest, inquire]


def _finish_spec(title, states, actions):
    return {'title': title, 'roles': ['traveler'], 'visibility': 'public', 'initial_state': 'initial',
        'max_steps': 16, 'loops': [],
        'states': {key: {'phase': 'active', 'outcome': 'unresolved', 'actions': value}
                   if isinstance(value, list) else value for key, value in states.items()},
        'actions': actions, 'ending': {'label': 'Stop this journey at the last accepted place, retaining actual history and knowledge; this is not a return.',
                                     'next_state': 'stopped', 'changes': []}}


def _terminals():
    return {'home': {'phase': 'completed', 'outcome': 'achieved', 'actions': []},
            'stayed': {'phase': 'completed', 'outcome': 'partly_achieved', 'actions': []},
            'stopped': {'phase': 'completed', 'outcome': 'not_achieved', 'actions': []}}


def _stop(actions, scopes):
    _choice(actions, scopes, 'stop', 'Stop the journey here; remain at the last accepted place.', 'stopped',
        assertion='I chose to stop this journey at my last accepted place. This choice did not return or teleport me.')
    scopes['__end__'] = ['visitor']


def _garden_journey():
    actions, scopes = {}, {}
    _main_crossings(actions, scopes, outward=True, target='garden', source=True)
    _main_crossings(actions, scopes, outward=False, target='home')
    _choice(actions, scopes, 'remain', 'Remain at the studio without starting a journey.', 'stayed', 'studio')
    initial_linger = _linger(actions, scopes, 'initial', 'studio', 'initial_lingered', route='garden-path')
    garden_linger = _linger(actions, scopes, 'garden', 'garden', 'garden_lingered', route='garden-path')
    observed_linger = _linger(actions, scopes, 'observed', 'garden', 'observed_lingered', route='garden-path')
    knowledge = _patch(KNOWLEDGE, holder=TRAVELER, subject=BENCH, assertion=KNOWLEDGE_ASSERTION,
                       attitude='knows', basis=KNOWLEDGE_BASIS)
    knowledge.update(visibility='restricted', audience=['visitor'], status='reported')
    _add(actions, scopes, 'observe_marker', 'Deliberately read the garden marker and retain what it actually indicates.',
        'observed', [knowledge], [*_place('garden'), _require(SOURCE, 'phase', 'open'),
            _require(MARKER, 'phase', 'answered'), _require(MARKER, 'answer', KNOWLEDGE_ASSERTION),
            _require(KNOWLEDGE, 'holder', TRAVELER), _require(BENCH, 'parent', 'garden'),
            _require(BENCH, 'kind', 'room'), _require(LOCAL_PATH, 'origin', 'garden'),
            _require(LOCAL_PATH, 'destination', BENCH)],
        [SOURCE, 'garden', MARKER, KNOWLEDGE, BENCH, LOCAL_PATH])
    _stop(actions, scopes)
    outward = ['walk_open', 'walk_conditional']
    returns = ['return_open', 'return_conditional', 'stop']
    states = {'initial': [*outward, *initial_linger, 'remain', 'stop'],
        'initial_lingered': [*outward, 'remain', 'stop'],
        'garden': ['observe_marker', *returns, *garden_linger],
        'garden_lingered': ['observe_marker', *returns],
        'observed': [*returns, *observed_linger], 'observed_lingered': returns,
        **_terminals()}
    return _finish_spec('An optional garden journey and return', states, actions), scopes


def _learned_journey():
    actions, scopes = {}, {}
    _main_crossings(actions, scopes, outward=True, target='garden', source=True)
    _main_crossings(actions, scopes, outward=False, target='home')
    _local_crossing(actions, scopes, outward=True, target='local')
    _local_crossing(actions, scopes, outward=False, target='garden_returning')
    _choice(actions, scopes, 'remain', 'Remain at the studio without taking another journey.', 'stayed', 'studio')
    initial_linger = _linger(actions, scopes, 'initial', 'studio', 'initial_lingered', route='garden-path')
    garden_linger = _linger(actions, scopes, 'garden', 'garden', 'garden_lingered', route='garden-path')
    local_linger = _linger(actions, scopes, 'local', BENCH, 'local_lingered', route=LOCAL_PATH)
    return_linger = _linger(actions, scopes, 'returning', 'garden', 'garden_returning_lingered', route='garden-path')
    _stop(actions, scopes)
    outward, returns = ['walk_open', 'walk_conditional'], ['return_open', 'return_conditional', 'stop']
    states = {'initial': [*outward, *initial_linger, 'remain', 'stop'],
        'initial_lingered': [*outward, 'remain', 'stop'],
        'garden': ['follow_known_path', *returns, *garden_linger],
        'garden_lingered': ['follow_known_path', *returns],
        'local': ['back_to_garden', *local_linger, 'stop'],
        'local_lingered': ['back_to_garden', 'stop'],
        'garden_returning': [*returns, *return_linger], 'garden_returning_lingered': returns,
        **_terminals()}
    return _finish_spec('A later journey using an actual remembered observation', states, actions), scopes


def _return_journey(local=False):
    actions, scopes = {}, {}
    _main_crossings(actions, scopes, outward=False, target='home')
    _stop(actions, scopes)
    returns = ['return_open', 'return_conditional', 'stop']
    if local:
        _local_crossing(actions, scopes, outward=False, target='garden')
        here = _linger(actions, scopes, 'initial', BENCH, 'initial_lingered', route=LOCAL_PATH)
        garden = _linger(actions, scopes, 'garden', 'garden', 'garden_lingered', route='garden-path')
        states = {'initial': ['back_to_garden', *here, 'stop'], 'initial_lingered': ['back_to_garden', 'stop'],
                  'garden': [*returns, *garden], 'garden_lingered': returns, **_terminals()}
    else:
        here = _linger(actions, scopes, 'initial', 'garden', 'initial_lingered', route='garden-path')
        states = {'initial': [*returns, *here], 'initial_lingered': returns, **_terminals()}
    return _finish_spec('Return from the current place by its actual path', states, actions), scopes


def _quiet(local=False):
    actions, scopes = {}, {}
    place = BENCH if local else 'garden'
    _choice(actions, scopes, 'rest', 'Rest here without taking on work or claiming a discovery.', 'stayed', place,
            assertion='I chose to rest at this actual place. No new knowledge, recovery or accomplishment is implied.')
    _choice(actions, scopes, 'look_around', 'Look around this immediate place without reading a marker or claiming a new fact.', 'stayed', place,
            assertion='I chose to look around at this actual place. I did not claim any specified new discovery.')
    _stop(actions, scopes)
    return _finish_spec('Ordinary leisure at the current place', {'initial': ['rest', 'look_around', 'stop'], **_terminals()}, actions), scopes


def travel_definitions():
    """Trusted additive wrappers; root computes their public references.

    Action scopes also list knowledge.subject/basis plaintext references. They
    are explicit product authorization inputs, not a second native state store.
    """
    values = []
    table = [
        ('garden_journey', 'walk', 'studio', 'Choose an optional garden journey', _garden_journey()),
        ('garden_return', 'return', 'garden', 'Return by the current path', _return_journey()),
        ('explore_again', 'learned', 'studio', 'Revisit a deliberately learned place', _learned_journey()),
        ('local_return', 'local_return', BENCH, 'Return from the current local place', _return_journey(True)),
        ('garden_quiet', 'quiet', 'garden', 'Spend ordinary time here', _quiet()),
        ('local_quiet', 'quiet', BENCH, 'Spend ordinary time at this place', _quiet(True)),
    ]
    for name, kind, start, title, (spec, scopes) in table:
        value = {'id': 'synthetic:' + name, 'version': 1, 'kind': 'travel', 'handler': 'encounter',
            'title': title, 'encounter': spec, 'participants': ['visitor'], 'role_bindings': {'traveler': 'visitor'},
            'start_location': start, 'exploration': True, 'exploration_kind': kind, 'action_scope_ids': scopes}
        if name in ('garden_journey', 'explore_again'):
            value['scene_source_id'] = SOURCE
        if name == 'garden_journey':
            value['observation_action_id'] = 'observe_marker'
        if name == 'explore_again':
            value.update(requires_discovery=True, knowledge_actions=['follow_known_path'])
        values.append(value)
    return values


def travel_records():
    """Real synthetic material, with an unknown personal seed, not discovery."""
    records = [
        _create('thread', SOURCE, phase='open', question=RULES),
        _create('thread', MARKER, phase='answered',
            question='A small wayfinding marker stands beside the garden path. Read it deliberately if you want to learn what it indicates.',
            answer=KNOWLEDGE_ASSERTION),
        _create('environment', CONDITIONS, location='garden', feature='dry', kind='terrain',
            rule='This is an explicit current synthetic path fact, not an automatic weather simulation.',
            duration='Until an explicit native change.', ending_condition='Superseded by an explicit native condition change.'),
        _create('location', BENCH, name='The Sheltered Bench', kind='room', parent='garden',
            geography='A roofed garden seat at the end of the short side path. It conveys no ownership, reward or special capability.'),
        _create('route', LOCAL_PATH, origin='garden', destination=BENCH, access='open',
            conditions='One physical local path may be crossed in either direction under current open access.',
            duration='An unmeasured fictional walk, with no automatic clock, effort, food or money charge.'),
        _create('knowledge', KNOWLEDGE, holder='visitor', subject=None, attitude='unknown',
            assertion='I have not deliberately read the garden marker in this authored starting state.', basis=None),
    ]
    records[-1].update(visibility='restricted', audience=['visitor'])
    return records
