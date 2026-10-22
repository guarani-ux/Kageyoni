"""A small explicitly synthetic opening; no imported campaign state."""
import json
from copy import deepcopy
from importlib.resources import files
from .protocol import digest

EVIDENCE = [{'note': 'Authored synthetic G1.2 fixture, not predecessor canon or character mastery.'}]

LIFE_SOURCE = 'studio-life-source'
TRAY = 'studio-tray'
PROMISE = 'studio-tray-promise'
KEEPER_CONCERN = 'studio-keeper-concern'
KEEPER_HISTORY = 'studio-keeper-history'
VISITOR_HISTORY = 'studio-visitor-history'
TRAY_SHELF = 'On the keeper shelf; available only by a separately accepted loan.'
TRAY_BORROWED = 'Borrowed by visitor; the agreed voluntary return is still outstanding.'
TRAY_TABLE = 'On the studio window table, still held by visitor under the loan.'
TRAY_TERMS = 'Borrow the one folding tea tray for a quiet tea at the studio, then return that same tray to the keeper; no payment, work or further promise.'
LIFE_EVIDENCE = [{'note': 'Public authored R05a studio-life fixture, source record studio-life-source. New synthetic events only; not recovered canon, prior memories or mastery.'}]


def change(rid, **data):
    return {'op': 'patch', 'id': rid, 'data': data, 'evidence': EVIDENCE}


def action(label, role, next_state, changes=None, speech=None):
    if speech is not None:
        payload = {'text': speech, 'act': 'inform', 'mode': 'spoken',
                   'listener_roles': ['visitor' if role == 'keeper' else 'keeper']}
        kind = 'dialogue'
    else:
        payload, kind = {'changes': changes or []}, 'event'
    return {'label': label, 'actor_role': role, 'kind': kind, 'payload': payload,
            'next_state': next_state, 'resolve_loops': []}


def encounter(title, states, actions):
    for aid, value in actions.items():
        if value['kind'] == 'event' and not value['payload']['changes']:
            value['payload']['changes'] = [{'op': 'create', 'domain': 'historical_account',
                'id': {'$encounter': ':choice:' + aid}, 'data': {'author': {'$role': value['actor_role']},
                'assertion': value['label']}, 'status': 'reported', 'visibility': 'public', 'evidence': EVIDENCE}]
    result = {'title': title, 'roles': ['visitor', 'keeper'], 'visibility': 'public',
              'initial_state': 'arrival', 'max_steps': 20, 'loops': [], 'states': {}, 'actions': actions}
    for key, value in states.items():
        result['states'][key] = {'phase': 'active', 'outcome': 'unresolved', 'actions': value} if isinstance(value, list) else value
    return result


def terminal(outcome):
    return {'phase': 'completed', 'outcome': outcome, 'actions': []}


def _life_patch(rid, **data):
    return {'op': 'patch', 'id': rid, 'data': data, 'evidence': LIFE_EVIDENCE}


def _life_requirements(holder=None, phase=None, availability=None):
    values = [(LIFE_SOURCE, 'phase', 'open'),
              ('visitor', 'location', 'studio'), ('keeper', 'location', 'studio')]
    if holder is not None:
        values += [(TRAY, 'holder', holder), (TRAY, 'quantity', 1), (TRAY, 'unit', 'tray')]
    if phase is not None:
        values.append((PROMISE, 'phase', phase))
    if availability is not None:
        values.append((TRAY, 'availability', availability))
    return [{'record_id': rid, 'field': field, 'equals': value} for rid, field, value in values]


def _life_action(aid, label, actor, next_state, *, speech=None, changes=(), requirements=()):
    """One authored event can record speech and its admitted material effects.

    The receipt, records and heard observations remain native. Quiet choices
    record only their attributed declaration, without fabricating an achievement,
    a feeling, a task or a generic historical-account record.
    """
    listener = 'visitor' if actor == 'keeper' else 'keeper'
    effects = list(deepcopy(changes))
    if speech is not None:
        effects.append({'op': 'create', 'domain': 'dialogue_turn',
            'id': {'$encounter': ':life-turn:' + aid}, 'status': 'reported',
            'visibility': 'public', 'evidence': LIFE_EVIDENCE,
            'data': {'speaker': {'$role': actor}, 'listeners': [{'$role': listener}],
                     'act': aid, 'text': speech, 'mode': 'spoken'}})
        observation = {'id': {'$encounter': ':life-heard:' + aid},
            'observer_id': {'$role': listener}, 'subject_id': {'$role': actor},
            'assertion': speech, 'certainty': 'heard', 'visibility': 'restricted',
            'audience': [{'$role': listener}]}
    else:
        observation = {'id': {'$encounter': ':life-choice:' + aid},
            'observer_id': {'$role': actor}, 'subject_id': {'$role': actor},
            'assertion': label, 'certainty': 'declared_choice', 'visibility': 'restricted',
            'audience': [{'$role': actor}]}
    return {'label': label, 'actor_role': actor, 'kind': 'event',
            'payload': {'changes': effects, 'observations': [observation]},
            'next_state': next_state, 'resolve_loops': [],
            'requirements': list(deepcopy(requirements)) or _life_requirements()}


def _life_encounter(title, states, actions):
    return {'title': title, 'roles': ['visitor', 'keeper'], 'visibility': 'public',
            'initial_state': 'arrival', 'max_steps': 20, 'loops': [],
            'states': {key: {'phase': 'active', 'outcome': 'unresolved', 'actions': value}
                       if isinstance(value, list) else value for key, value in states.items()},
            'actions': actions}


def life_definitions():
    """Optional ordinary company and one material loan, with later native use.

    Asking is not consent. Keeper chooses the loan on a separate bound turn.
    One fixed native resource and a versioned commitment carry its consequence;
    there is no relationship score, automatic debt or offscreen executor.
    """
    available = _life_requirements('keeper', 'ended', TRAY_SHELF)
    held = _life_requirements('visitor', 'active')
    actions = {
        'rest': _life_action('rest', 'Settle into the window seat.', 'visitor', 'resting'),
        'leave': _life_action('leave', 'Leave this conversation with the afternoon still free.', 'visitor', 'leaving'),
        'ask': _life_action('ask', "Ask what has caught the keeper's attention.", 'visitor', 'keeper_reply',
            speech='What have you been looking at today?'),
        'share_sketch': _life_action('share_sketch', 'Show the unfinished window sketch without asking for help.', 'keeper', 'company',
            speech='The shadow of that cup keeps moving. I have drawn it three different ways. You can look, if you like. It is not a job.'),
        'keep_drawing': _life_action('keep_drawing', 'Keep drawing and leave the visitor free to stay or go.', 'keeper', 'resting',
            speech='I would like a little quiet with this line. Tea is there, and the window seat is yours if you want it.'),
        'stay_company': _life_action('stay_company', 'Stay for ordinary company without promising an output.', 'visitor', 'resting',
            speech='I will sit here a while. You need not turn the sketch into an explanation.'),
        'request_tray': _life_action('request_tray', 'Ask to borrow the folding tray. Proposed terms: ' + TRAY_TERMS, 'visitor', 'keeper_loan',
            speech="Could I borrow the folding tray for tea by the window? I'll bring this one back when I'm done.",
            requirements=available),
        'lend_tray': _life_action('lend_tray', 'Lend the one folding tray on the offered terms.', 'keeper', 'loan_held',
            speech="Yes, take it. Bring this one back when you're finished; it fits beside my easel.",
            requirements=available, changes=[
                _life_patch(TRAY, holder='visitor', availability=TRAY_BORROWED),
                _life_patch(PROMISE, value_status='known', statement=TRAY_TERMS,
                            phase='active', change_basis='voluntary'),
                _life_patch(KEEPER_HISTORY, shared_history='I lent the one folding tea tray after the visitor offered its specific return terms. This was not consent to another request.'),
                _life_patch(VISITOR_HISTORY, shared_history="I borrowed the keeper's folding tea tray under the specific return terms I offered. No other favour was exchanged.")]),
        'refuse_tray': _life_action('refuse_tray', 'Keep the tray and decline the request without imposing a debt.', 'keeper', 'declined',
            speech='Not this tray today; I want it beside me while I draw. There is tea without it, and you are welcome to stay.',
            requirements=available, changes=[
                _life_patch(KEEPER_HISTORY, shared_history='I declined the requested tray loan. The visitor owes no return, work or compensation.'),
                _life_patch(VISITOR_HISTORY, shared_history='The keeper declined the tray loan. I did not borrow it or accept a debt.')]),
        'continue_sketch': _life_action('continue_sketch', "Go back to the keeper's own sketch.", 'keeper', 'declined',
            speech="I'd like to stick with this drawing for now. Tea's there if you feel like it."),
    }
    visit = _life_encounter('Ordinary company at the studio window',
        {'arrival': ['rest', 'ask', 'request_tray', 'leave'],
         'keeper_reply': ['share_sketch', 'keep_drawing'],
         'company': ['stay_company', 'request_tray', 'leave'],
         'keeper_loan': ['lend_tray', 'refuse_tray', 'continue_sketch'],
         'declined': ['rest', 'leave'], 'resting': terminal('achieved'),
         'leaving': terminal('not_achieved'), 'loan_held': terminal('achieved')}, actions)

    later = deepcopy(actions)
    later.update({
        'notice_tray': _life_action('notice_tray', 'Ask to pick up the current studio conversation.', 'visitor', 'keeper_recall',
            speech='Good to see you. Shall we pick up where we left off, or would you rather keep drawing?'),
        'remember_loan': _life_action('remember_loan', 'Refer to the actual outstanding tray loan.', 'keeper', 'held_choice',
            speech="You've still got the folding tray. Put it by the window if you like; bring it back when you're finished.",
            requirements=held),
        'no_loan': _life_action('no_loan', 'Offer tea with the tray beside the keeper.', 'keeper', 'company',
            speech='The tray is here with me. We can simply have tea, or I can go on with the sketch.',
            requirements=available),
        'use_tray': _life_action('use_tray', 'Set the borrowed tray with cups at the studio window table.', 'visitor', 'tea_reply',
            requirements=_life_requirements('visitor', 'active', TRAY_BORROWED),
            changes=[_life_patch(TRAY, availability=TRAY_TABLE)]),
        'join_tea': _life_action('join_tea', 'Choose to join the visitor at the actually prepared tray.', 'keeper', 'tea_choice',
            speech='One cup, then I will go back to that stubborn line. Leave me the seat where I can still see the window.',
            requirements=_life_requirements('visitor', 'active', TRAY_TABLE)),
        'return_tray': _life_action('return_tray', 'Return the same tray and end only its accepted promise.', 'visitor', 'returned_reply',
            speech='Here is your folding tray back.', requirements=held,
            changes=[_life_patch(TRAY, holder='keeper', availability=TRAY_SHELF),
                _life_patch(PROMISE, phase='ended', change_basis='voluntary'),
                _life_patch(KEEPER_HISTORY, shared_history='The visitor returned the one borrowed tray, completing its specific promise. Earlier loan and refusal events remain recorded.'),
                _life_patch(VISITOR_HISTORY, shared_history="I returned the same borrowed tray and ended that promise. This says nothing about a different commitment or the keeper's feelings.")]),
        'acknowledge_return': _life_action('acknowledge_return', 'Acknowledge the actual returned tray and restored availability.', 'keeper', 'returned',
            speech='There it is. Thank you. I can put it beside the easel again.',
            requirements=available),
    })
    followup = _life_encounter('Return to the studio and its unfinished matters',
        {'arrival': ['notice_tray', 'use_tray', 'return_tray', 'request_tray', 'rest', 'leave'],
         'keeper_reply': ['share_sketch', 'keep_drawing'],
         'keeper_recall': ['remember_loan', 'no_loan', 'keep_drawing'],
         'held_choice': ['use_tray', 'return_tray', 'rest', 'leave'],
         'keeper_loan': ['lend_tray', 'refuse_tray', 'continue_sketch'],
         'declined': ['rest', 'leave'], 'company': ['stay_company', 'request_tray', 'leave'],
         'tea_reply': ['join_tea', 'keep_drawing'],
         'tea_choice': ['return_tray', 'rest', 'leave'],
         'returned_reply': ['acknowledge_return', 'keep_drawing'],
         'resting': terminal('achieved'), 'leaving': terminal('not_achieved'),
         'loan_held': terminal('achieved'), 'returned': terminal('achieved')}, later)
    return [{'id': 'synthetic:' + name, 'version': 1, 'kind': 'life',
             'handler': 'encounter', 'title': title, 'encounter': spec,
             'participants': ['visitor', 'keeper'], 'start_location': 'studio',
             'scene_source_id': LIFE_SOURCE}
            for name, title, spec in [('visit', 'Company, quiet and an optional tray loan', visit),
                                      ('followup', 'The studio after an earlier choice', followup)]]


def _initialize_life(engine):
    def record(domain, rid, **data):
        return {'op': 'create', 'domain': domain, 'id': rid, 'data': data,
                'status': 'proposed', 'visibility': 'public', 'evidence': LIFE_EVIDENCE}
    engine.apply({'api_version': 3, 'branch': 'main', 'request_id': 'samsara:studio-life-fixture',
        'expected_revision': engine.branch('main')['revision'], 'actor': 'fixture', 'kind': 'scene',
        'narrative': 'Author a separately identified public studio-life fixture with no prior loan or inherited history.',
        'changes': [
            record('thread', LIFE_SOURCE,
                question='Authored synthetic studio visit: ordinary company, a separately consented one-tray loan, actual later use and voluntary return. No canonical memories, friendship score or offscreen progress.', phase='open'),
            record('resource', TRAY, holder='keeper', name='The folding tea tray', quantity=1,
                unit='tray', availability=TRAY_SHELF),
            record('character_aspect', PROMISE, character='visitor', section='interiority',
                kind='commitment', value_status='absent', phase='ended', change_basis='established',
                related_character='keeper'),
            record('character_aspect', KEEPER_CONCERN, character='keeper', section='interiority',
                kind='drive', value_status='known', statement='I want some unhurried time with my unfinished window sketch. Company may be welcome; I can also prefer quiet without giving the visitor a task.',
                phase='active', change_basis='established'),
            record('relationship', KEEPER_HISTORY, subject='keeper', object='visitor', kind='studio acquaintance'),
            record('relationship', VISITOR_HISTORY, subject='visitor', object='keeper', kind='studio acquaintance')
        ]})


def definitions():
    quiet = encounter('An afternoon at the open studio',
        {'arrival': ['rest', 'ask', 'leave'], 'reply': ['suggest', 'leave_space'],
         'choice': ['consider', 'decline'], 'resting': terminal('achieved'),
         'leaving': terminal('not_achieved'), 'open': terminal('partly_achieved')},
        {'rest': action('Sit with the tea and enjoy the room', 'visitor', 'resting'),
         'ask': action('Ask what the keeper is working on', 'visitor', 'reply', speech='What has your attention today?'),
         'leave': action('Leave without taking on work', 'visitor', 'leaving'),
         'suggest': action('Share a question about making useful instructions', 'keeper', 'choice',
             speech='I wonder how to make a short handoff useful without sending someone through every document. I may try a small note. You are welcome to stay, or leave me to it.'),
         'leave_space': action('Respect the quiet and offer no task', 'keeper', 'resting', speech='There is nothing you need to do. The window seat is free.'),
         'consider': action('Continue the conversation without promising an outcome', 'visitor', 'open', speech='I am interested. Show me what you make, when it is ready.'),
         'decline': action('Decline the invitation and keep the afternoon free', 'visitor', 'resting', speech='Not today. I would rather sit for a while.')})
    bout = encounter('A consented three-choice practice bout',
        {'arrival': ['accept', 'refuse'], 'stance': ['guard', 'open_guard'],
         'guarded': ['press_guard', 'circle_guard', 'stop_guard'],
         'open_guard': ['touch', 'circle_open', 'stop_open'],
         'visitor_touch': terminal('achieved'), 'keeper_touch': terminal('not_achieved'),
         'draw': terminal('partly_achieved'), 'withdrawn': terminal('not_achieved')},
        {'accept': action('Accept a nonlethal touch bout', 'visitor', 'stance', speech='One exchange, padded sticks, no injury or mastery award. I can stop at any point.'),
         'refuse': action('Decline and return to ordinary life', 'visitor', 'withdrawn'),
         'guard': action('Keep a closed guard', 'keeper', 'guarded'),
         'open_guard': action('Advance with the guard open', 'keeper', 'open_guard'),
         'press_guard': action('Press into the closed guard: keeper scores a touch', 'visitor', 'keeper_touch', [change('visitor', condition='The keeper touched the visitor sleeve in the synthetic bout; no injury.')]),
         'circle_guard': action('Circle out of range: a draw', 'visitor', 'draw'),
         'stop_guard': action('Call a stop and withdraw', 'visitor', 'withdrawn'),
         'touch': action('Use the opening: visitor scores a touch', 'visitor', 'visitor_touch', [change('keeper', condition='The visitor touched the keeper sleeve in the synthetic bout; no injury.')]),
         'circle_open': action('Stay out of range: a draw', 'visitor', 'draw'),
         'stop_open': action('Call a stop and withdraw', 'visitor', 'withdrawn')})
    travel = encounter('Walk from the studio to the garden',
        {'arrival': ['garden', 'remain'], 'arrived': terminal('achieved'), 'stayed': terminal('not_achieved')},
        {'garden': action('Take the public path to the garden', 'visitor', 'arrived', [change('visitor', location='garden')]),
         'remain': action('Stay at the studio', 'visitor', 'stayed')})
    travel['actions']['garden']['requirements'] = [{'record_id': 'visitor', 'field': 'location', 'equals': 'studio'}, {'record_id': 'garden-path', 'field': 'access', 'equals': 'open'}]
    values = []
    for name, kind, spec, title in [('quiet', 'travel', quiet, 'Visit the open studio'),
        ('bout', 'battle', bout, 'A small nonlethal bout'), ('travel', 'travel', travel, 'Walk to the garden')]:
        values.append({'id': 'synthetic:' + name, 'version': 1, 'kind': kind, 'handler': 'encounter', 'title': title, 'encounter': spec,
                       'participants': ['visitor', 'keeper']})
    for kind in ('study', 'research', 'real_work'):
        values.append({'id': 'synthetic:' + kind, 'version': 1, 'kind': kind, 'handler': 'text_work',
                       'title': {'study': 'Read and retain a fallible interpretation', 'research': 'Answer a bounded question from admitted sources', 'real_work': 'Produce an inspectable local artifact'}[kind],
                       'participants': None})
    for name, kind, mode, title in (
        ('source_study', 'study', 'study', 'Study a source and make a fallible practical attempt'),
        ('source_research', 'research', 'research', 'Investigate a question with exact supports, counters and unknowns'),
        ('source_script', 'real_work', 'script', 'Write an audiovisual script from the current admitted brief'),
    ):
        values.append({'id': 'synthetic:' + name, 'version': 1, 'kind': kind, 'handler': 'text_work',
                       'title': title, 'participants': None, 'source_work': {'version': 1, 'mode': mode}})
    values.append({'id': 'synthetic:media_work', 'version': 1, 'kind': 'real_work', 'handler': 'text_work',
        'title': 'Return a local video component from the current admitted brief',
        'participants': None, 'media_work': {'version': 1, 'profile': 'local_instruction_mp4'}})
    values.extend(life_definitions())
    for value in values:
        value['reference'] = {'id': value['id'], 'version': value['version'], 'digest': digest(value)}
    from .practice_content import practice_definitions
    values.extend(practice_definitions())
    from .travel_content import travel_definitions
    values.extend(travel_definitions())
    for value in values:
        value['reference'] = {'id': value['id'], 'version': value['version'], 'digest': digest({k: v for k, v in value.items() if k != 'reference'})}
    return values


def initialize(engine):
    from kageyoni.application import Application
    from kageyoni.persistence.migrations import install_worker_custody
    install_worker_custody(engine)
    from kageyoni.contests import install_contests
    install_contests(engine)
    app = Application(engine)
    if engine.db.execute("SELECT 1 FROM records WHERE branch='main' LIMIT 1").fetchone():
        raise ValueError('Synthetic initialization requires an empty world.')
    for cid, label in [('visitor', 'The Visitor'), ('keeper', 'The Studio Keeper')]:
        app.genesis.introduce('main', 'samsara:introduce:' + cid, engine.branch('main')['revision'],
            {'character_id': cid, 'label': label, 'existence': 'established', 'entity_kind': 'person', 'visibility': 'public'})
    def record(domain, rid, **data):
        return {'op': 'create', 'domain': domain, 'id': rid, 'data': data,
                'status': 'proposed', 'visibility': 'public', 'evidence': EVIDENCE}
    opening = [
            record('location', 'studio', name='The Open Studio', kind='room', geography='Tea, abundant food, an unfinished sketch, and a sunny window seat. Nobody must earn their place here.'),
            record('location', 'garden', name='The Garden', kind='region', geography='A public path opens onto shade, conversation, and unhurried space.'),
            record('route', 'garden-path', origin='studio', destination='garden', access='open', duration='a short walk'),
            record('thread','fixture:support-extension-source',question='Public installed synthetic capacity replacement, native support consumer and retained lower-load ending; authored test content.',phase='open'),
            change('visitor', location='studio'), change('keeper', location='studio'),
            {'op': 'create', 'domain': 'thread', 'id': 'synthetic-private-thread', 'data': {'question': 'PRIVATE_FIXTURE_DO_NOT_DISCLOSE', 'phase': 'open'},
             'status': 'proposed', 'visibility': 'gm', 'evidence': EVIDENCE}]
    for item in opening:
        if item['op'] == 'patch':
            item['expected_version'] = engine.get('main', item['id'])['version']
    engine.apply({'api_version': 3, 'branch': 'main', 'request_id': 'samsara:opening', 'expected_revision': engine.branch('main')['revision'],
        'actor': 'fixture', 'kind': 'scene', 'narrative': 'Create a separately identified synthetic opening.', 'changes': opening})
    for item in definitions():
        if item['handler'] == 'encounter':
            app.encounters.define(item['id'], item['version'], item['encounter'], 'samsara:define:' + item['id'])
    # The operational workspace is bound to a stable node. Input records are
    # selected explicitly so subsequent world changes do not invalidate it.
    workspace = app.workspaces.open('main', 'visitor', 'document', 'samsara:workspace', viewer=None, source_ids=[])
    from kageyoni.persistence.unit_of_work import UnitOfWork
    with UnitOfWork(engine.db):
        engine.define_property('fixture:load_capacity', 1, 'Load capacity',
            'Authored synthetic maximum supported load in kilograms.', 'integer', ['person'],
            {'min': 0, 'max': 20, 'resolver': 'replace', 'allow_unknown_replace': True}, 'active', unit='kg')
        engine.add_rule('fixture:support', 1, 'Support threshold', ['fixture:load_capacity'], [], True,
            {'kind': 'threshold', 'property': 'fixture:load_capacity', 'threshold': 12},
            [('fixture:load_capacity', 1, 'reads')])
        engine.apply({'api_version': 3, 'branch': 'main', 'request_id': 'samsara:property-fixture',
            'expected_revision': engine.branch('main')['revision'], 'actor': 'fixture', 'kind': 'scene',
            'narrative': 'Install the public synthetic capacity fixture, without mastery claims.',
            'changes': [record('clock', 'fixture:clock', name='Synthetic studio clock', tick=0, unit='scene', location='studio')],
            'properties': [{'entity_id': eid, 'property_id': 'fixture:load_capacity', 'definition_version': 1,
                'state': 'known', 'value': 10, 'unit': 'kg', 'context': {}, 'epistemic_status': 'synthetic',
                'visibility': 'public'} for eid in ('visitor', 'keeper')]})
    from .causality import install_fixture
    with UnitOfWork(engine.db):install_fixture(engine)
    with UnitOfWork(engine.db):_initialize_life(engine)
    from .practice_content import practice_records
    engine.apply({'api_version':3,'branch':'main','request_id':'samsara:practice-fixture','expected_revision':engine.branch('main')['revision'],'actor':'fixture','kind':'scene','narrative':'Install an optional explicitly synthetic marked practice, without mastery or relationship rewards.','changes':practice_records()})
    from .travel_content import travel_records
    engine.apply({'api_version':3,'branch':'main','request_id':'samsara:travel-fixture','expected_revision':engine.branch('main')['revision'],'actor':'fixture','kind':'scene','narrative':'Install explicitly synthetic paths and an unknown discovery seed; no prior journey.','changes':travel_records()})
    return workspace['workspace_id']


def work_template():
    return json.loads(files('samsara').joinpath('data/work-record.json').read_text())
