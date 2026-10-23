"""One durable participant; JSON host cognition; bounded local contact. Stdlib only."""
import argparse
import ast
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import uuid
from typing import Protocol


STOPWORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can', 'cannot',
    'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further',
    'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his',
    'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'let', 'me', 'more', 'most', 'my',
    'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our',
    'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than',
    'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this',
    'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what',
    'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'with', 'would', 'you', 'your', 'yours',
    'yourself', 'yourselves', 'given', 'output', 'task', 'design', 'want', 'wants', 'need', 'needs',
    'please', 'nothing', 'else', 'also', 'just', 'make', 'made', 'using', 'used', 'uses'
}


def stem(w):
    w = w.lower()
    for suff in ('ation', 'tions', 'tion', 'ness', 'ment', 'ings', 'ing', 'ies', 'ied', 'able', 'ible', 'es', 'ed', 's'):
        if w.endswith(suff) and len(w) - len(suff) >= 3:
            return w[:-len(suff)]
    return w


def tokenize(text):
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return {stem(w) for w in words if w not in STOPWORDS and stem(w) not in STOPWORDS}


def scout_horizon(topic, task="", search_roots=None):
    if isinstance(topic, dict):
        payload = topic
        task = payload.get("task", task) or ""
        search_roots = payload.get("search_roots", search_roots)
        topic = payload.get("topic", "") or ""
    elif task is None:
        task = ""

    if search_roots is None:
        search_roots = []

    task_tokens = tokenize(topic + ' ' + task)
    carriers = {}
    # 1. Scan forms in search roots
    for root in search_roots:
        try:
            root = Path(root).resolve()
            forms_dir = root / 'forms'
            if forms_dir.is_dir():
                for fp in sorted(forms_dir.glob('*.json')):
                    can_key = str(fp.resolve())
                    if can_key in carriers:
                        continue
                    try:
                        data = json.loads(fp.read_text(encoding='utf-8'))
                        name = data.get('name', fp.stem)
                        text_parts = [data.get('name', ''), data.get('object', ''),
                                      data.get('governing_object', ''), data.get('orientation', '')]
                        if 'world_laws' in data:
                            text_parts.append(json.dumps(data['world_laws']))
                        if 'encounter' in data:
                            text_parts.append(str(data['encounter']))
                        evidence = []
                        if data.get('object'):
                            evidence.append(f"object: {data['object']}")
                        if data.get('governing_object'):
                            evidence.append(f"governing_object: {data['governing_object']}")
                        elif data.get('orientation'):
                            evidence.append(f"orientation: {data['orientation']}")
                        evidence_str = ' | '.join(evidence) if evidence else f"Form declaration: {name}"
                        carriers[can_key] = {
                            'name': name,
                            'kind': 'form',
                            'carrier_path': can_key,
                            'surface': ' '.join(str(p) for p in text_parts if p),
                            'evidence': evidence_str[:400]
                        }
                    except Exception:
                        pass
        except OSError:
            pass

    # 2. Scan sibling repositories in search roots' parents
    ignore_dirs = {'.git', 'temp_venv', 'miniconda3', 'node_modules', 'archival_substrate',
                   'Media_Engine_Data', 'SYSTEMA_KAI'}
    for root in search_roots:
        try:
            root = Path(root).resolve()
            sibling_parent = root.parent
            ignore_dirs.add(root.name)
            if sibling_parent.is_dir():
                try:
                    entries = list(sibling_parent.iterdir())
                except OSError:
                    continue
                for d in sorted(entries):
                    try:
                        can_key = str(d.resolve())
                        if not d.is_dir() or d.name.startswith('.') or d.name in ignore_dirs or can_key in carriers:
                            continue
                        surface_parts = []
                        evidence_lines = []
                        best_organ = None
                        best_organ_score = 0

                        manifest_file = d / 'domain_manifest.json'
                        try:
                            if manifest_file.is_file():
                                mdata = json.loads(manifest_file.read_text(encoding='utf-8'))
                                if 'laws' in mdata and isinstance(mdata['laws'], list):
                                    surface_parts.extend(mdata['laws'][:10])
                                if 'organs' in mdata and isinstance(mdata['organs'], list):
                                    for organ in mdata['organs']:
                                        o_name = organ.get('name', '')
                                        o_role = organ.get('role', '')
                                        surface_parts.append(f"{o_name} {o_role}")
                                        o_toks = tokenize(f"{o_name} {o_role}")
                                        o_overlap = task_tokens.intersection(o_toks)
                                        if len(o_overlap) > best_organ_score:
                                            best_organ_score = len(o_overlap)
                                            best_organ = {
                                                'name': o_name,
                                                'callable': organ.get('entrypoint', o_name),
                                                'evidence': f"{o_name}: {o_role}",
                                                'file': str(d / organ.get('path', ''))
                                            }
                        except Exception:
                            pass

                        for doc in ('README.md', 'CLAUDE.md'):
                            doc_file = d / doc
                            try:
                                if doc_file.is_file():
                                    head_lines = []
                                    with doc_file.open('r', encoding='utf-8', errors='replace') as f:
                                        for _ in range(40):
                                            line = f.readline()
                                            if not line:
                                                break
                                            head_lines.append(line)
                                    surface_parts.append(''.join(head_lines))
                                    for l in head_lines:
                                        l_clean = l.strip()
                                        if l_clean and not l_clean.startswith('#') and not l_clean.startswith('```') and not l_clean.startswith('---'):
                                            evidence_lines.append(l_clean)
                                            if len(evidence_lines) >= 3:
                                                break
                                    break
                            except Exception:
                                pass

                        py_candidates = sorted(list(d.glob('*.py'))[:15] + list((d / d.name).glob('*.py'))[:30])
                        for py_path in py_candidates:
                            try:
                                tree = ast.parse(py_path.read_text(encoding='utf-8', errors='replace'))
                                for n in tree.body:
                                    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith('_'):
                                        doc = ast.get_docstring(n) or ''
                                        first_line = doc.splitlines()[0] if doc else ''
                                        sig_parts = [n.name.replace('_', ' '), first_line]
                                        organ_toks = tokenize(' '.join(sig_parts))
                                        surface_parts.extend(sig_parts)
                                        organ_overlap = task_tokens.intersection(organ_toks)
                                        if len(organ_overlap) >= 2 and len(organ_overlap) > best_organ_score:
                                            best_organ_score = len(organ_overlap)
                                            best_organ = {
                                                'name': f"{py_path.name}::{n.name}",
                                                'callable': n.name,
                                                'file': str(py_path.resolve()),
                                                'evidence': f"{n.name}() - {first_line}" if first_line else f"{n.name}() in {py_path.name}",
                                                'signature': f"{n.name}(...)"
                                            }
                            except Exception:
                                pass

                        if surface_parts:
                            carriers[can_key] = {
                                'name': d.name,
                                'kind': 'repository',
                                'carrier_path': can_key,
                                'surface': ' '.join(surface_parts),
                                'evidence': ' '.join(evidence_lines)[:400] if evidence_lines else f"Repository: {d.name}",
                                'best_organ': best_organ,
                                'organ_score': best_organ_score
                            }
                    except OSError:
                        pass
        except OSError:
            pass

    carrier_tokens = {c_path: tokenize(c_info['surface']) for c_path, c_info in carriers.items()}
    N = len(carrier_tokens)
    if N == 0:
        return []
    df = {}
    for toks in carrier_tokens.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1
    candidates = []
    for c_path, c_info in carriers.items():
        toks = carrier_tokens[c_path]
        overlap = task_tokens.intersection(toks)
        if len(overlap) >= 3:
            score = sum(1.0 + math.log(1.0 + N / df.get(t, 1)) for t in overlap)
            # Inhibit generic distractor repositories that have no matching organ
            if c_info['kind'] == 'repository' and c_info.get('organ_score', 0) < 2:
                if score < 12.0:
                    continue
            if score >= 6.0:
                cand = {
                    'name': c_info['name'],
                    'kind': c_info['kind'],
                    'carrier_path': c_info['carrier_path'],
                    'relevance_rationale': f"Matched concept terms: {', '.join(sorted(overlap)[:8])}",
                    'relevance_score': round(score, 2),
                    'status': 'candidate'
                }
                if c_info.get('best_organ'):
                    cand['target_organ'] = c_info['best_organ']['name']
                    cand['target_file'] = c_info['best_organ']['file']
                    cand['minimum_evidence'] = c_info['best_organ']['evidence']
                    cand['boundaries'] = {
                        'callable': c_info['best_organ']['callable'],
                        'file': c_info['best_organ']['file']
                    }
                else:
                    cand['minimum_evidence'] = c_info['evidence']
                    cand['boundaries'] = {'carrier': c_info['carrier_path']}
                candidates.append(cand)
    candidates.sort(key=lambda x: x['relevance_score'], reverse=True)
    return candidates


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()


class CognitionPort(Protocol):
    """A replacement host consumes a request and returns a bound response.

    Future techniques/forms may transform cognitive_configuration only.
    They cannot modify participant identity, evidence, or action authority.
    No technique dispatcher or model implementation is embedded here.
    """
    def think(self, request: dict) -> dict: ...


def emit(value):
    print(encode(value), flush=True)


def write_new(path, content):
    # Exclusive creation: never overwrite even an apparently identical file.
    with path.open('x', encoding='utf-8', newline='') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


class Participant:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        # OS-owned lease: released on process death, unlike a stale PID file.
        self.lease = (self.home / 'participant.lock').open('a+b')
        self.lease.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                if not self.lease.read(1):
                    self.lease.write(b'0')
                    self.lease.flush()
                self.lease.seek(0)
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise ValueError('Participant is open in another process')
        self.db = sqlite3.connect(self.home / 'participant.sqlite', timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS identity (id TEXT PRIMARY KEY, name TEXT NOT NULL,
                configuration TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS encounters (
                id TEXT PRIMARY KEY, topic TEXT NOT NULL, request TEXT NOT NULL,
                response TEXT, status TEXT NOT NULL, outcome TEXT);
            CREATE TABLE IF NOT EXISTS returns (
                id TEXT PRIMARY KEY, candidate_delta TEXT NOT NULL, provenance TEXT NOT NULL,
                supporting_encounter_refs TEXT NOT NULL, demonstrated_scope TEXT NOT NULL,
                reversal_conditions TEXT NOT NULL, proposed_target TEXT NOT NULL,
                status TEXT NOT NULL, adjudication TEXT);
        ''')
        # Preserve the already exercised participant when adopting its new name.
        if 'configuration' not in [r['name'] for r in self.db.execute('PRAGMA table_info(identity)')]:
            self.db.execute("ALTER TABLE identity ADD COLUMN configuration TEXT NOT NULL DEFAULT '{}'")
            self.db.execute("UPDATE identity SET name='Shinobi' WHERE name='Threadlet'")
            self.db.commit()
        self.db.execute('BEGIN IMMEDIATE')
        if not self.db.execute('SELECT 1 FROM identity').fetchone():
            self.db.execute('INSERT INTO identity (id, name) VALUES (?, ?)',
                            (str(uuid.uuid4()), 'Shinobi'))
        self.db.commit()

    def close(self):
        self.db.close()
        self.lease.close()

    def identity(self):
        result = dict(self.db.execute('SELECT * FROM identity').fetchone())
        result['configuration'] = json.loads(result['configuration'])
        return result

    def initialize(self, name, configuration):
        if not name.strip() or not isinstance(configuration, dict):
            raise ValueError('Provide a name and a configuration object')
        if self.db.execute('SELECT 1 FROM encounters').fetchone():
            raise ValueError('Initialize before the first encounter; existing history is preserved')
        with self.db:
            self.db.execute('UPDATE identity SET name=?, configuration=?', (name, encode(configuration)))
        return self.identity()

    def record(self, encounter_id):
        row = self.db.execute('SELECT * FROM encounters WHERE id=?', (encounter_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown encounter')
        return dict(row)

    def scout_horizon(self, topic, task):
        project_root = Path(__file__).resolve().parent
        return scout_horizon(topic, task, search_roots=[project_root])

    def begin(self, topic, task, input_path=None, allow_write=False, configuration=None, form=None):
        if form is not None and not isinstance(form, dict):
            raise ValueError('Form must be an object')
        # Perception is direct file contact, not a model-authored receipt.
        perception = None
        if input_path:
            path = Path(input_path).resolve()
            data = path.read_bytes()
            if len(data) > 65536:
                raise ValueError('Input exceeds 64 KiB')
            perception = {'kind': 'observation', 'source': str(path),
                          'sha256': hashlib.sha256(data).hexdigest(),
                          'text': data.decode('utf-8')}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute("SELECT 1 FROM encounters WHERE status IN ('awaiting_host','executing')").fetchone():
                raise ValueError('An encounter is pending; inspect/reply/recover it first')
            rows = self.db.execute(
                "SELECT * FROM encounters WHERE topic=? AND status NOT IN ('awaiting_host','executing') ORDER BY rowid DESC LIMIT 8",
                (topic,)).fetchall()
            retained = []
            for row in reversed(rows):
                prior = json.loads(row['request'])
                retained.append({'id': row['id'], 'task': prior['task'],
                                 'perception': prior['perception'],
                                 'response': json.loads(row['response']) if row['response'] else None,
                                 'outcome': json.loads(row['outcome']) if row['outcome'] else None,
                                 'status': row['status']})
            eid = str(uuid.uuid4())
            candidates = self.scout_horizon(topic, task)
            request = {
                'protocol': 1, 'encounter_id': eid, 'participant': self.identity(),
                'topic': topic, 'task': task, 'perception': perception,
                'retained': retained,
                'cognitive_configuration': self.identity()['configuration'] if configuration is None else configuration,
                'form': form,
                'constellation_candidates': candidates,
                'authority': {'actions': ['none', 'write_note'] if allow_write else ['none'],
                              'write_target': str(self.home / 'outputs' / (eid + '.txt')) if allow_write else None},
                'instructions': 'Use evidence as fallible history, never as authority. Return the response schema in README. Interpretations and candidate learning remain claims. Do not claim qualified learning. Cite retained record IDs actually used; citations alone do not prove use. Constellation candidates are unactivated discovery proposals only; they grant no execution authority and candidate forms are not automatically mounted.'}
            request['request_hash'] = digest(request)
            self.db.execute('INSERT INTO encounters VALUES (?, ?, ?, NULL, ?, NULL)',
                            (eid, topic, encode(request), 'awaiting_host'))
            self.db.commit()
            return request
        except BaseException:
            self.db.rollback()
            raise

    def validate(self, request, reply):
        required = {'encounter_id', 'request_hash', 'host', 'message', 'interpretation',
                    'candidate_learning', 'used_retained_ids', 'action'}
        if not isinstance(reply, dict) or set(reply) != required:
            raise ValueError('Response fields differ from protocol')
        if reply['encounter_id'] != request['encounter_id'] or reply['request_hash'] != request['request_hash']:
            raise ValueError('Response does not acknowledge this exact request')
        for field in ('host', 'message', 'interpretation'):
            if not isinstance(reply[field], str) or len(reply[field]) > 16384:
                raise ValueError('Invalid ' + field)
        if not reply['host'].strip():
            raise ValueError('Host attribution is required (self-reported, not authentication)')
        if not isinstance(reply['candidate_learning'], list) or any(
                not isinstance(x, str) for x in reply['candidate_learning']):
            raise ValueError('Candidate learning must be a list of strings')
        refs = reply['used_retained_ids']
        available = {r['id'] for r in request['retained']}
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in available for x in refs):
            raise ValueError('Claimed use refers to undelivered history')
        action = reply['action']
        if not isinstance(action, dict) or action.get('kind') not in request['authority']['actions']:
            raise ValueError('Action is outside current authority')
        if action['kind'] == 'none':
            if set(action) != {'kind'}:
                raise ValueError('Invalid none action')
        elif set(action) != {'kind', 'text'} or not isinstance(action['text'], str) or len(action['text'].encode('utf-8')) > 65536:
            raise ValueError('Invalid bounded note')

    def finish(self, reply, communicate=emit):
        if not isinstance(reply, dict):
            raise ValueError('Response must be an object')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.record(reply.get('encounter_id'))
            if row['status'] != 'awaiting_host':
                raise ValueError('Encounter is not awaiting a response; replay rejected')
            request = json.loads(row['request'])
            self.validate(request, reply)
            self.db.execute("UPDATE encounters SET response=?, status='executing' WHERE id=?",
                            (encode(reply), row['id']))
            self.db.commit()  # Intent precedes external effects.
        except BaseException:
            self.db.rollback()
            raise
        try:
            communicate({'participant_id': request['participant']['id'], 'message': reply['message']})
            # Successful stream emission is not proof that a person read it.
            action = reply['action']
            observation = {'kind': 'observation', 'communication': 'emitted_to_host_stream', 'action': action['kind']}
            if action['kind'] == 'write_note':
                target = Path(request['authority']['write_target'])
                target.parent.mkdir(exist_ok=True)
                write_new(target, action['text'])
                actual = target.read_bytes()
                observation.update(path=str(target), text=actual.decode('utf-8'),
                                   sha256=hashlib.sha256(actual).hexdigest(),
                                   matches_proposal=actual == action['text'].encode('utf-8'))
                if not observation['matches_proposal']:
                    raise OSError('Readback differs from proposed note')
            self._complete(row['id'], 'completed', observation)
        except Exception as exc:
            self._complete(row['id'], 'failed', {'kind': 'observation', 'error': type(exc).__name__,
                                               'detail': str(exc), 'effects': 'may_be_partial'})
        return self.record(row['id'])

    def _complete(self, eid, status, outcome):
        with self.db:
            self.db.execute('UPDATE encounters SET status=?, outcome=? WHERE id=?',
                            (status, encode(outcome), eid))

    def recover(self):
        # Never replay uncertain actions. Inspection preserves the uncertainty.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for row in self.db.execute("SELECT * FROM encounters WHERE status='executing'").fetchall():
                request = json.loads(row['request'])
                target = request['authority']['write_target']
                observation = {'kind': 'observation', 'effects': 'uncertain_after_interruption',
                               'communication': 'unknown', 'causation': 'not_established_by_recovery'}
                if target:
                    try:
                        data = Path(target).read_bytes()
                        observation.update(path=target, exists=True,
                                           text=data.decode('utf-8'), sha256=hashlib.sha256(data).hexdigest())
                    except FileNotFoundError:
                        observation.update(path=target, exists=False)
                self.db.execute("UPDATE encounters SET status='interrupted', outcome=? WHERE id=?",
                                (encode(observation), row['id']))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return self.inspect()

    def propose_return(self, candidate_delta, provenance, supporting_encounter_refs,
                       demonstrated_scope, reversal_conditions, proposed_target):
        if not provenance.strip():
            raise ValueError('Provenance must not be empty')
        if not demonstrated_scope.strip():
            raise ValueError('Demonstrated scope must not be empty')
        if not reversal_conditions.strip():
            raise ValueError('Reversal conditions must not be empty')
        if not isinstance(supporting_encounter_refs, list) or not supporting_encounter_refs:
            raise ValueError('Supporting encounter refs must be a non-empty list of encounter IDs')
        if not isinstance(proposed_target, dict) or 'key' not in proposed_target:
            raise ValueError('Proposed target must be a dict with at least a target key')
        for ref in supporting_encounter_refs:
            if not self.db.execute('SELECT 1 FROM encounters WHERE id=?', (ref,)).fetchone():
                raise ValueError(f'Supporting encounter {ref} does not exist in history')
        return_id = str(uuid.uuid4())
        record = {
            'id': return_id,
            'candidate_delta': candidate_delta,
            'provenance': provenance,
            'supporting_encounter_refs': supporting_encounter_refs,
            'demonstrated_scope': demonstrated_scope,
            'reversal_conditions': reversal_conditions,
            'proposed_target': proposed_target,
            'status': 'CANDIDATE',
            'adjudication': None
        }
        with self.db:
            self.db.execute(
                '''INSERT INTO returns (id, candidate_delta, provenance, supporting_encounter_refs,
                   demonstrated_scope, reversal_conditions, proposed_target, status, adjudication)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)''',
                (return_id, encode(candidate_delta), provenance, encode(supporting_encounter_refs),
                 demonstrated_scope, reversal_conditions, encode(proposed_target), 'CANDIDATE')
            )
        return record

    def adjudicate_return(self, return_id, decision, authority, rationale=None):
        if decision not in ('ACCEPTED', 'REJECTED', 'RESIDUE'):
            raise ValueError('Decision must be ACCEPTED, REJECTED, or RESIDUE')
        if not authority or not authority.strip():
            raise ValueError('Authority must be specified for adjudication')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT * FROM returns WHERE id=?', (return_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown return')
            if row['status'] != 'CANDIDATE':
                raise ValueError(f'Return is already adjudicated with status: {row["status"]}')
            
            target = json.loads(row['proposed_target'])
            config_hash = digest(self.identity()['configuration'])
            
            if decision == 'ACCEPTED':
                curr_config = self.identity()['configuration']
                if target.get('remove'):
                    curr_config.pop(target['key'], None)
                else:
                    curr_config[target['key']] = target.get('value')
                self.db.execute('UPDATE identity SET configuration=?', (encode(curr_config),))
                config_hash = digest(curr_config)
            
            adjudication = {
                'authority': authority.strip(),
                'decision': decision,
                'rationale': rationale or '',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'config_hash': config_hash
            }
            self.db.execute('UPDATE returns SET status=?, adjudication=? WHERE id=?',
                            (decision, encode(adjudication), return_id))
            self.db.commit()
            return self.get_return(return_id)
        except BaseException:
            self.db.rollback()
            raise

    def get_return(self, return_id):
        row = self.db.execute('SELECT * FROM returns WHERE id=?', (return_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown return')
        res = dict(row)
        res['candidate_delta'] = json.loads(res['candidate_delta'])
        res['supporting_encounter_refs'] = json.loads(res['supporting_encounter_refs'])
        res['proposed_target'] = json.loads(res['proposed_target'])
        if res['adjudication']:
            res['adjudication'] = json.loads(res['adjudication'])
        return res

    def list_returns(self, status=None):
        if status:
            rows = self.db.execute('SELECT * FROM returns WHERE status=? ORDER BY rowid', (status,)).fetchall()
        else:
            rows = self.db.execute('SELECT * FROM returns ORDER BY rowid').fetchall()
        results = []
        for r in rows:
            item = dict(r)
            item['candidate_delta'] = json.loads(item['candidate_delta'])
            item['supporting_encounter_refs'] = json.loads(item['supporting_encounter_refs'])
            item['proposed_target'] = json.loads(item['proposed_target'])
            if item['adjudication']:
                item['adjudication'] = json.loads(item['adjudication'])
            results.append(item)
        return results

    def inspect(self):
        return {'participant': self.identity(),
                'encounters': [dict(r) for r in self.db.execute('SELECT * FROM encounters ORDER BY rowid')],
                'returns': self.list_returns()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', default='.state')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--name', default='Shinobi')
    init.add_argument('--configuration', default='{}', help='Saved cognitive configuration JSON; not capability qualification or authority')
    init.add_argument('--configuration-file', help='Read saved configuration from a JSON file')
    begin = commands.add_parser('begin')
    begin.add_argument('--topic', required=True)
    begin.add_argument('--task', required=True)
    begin.add_argument('--input')
    begin.add_argument('--allow-write', action='store_true')
    begin.add_argument('--configuration', help='JSON object passed to the host, never authority')
    begin.add_argument('--form', help='Encounter-local form JSON file; omit to operate without a form')
    begin.add_argument('--hold', action='store_true', help='Wait on stdin after durable request emission; useful for process-death tests')
    scout = commands.add_parser('scout')
    scout.add_argument('--topic', required=True)
    scout.add_argument('--task', required=True)
    reply = commands.add_parser('reply')
    reply.add_argument('file')
    commands.add_parser('inspect')
    commands.add_parser('recover')

    propose = commands.add_parser('propose-return')
    propose.add_argument('--delta', required=True)
    propose.add_argument('--provenance', required=True)
    propose.add_argument('--encounters', required=True, help='Comma-separated encounter IDs')
    propose.add_argument('--scope', required=True)
    propose.add_argument('--reversal', required=True)
    propose.add_argument('--target-key', required=True)
    propose.add_argument('--target-value', required=True)

    adjudicate = commands.add_parser('adjudicate-return')
    adjudicate.add_argument('return_id')
    adjudicate.add_argument('--decision', required=True, choices=['ACCEPTED', 'REJECTED', 'RESIDUE'])
    adjudicate.add_argument('--authority', required=True)
    adjudicate.add_argument('--rationale', default='')

    list_ret = commands.add_parser('returns')
    list_ret.add_argument('--status', choices=['CANDIDATE', 'ACCEPTED', 'REJECTED', 'RESIDUE'])

    args = parser.parse_args()
    participant = Participant(args.home)
    try:
        if args.command == 'init':
            config = json.loads(Path(args.configuration_file).read_text(encoding='utf-8-sig')) if args.configuration_file else json.loads(args.configuration)
            emit(participant.initialize(args.name, config))
        elif args.command == 'begin':
            config = json.loads(args.configuration) if args.configuration else None
            if config is not None and not isinstance(config, dict):
                raise ValueError('Configuration must be an object')
            form = json.loads(Path(args.form).read_text(encoding='utf-8-sig')) if args.form else None
            emit(participant.begin(args.topic, args.task, args.input, args.allow_write, config, form))
            if args.hold:
                sys.stdin.read()
        elif args.command == 'reply':
            result = participant.finish(json.loads(Path(args.file).read_text(encoding='utf-8-sig')))
            emit(result)
            if result['status'] == 'failed':
                return 1
        elif args.command == 'recover':
            emit(participant.recover())
        elif args.command == 'propose-return':
            refs = [x.strip() for x in args.encounters.split(',') if x.strip()]
            try:
                target_val = json.loads(args.target_value)
            except json.JSONDecodeError:
                target_val = args.target_value
            try:
                delta_val = json.loads(args.delta)
            except json.JSONDecodeError:
                delta_val = args.delta
            emit(participant.propose_return(delta_val, args.provenance, refs, args.scope, args.reversal, {'key': args.target_key, 'value': target_val}))
        elif args.command == 'adjudicate-return':
            emit(participant.adjudicate_return(args.return_id, args.decision, args.authority, args.rationale))
        elif args.command == 'returns':
            emit(participant.list_returns(args.status))
        elif args.command == 'scout':
            emit(participant.scout_horizon(args.topic, args.task))
        else:
            emit(participant.inspect())
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        participant.close()


if __name__ == '__main__':
    sys.exit(main())
