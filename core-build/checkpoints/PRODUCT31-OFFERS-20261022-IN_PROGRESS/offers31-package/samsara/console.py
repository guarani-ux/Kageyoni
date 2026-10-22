"""Small terminal command facade; structured and screen clients share services."""
import json
import shlex
from uuid import uuid4
from .protocol import Fault


def describe_situation(value, place=False):
    names = {p['reference']['id']: p['name'] for p in value['people']}
    name = lambda rid: names.get(rid, value['place']['name'] if value['place']['reference'] and rid == value['place']['reference']['id'] else rid)
    lines = ['You are ' + name(value['perspective_id']) + '.']
    if place:
        lines += [value['place']['name'], value['place']['description']]
    if value['people']:
        lines.append('Here: ' + ', '.join(p['name'] for p in value['people']) + '.')
    for person in value['people']:
        if person['condition']:
            lines.append(person['name'] + ': ' + person['condition'])
        for concern in person['concerns']:
            lines.append(person['name'] + ': ' + concern['statement'])
    for relation in value['relationships']:
        if relation['shared_history']:
            lines.append(name(relation['subject_id']) + ' about ' + name(relation['object_id']) + ': ' + relation['shared_history'])
    for promise in value['commitments']:
        lines.append('Still open for ' + name(promise['character_id']) + ': ' + promise['statement'])
    for material in value['materials']:
        lines.append(material['name'] + ' — ' + str(material['quantity']) + ' ' + material['unit']
            + '; with ' + name(material['holder_id']) + '. ' + material['availability'])
    for item in value['equipment']:
        lines.append(item['name'] + ' — with ' + name(item['holder_id']) + ', '
            + ('equipped' if item['equipped'] else 'not equipped') + '; ' + item['condition'])
    for scene in value['practice']:
        lines += [scene['name'] + ' · ' + scene['phase'] + ': ' + scene['context']]
        lines += [name(p['character_id']) + ': ' + p['position'] + '. ' + p['active_effects'] for p in scene['positions']]
    for prior in value['prior_practice']:
        lines.append('Earlier accepted practice: ' + prior['result'])
    for account in value['own_accounts']:
        lines += ['Your retained fallible account (' + account['attitude'] + '): ' + account['assertion'],
            'About that earlier practice: ' + account['prior_result']]
    for route in value.get('routes', []):
        lines.append('Path to ' + route['name'] + ': ' + route['access'] + '. ' + route['condition'])
    for discovery in value.get('discoveries', []):
        lines.append('Your deliberate discovery: ' + discovery['assertion'])
    for cue in value.get('cues', []):
        lines.append(cue['question'])
    if value['recent_turns']:
        lines.append('Earlier exchanges, in order:')
        lines += [name(turn['speaker_id']) + ': ' + turn['text'] for turn in value['recent_turns']]
    if value['more_turns']:
        lines.append('Showing the eight most recent authorized exchanges; open promises are retained above.')
    if value['additional_context']:
        lines.append('This is a bounded selection of the available context.')
    return lines


def show(client, activity_id):
    cp = client.status(activity_id)
    lines = [f"{activity_id}: {cp['state']} / {cp['outcome']}"]
    world = client.view()
    lines += describe_situation(world['situation'])
    input_ref = None
    try:
        packet, input_ref = client.prepared(activity_id)
        if packet['input']['type'] == 'encounter_action':
            observation = packet['input']['issued']['observation']
            lines += [observation['title']]
            if packet['input'].get('situation'):
                lines.append('Your current choices:')
            lines += [f"{x['action_id']}: {x['label']}" for x in observation['next_actions']]
        else:
            lines += [packet['input']['objective'] or 'Open pursuit', packet['input']['acceptance']]
    except Fault:
        current = next((a for a in world['activities'] if a['activity_id'] == activity_id), None)
        names = {p['reference']['id']: p['name'] for p in world['situation']['people']}
        if cp['state'] == 'waiting' and current and current['active_actor'] in names:
            lines.append('Waiting for ' + names[current['active_actor']] + ' to choose.')
        elif cp['state'] == 'waiting':
            lines.append('No choice is currently available to this identity. Use view for the current situation.')
        elif cp['state'] == 'paused':
            lines.append('Paused. Resume to choose again, or cancel to stop.')
    for index, ref in enumerate(cp['result_refs']):
        label = 'Your prepared input' if ref == input_ref else 'Accepted result'
        lines.append(f'{label} {index}: read {activity_id} {index}')
    return '\n'.join(lines)


def readable_artifact(blob):
    """Ordinary reading shows the encounter; Client.read retains exact bytes."""
    raw = blob.decode('utf-8')
    try:
        value = json.loads(raw)
    except ValueError:
        return raw
    if not isinstance(value, dict):
        return raw
    if value.get('kind') == 'accepted_encounter':
        lines = [value['description'], 'Recorded result.']
        for change in value['changes']:
            after, before = change['after'], change['before']
            if after is None:
                continue
            name = after['data'].get('name') or change['record_id']
            prior = before['data'] if before else {}
            for key, item in after['data'].items():
                if prior.get(key) != item:
                    lines.append(str(name) + ' · ' + key.replace('_', ' ') + ': ' + str(item))
        return '\n'.join(lines)
    if value.get('kind') == 'practice_account_record':
        account = value['account']
        return ('Your retained fallible account (' + account['attitude'] + '): ' + account['assertion']
            + '\nAbout that earlier practice: ' + account['prior_result']) if account else 'No interpretation has been added.'
    packet = value.get('input')
    if isinstance(packet, dict) and packet.get('type') == 'encounter_action':
        lines = ['Prepared input for your current choice. This is not an accepted result.']
        if packet.get('situation'):
            lines += describe_situation(packet['situation'], place=True)
        observation = packet['issued']['observation']
        lines += [observation['title']]
        lines += [a['action_id'] + ': ' + a['label'] for a in observation['next_actions']]
        return '\n'.join(lines)
    return raw


def execute(client, command, actor='visitor'):
    parts = shlex.split(command)
    if not parts:
        return ''
    name = parts[0].lstrip('/')
    if name in ('help', '?'):
        return ('view | start quiet|visit|followup|bout|practice|practice_return|practice_recover|travel|garden_journey|garden_return|explore_again|local_return|garden_quiet|local_quiet ID | start real_work|study|research ID "purpose" | '
                'show ID | act ID ACTION | read ID INDEX | index ID | job ID | read-job ID | pause ID | resume ID | cancel ID | '
                'return ID "text" | sources ASSIGNMENT | read-source ASSIGNMENT INDEX | '
                'start research|study|real_work ID "purpose" from ASSIGNMENT | '
                'start source_study|source_research|source_script ID "purpose" from ASSIGNMENT | '
                'source-input ID | return-source ID AUTHORED_FILE PROPOSAL_FILE | '
                'prop [ENTITY] | select ENTITY | boost [ENTITY] | apply CHANGE DIGEST | withdraw CHANGE DIGEST | '
                'lift LOAD [ENTITY] | lower LOAD | support LOAD | tick N | '
                'signal ROOT | world ROOT | step ROOT | retry-world ROOT | '
                'extensions VERSION | prepare-extension VERSION [POLICY] | extension ACTION VERSION DIGEST | '
                'account PRACTICE pressure|release|uncertain|unchanged | quit. No work is compulsory.')
    if name == 'account' and len(parts) == 3:
        result = client.practice_account(parts[1], parts[2])
        return readable_artifact(client.read(result['account_ref']))
    if name=='extensions' and len(parts)==2:
        return json.dumps(client.extension_catalog(int(parts[1])),indent=2)
    if name=='prepare-extension' and len(parts) in (2,3):
        return json.dumps(client.prepare_extension(int(parts[1]),parts[2] if len(parts)==3 else 'cancel_and_reconcile'),indent=2)
    if name=='extension' and len(parts)==4:
        catalog=client.extension_catalog(int(parts[2]))
        return json.dumps(client.extension({'definition':catalog['definition'],'candidate_digest':parts[3]},parts[1]),indent=2)
    if name == 'prop' and len(parts) in (1,2):
        return json.dumps(client.property(parts[1] if len(parts)==2 else actor),indent=2)
    if name == 'select' and len(parts)==2:
        return json.dumps(client.select(ids=[parts[1]]),indent=2)
    if name == 'boost' and len(parts) in (1,2):
        change=client.prepare_boost(parts[1] if len(parts)==2 else actor)
        return json.dumps(change,indent=2)+'\n'+client.read(change['visible_diff_ref']).decode()
    if name in ('apply','withdraw') and len(parts)==3:
        return json.dumps(client.change({'change_id':parts[1],'digest':parts[2]},name),indent=2)
    if name == 'lift' and len(parts) in (2,3):
        value=client.support(parts[1],parts[2] if len(parts)==3 else actor)
        return json.dumps(value,indent=2)+'\n'+client.read(value['trace_ref']).decode()
    if name == 'support' and len(parts)==2:
        return json.dumps(client.support_status(parts[1]),indent=2)
    if name == 'lower' and len(parts)==2:
        return json.dumps(client.checked({'name':'support.release','support_id':parts[1]})['return'],indent=2)
    if name == 'tick' and len(parts)==2:
        return json.dumps(client.advance_clock(int(parts[1])),indent=2)
    if name in ('signal','world','step','retry-world') and len(parts)==2:
        action={'signal':'signal','world':'status','step':'step','retry-world':'resume'}[name]
        return json.dumps(client.causal(parts[1],action),indent=2)
    if name == 'view':
        view = client.view()
        rows = describe_situation(view['situation'], place=True)
        rows += [f"{x['activity_id']}: {x['state']} / {x['outcome']} ({x['title']})" for x in view['activities']]
        names = {p['reference']['id']: p['name'] for p in view['situation']['people']}
        for item in view['activities']:
            if item['state'] == 'waiting' and item['active_actor'] and item['active_actor'] != view['situation']['perspective_id']:
                rows.append(item['activity_id'] + ' is waiting for ' + names.get(item['active_actor'], item['active_actor']) + ' to choose.')
        for choice in view['situation']['choices']:
            rows += [f"{choice['activity_id']} · {a['action_id']}: {a['label']}" for a in choice['actions']]
        if view['cursor']:
            rows.append('More activities are available through workspace.view pagination.')
        return '\n'.join(rows)
    if name == 'start' and len(parts) >= 3:
        kind, aid = parts[1:3]
        if len(parts) >= 5 and parts[-2] == 'from':
            if kind in ('source_study', 'source_research', 'source_script'):
                purpose = ' '.join(parts[3:-2])
                if not purpose:
                    raise Fault('INVALID')
                client.start_source_assignment(parts[-1], aid, kind.removeprefix('source_'), purpose, actor)
                return show(client, aid)
            if kind not in ('real_work', 'study', 'research'):
                raise Fault('INVALID')
            client.start_assignment(parts[-1], aid, actor, kind, ' '.join(parts[3:-2]) or None)
            return show(client, aid)
        sources = client.view()['source_refs'] if kind in ('real_work', 'study', 'research') else []
        purpose = ' '.join(parts[3:]) or None
        client.start(kind, aid, actor, purpose, source_refs=sources)
        return show(client, aid)
    if name == 'show' and len(parts) == 2:
        return show(client, parts[1])
    if name == 'sources' and len(parts) == 2:
        value = client.intake_status(parts[1])
        return json.dumps(value, indent=2, ensure_ascii=False)
    if name == 'read-source' and len(parts) == 3:
        value = client.intake_status(parts[1]); index = int(parts[2])
        if not 0 <= index < len(value['source_refs']):
            raise Fault('UNAVAILABLE')
        return client.read(value['source_refs'][index]).decode('utf-8')
    if name == 'source-input' and len(parts) == 2:
        packet, _ = client.prepared(parts[1])
        if packet['input'].get('source_work', {}).get('version') != 1:
            raise Fault('UNSUPPORTED')
        return json.dumps(packet['input'], ensure_ascii=False, indent=2)
    if name == 'return-source' and len(parts) == 4:
        from .intake import _read_at
        from .protocol import decode
        from pathlib import Path, PurePosixPath
        for filename in parts[2:]:
            if PurePosixPath(filename).name != filename:
                raise Fault('INVALID')
        # Proposal files are data inside this identity's staging directory.
        # Stable regular-file checks prohibit paths, symlinks and partial writes.
        _read_at(client.output_root, parts[2])
        proposal = decode(_read_at(client.output_root, parts[3]))
        if (not isinstance(proposal, dict) or set(proposal) != {'inquiry', 'draft', 'disposition', 'assessment'}
                or not isinstance(proposal['assessment'], dict)
                or set(proposal['assessment']) != {'attribution', 'limit'}):
            raise Fault('INVALID')
        client.return_source_work(parts[1], Path(client.output_root) / parts[2],
            proposal['inquiry'], draft=proposal['draft'], disposition=proposal['disposition'],
            attribution=proposal['assessment']['attribution'], limit=proposal['assessment']['limit'])
        return show(client, parts[1])
    if name == 'act' and len(parts) == 3:
        client.act(parts[1], parts[2]); return show(client, parts[1])
    if name == 'index' and len(parts) == 2:
        client.enqueue(parts[1])
        return 'Source inventory queued. Use job ' + parts[1] + ' to inspect progress; read-job ' + parts[1] + ' retrieves its returned bytes.'
    if name == 'job' and len(parts) == 2:
        value = client.job(parts[1])
        return f"{parts[1]}: {value['state']}. {value['reason']}"
    if name == 'read-job' and len(parts) == 2:
        value = client.job(parts[1])
        if value['output_ref'] is None:
            raise Fault('DEPENDENCY')
        return client.read(value['output_ref']).decode('utf-8')
    if name in ('pause', 'resume', 'cancel') and len(parts) == 2:
        client.checked({'name': 'activity.' + name, 'activity_id': parts[1]})
        return show(client, parts[1])
    if name == 'read' and len(parts) == 3:
        refs = client.status(parts[1])['result_refs']
        index = int(parts[2])
        if not 0 <= index < len(refs):
            raise Fault('UNAVAILABLE')
        return readable_artifact(client.read(refs[index]))
    if name == 'return' and len(parts) >= 3:
        packet, input_ref = client.prepared(parts[1])
        if packet['input']['type'] == 'encounter_action':
            raise Fault('INVALID')
        path = client.output_root / ('component-' + uuid4().hex + '.md')
        path.write_text(' '.join(parts[2:]) + '\n', encoding='utf-8')
        ref = client.submit_file(packet, path)
        client.receive(packet, input_ref, [ref])
        return show(client, parts[1])
    raise Fault('INVALID')
