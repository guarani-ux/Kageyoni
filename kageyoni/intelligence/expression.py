"""V2: a versioned method changes a bounded, inspectable contribution.

The host owns semantic interpretation. The engine checks scopes, freshness,
exact field matches, and registered mechanical operations. No role name grants
expertise; no contribution changes the story or teaches the node automatically.
"""
from copy import deepcopy

from ..engine import digest, encoded, require, Rejected
from ..execution import operations
from ..execution.manual import judgment_packet
from ..processes.outcomes import Result, Disposition, Objective
from ..persistence.unit_of_work import UnitOfWork
from .nodes import Nodes


_REF_FIELDS = frozenset({'domain', 'id', 'record_revision', 'snapshot_hash'})
_TASK_FIELDS = frozenset({'task_id', 'revision', 'domain', 'objective', 'candidates', 'source_refs', 'method_ids', 'context'})
_LIMITS = {
    'interpretation': 'Task field meanings and method applicability are attributed trial inputs.',
    'mechanical_checks': 'Current permitted records, exact field equality, and registered operations.',
    'semantic_judgment': 'not_performed',
    'competence': 'Experimental method use does not establish expertise or grant an ability.',
    'source_truth': 'Recorded values retain their source status; their truth is not established by equality.',
    'objective_scope': 'Completion covers the registered calculation or supplied-evidence check; the task objective remains unresolved.',
}


def _text(value, name, maximum=256):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum, name + ' required or too long')
    return value


def _reference(value):
    require(isinstance(value, dict) and set(value) == _REF_FIELDS, 'source reference requires exact identity, version, and hash')
    _text(value['domain'], 'source domain', 128)
    _text(value['id'], 'source id')
    require(type(value['record_revision']) is int and value['record_revision'] > 0, 'source revision must be positive')
    require(isinstance(value['snapshot_hash'], str) and len(value['snapshot_hash']) == 64
            and all(c in '0123456789abcdef' for c in value['snapshot_hash']), 'source hash invalid')
    return dict(value)


def _key(reference):
    return (reference['domain'], reference['id'])


def _equal(left, right):
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    return type(left) is type(right) and left == right


def _scalar(value):
    return value is None or type(value) in (str, bool, int, float)


def _path(record, path):
    # Deliberately permit only the viewer's data projection. Administrative
    # evidence, event IDs, audiences, and internal version fields are not claims.
    require(isinstance(path, list) and 2 <= len(path) <= 12 and path[0] == 'data', 'evidence field path must start in record data')
    require(all((isinstance(p, str) and 0 < len(p) <= 128) or (type(p) is int and 0 <= p <= 10000) for p in path), 'invalid evidence field path')
    current = record
    for part in path:
        if isinstance(current, dict) and isinstance(part, str) and part in current:
            current = current[part]
        elif isinstance(current, list) and type(part) is int and part < len(current):
            current = current[part]
        else:
            return False, None
    return True, current


class Expression:
    def __init__(self, engine, methods=None, development=None):
        self.engine = engine
        if methods is None:
            from .methods import Methods
            methods = Methods(engine)
        self.methods = methods
        if development is None:
            from .development import Development
            development = Development(engine)
        self.development = development

    def source_ref(self, branch, record_id, viewer=None):
        """Produce a current ref only after establishing record visibility."""
        with UnitOfWork(self.engine.db):
            permitted = {r['id']: r for r in self.engine.context(branch, viewer=viewer,
                         include_properties=False, include_processes=False)['records']}
            require(record_id in permitted, 'source unavailable')
            row = self.engine.get(branch, record_id)
            return {'domain': row['domain'], 'id': row['id'], 'record_revision': row['version'],
                    'snapshot_hash': digest(row)}

    def _sources(self, branch, references, permitted):
        checked = {}
        for source in references:
            source = _reference(source)
            key = _key(source)
            require(key not in checked or checked[key] == source, 'conflicting source references')
            # Establish visibility before reading the owner snapshot or comparing
            # its hash. Hidden and absent source errors are deliberately identical.
            projection = permitted.get(source['id'])
            require(projection is not None and projection['domain'] == source['domain'], 'source unavailable or stale')
            full = self.engine.get(branch, source['id'])
            require(full['version'] == source['record_revision'] and digest(full) == source['snapshot_hash'], 'source unavailable or stale')
            checked[key] = source
        return checked

    def _claim(self, claim, sources, permitted):
        require(isinstance(claim, dict) and set(claim) == {'value', 'evidence'}, 'claim requires value and field evidence')
        value = claim['value']
        require(_scalar(value), 'claim value must be a JSON scalar')
        if type(value) in (int, float):
            require(operations.finite_number(value), 'claim number must be finite')
        if isinstance(value, str):
            require(len(value) <= 10000, 'claim text too long')
        evidence = claim['evidence']
        require(isinstance(evidence, list) and len(evidence) <= 32, 'claim evidence must be a bounded list')
        inspected, supported = [], bool(evidence) and value is not None
        for citation in evidence:
            require(isinstance(citation, dict) and set(citation) == {'source_ref', 'field_path'}, 'citation requires source reference and field path')
            reference = _reference(citation['source_ref'])
            require(sources.get(_key(reference)) == reference, 'claim source not available in declared task sources')
            record = permitted[reference['id']]
            found, actual = _path(record, citation['field_path'])
            match = found and actual is not None and _scalar(actual) and _equal(value, actual)
            supported = supported and match
            inspected.append({'source_ref': reference, 'field_path': deepcopy(citation['field_path']),
                              'source_status': record['status'], 'check': 'exact_match' if match else 'unmatched'})
        # A mismatched caller value is never presented as a checked value. It may
        # remain in a caller-only manual packet as attributed input, explicitly
        # flagged unsupported, so a host can identify the unresolved question.
        return {'value': value, 'support': 'matched' if supported else 'unmatched', 'evidence': inspected}

    def _task(self, task, sources, permitted):
        require(isinstance(task, dict) and set(task) <= _TASK_FIELDS, 'invalid task fields')
        for field, bound in (('task_id', 256), ('domain', 128), ('objective', 10000)):
            _text(task.get(field), field, bound)
        require(type(task.get('revision')) is int and task['revision'] > 0, 'task revision must be positive')
        candidates = task.get('candidates')
        require(isinstance(candidates, list) and 1 <= len(candidates) <= 100, 'task needs 1 to 100 candidates')
        inspected, seen = [], set()
        for candidate in candidates:
            require(isinstance(candidate, dict) and set(candidate) <= {'id', 'label', 'claims', 'counterclaims'}, 'invalid candidate fields')
            candidate_id = _text(candidate.get('id'), 'candidate id')
            require(candidate_id not in seen, 'candidate IDs must be distinct')
            seen.add(candidate_id)
            if 'label' in candidate:
                _text(candidate['label'], 'candidate label', 1000)
            result = {'id': candidate_id, 'claims': {}, 'counterclaims': {}}
            for kind in ('claims', 'counterclaims'):
                claims = candidate.get(kind, {})
                require(isinstance(claims, dict) and len(claims) <= 64, 'candidate claims must be a bounded object')
                require(all(isinstance(field, str) for field in claims), 'claim fields must be strings')
                for field, claim in sorted(claims.items()):
                    _text(field, 'claim field', 128)
                    result[kind][field] = self._claim(claim, sources, permitted)
            inspected.append(result)
        normalized = {'task_id': task['task_id'], 'revision': task['revision'], 'domain': task['domain'],
                      'objective': task['objective'], 'candidates': sorted(inspected, key=lambda c: c['id'])}
        if 'context' in task:
            context = task['context']
            require(isinstance(context, dict) and len(context) <= 32, 'task context must be a bounded scalar object')
            for key, value in context.items():
                _text(key, 'context key', 128)
                require(_scalar(value), 'context values must be JSON scalars')
                if type(value) in (int, float):
                    require(operations.finite_number(value), 'context number must be finite')
                if isinstance(value, str):
                    require(len(value) <= 1000, 'context value too long')
            normalized['context'] = deepcopy(context)
        return normalized

    def prepare(self, branch, character_id, task, viewer=None, workspace_id=None):
        # One snapshot covers filtered records, their owner-side hashes and
        # current assignments, including direct CLI prepare calls.
        with UnitOfWork(self.engine.db):
            return self._prepare(branch, character_id, task, viewer, workspace_id)

    def _prepare(self, branch, character_id, task, viewer=None, workspace_id=None):
        require(isinstance(task, dict), 'task must be an object')
        try:
            serialized = encoded(task)
        except (ValueError, TypeError, RecursionError, OverflowError):
            raise Rejected('task must be finite JSON') from None
        require(len(serialized) <= 500000, 'task exceeds bounded input size')
        node = Nodes(self.engine).read(branch, character_id, viewer=viewer)
        workspace_id = workspace_id or node['workspace_id']
        require(workspace_id == node['workspace_id'], 'V2 contribution requires the bound world workspace')
        context = self.engine.context(branch, viewer=viewer, include_properties=False, include_processes=False)
        permitted = {r['id']: r for r in context['records']}
        refs = task.get('source_refs', [])
        require(isinstance(refs, list) and len(refs) <= 128, 'task sources must be a bounded list')
        sources = self._sources(branch, refs, permitted)
        checked_task = self._task(task, sources, permitted)
        methods = self.methods.eligible(branch, character_id, checked_task['domain'], viewer=viewer, workspace_id=workspace_id)
        requested = task.get('method_ids')
        if requested is not None:
            require(isinstance(requested, list) and 1 <= len(requested) <= 32
                    and all(isinstance(item, str) and item for item in requested)
                    and len(set(requested)) == len(requested), 'method_ids must be a distinct bounded list')
            allowed = {m['method_id'] for m in methods}
            require(set(requested) <= allowed, 'requested method unavailable for this task')
            methods = [m for m in methods if m['method_id'] in requested]
        require(len(methods) <= 32, 'select at most 32 methods')
        methods = sorted(methods, key=lambda m: m['method_id'])
        for method in methods:
            require(method['qualification'] == 'experimental', 'method lacks bounded-trial qualification')
            require(checked_task['domain'] in method['definition']['domains'], 'method task domain mismatch')
            require(method['branch'] == branch and method['node_id'] == node['node_id']
                    and method['workspace_id'] == workspace_id, 'method scope mismatch')
            operations.validate_operation(method['definition']['operation'])
            sources.update(self._sources(branch, method['source_refs'], permitted))
        development = self.development.apply(branch, character_id, checked_task['domain'],
                                             checked_task.get('context', {}), methods,
                                             viewer=viewer, workspace_id=workspace_id)
        sources.update(self._sources(branch, development['source_refs'], permitted))
        historical_sources = []
        for ref in development['historical_source_refs']:
            ref = _reference(ref)
            record = permitted.get(ref['id'])
            require(record is not None and record['domain'] == ref['domain'], 'historical lesson source unavailable')
            historical_sources.append(ref)
        # Keep immutable method records and their digests intact. A qualified
        # lesson substitutes only params into this explicit effective copy;
        # operation kind and authored guards remain those of the base method.
        effective_methods = deepcopy(methods)
        for method in effective_methods:
            method['definition']['operation'] = development['operations'][method['method_id']]
        pending, failed = [], []
        for method in effective_methods:
            operation = method['definition']['operation']
            if operation['kind'] not in operations.SUPPORTED:
                pending.append({'method_id': method['method_id'], 'kind': 'operation', 'condition': operation['kind']})
            pending.extend(dict(g, method_id=method['method_id']) for g in operations.pending_guards(method['definition']))
            failed.extend({'method_id': method['method_id'], 'condition': g}
                          for g in operations.failed_guards(method['definition'], checked_task['candidates']))
        binding = {
            'node_id': node['node_id'], 'character_id': character_id, 'branch': branch,
            'workspace_id': workspace_id, 'viewer': viewer, 'world_revision': context['revision'],
            'profile_revision': node['profile_revision'], 'task_id': task['task_id'],
            'task_revision': task['revision'], 'task_digest': digest(task),
            'methods': [{'method_id': m['method_id'], 'revision': m['revision'], 'digest': m['digest'],
                         'assignment_revision': m['assignment_revision']} for m in methods],
            'sources': [sources[key] for key in sorted(sources)],
        }
        if development['lessons']:
            binding['lessons'] = deepcopy(development['lessons'])
        if historical_sources:
            binding['historical_sources'] = historical_sources
        phase = 'blocked' if not methods or failed or development['conflicts'] else ('waiting' if pending else 'ready')
        # Preview only pure local calculations. This establishes whether a
        # candidate-supported operation can close before any durable write.
        previews = ([{'method_id': m['method_id'],
                      'result': operations.run(m['definition']['operation'], checked_task['candidates'])}
                     for m in effective_methods] if phase == 'ready' else [])
        unsupported = bool(previews) and any(row['result']['phase'] != 'completed' for row in previews)
        if unsupported:
            phase = 'blocked'
        reasons = (['No permitted current experimental method matches this task domain.'] if not methods else
                   ['Qualified lessons propose incompatible parameters for the same method.'] if development['conflicts'] else
                   ['A declared mechanical precondition is unmet.'] if failed else
                   ['No supported candidate for a required method.'] if unsupported else
                   ['The method requires a bounded judgment.'] if pending else
                   ['Permitted current inputs are ready for a registered operation.'])
        packet = {'expression_interface': '1', 'phase': phase, 'binding': binding,
                  'task': checked_task, 'methods': deepcopy(methods), 'pending': pending,
                  'failed_guards': failed, 'operation_results': previews,
                  'reasons': reasons, 'limits': deepcopy(_LIMITS)}
        if development['lessons']:
            packet['development'] = {key: deepcopy(development[key]) for key in ('lessons', 'applications', 'conflicts')}
            packet['effective_operations'] = deepcopy(development['operations'])
        packet['fingerprint'] = digest(packet)
        return packet

    def execute(self, branch, character_id, task, viewer=None, workspace_id=None, prepared=None):
        packet = self.prepare(branch, character_id, task, viewer=viewer, workspace_id=workspace_id)
        if prepared is not None:
            require(isinstance(prepared, dict) and prepared == packet,
                    'prepared contribution no longer matches permitted current inputs')
        binding = deepcopy(packet['binding'])
        output = {'expression_interface': '1', 'phase': packet['phase'], 'binding': binding,
                  'prepared_fingerprint': packet['fingerprint'], 'artifact': None,
                  'judgment_packet': None, 'reasons': list(packet['reasons']),
                  'limits': deepcopy(_LIMITS), 'checks_passed': False, 'objective': 'unresolved',
                  'objective_scope': 'registered_operation', 'task_objective': 'unresolved'}
        if 'development' in packet:
            output['development'] = deepcopy(packet['development'])
        if packet['phase'] == 'blocked':
            Result(Disposition.BLOCKED, reason=packet['reasons'][0])
            output['outcome'] = 'insufficient_support'
            output['operation_results'] = deepcopy(packet['operation_results'])
            return output
        if packet['phase'] == 'waiting':
            handoff_methods = deepcopy(packet['methods'])
            for method in handoff_methods:
                method['definition']['operation'] = packet.get('effective_operations', {}).get(
                    method['method_id'], method['definition']['operation'])
            handoff = judgment_packet(binding, packet['task'], handoff_methods, packet['pending'])
            Result(Disposition.WAITING, reason=packet['reasons'][0], resume_condition=handoff['resume_condition'])
            output.update(outcome='requires_judgment', judgment_packet=handoff)
            return output
        results = deepcopy(packet['operation_results'])
        if any(row['result']['phase'] != 'completed' for row in results):
            Result(Disposition.BLOCKED, reason='No supported candidate for a required method.')
            output.update(phase='blocked', outcome='insufficient_support',
                          reasons=['No supported candidate for a required method.'], operation_results=results)
            return output
        content = {'task_id': task['task_id'], 'results': results, 'limits': deepcopy(_LIMITS)}
        if 'development' in packet:
            content['development'] = deepcopy(packet['development'])
        artifact = {'media_type': 'application/json', 'content': content, 'digest': digest(content)}
        # The objective is the bounded calculation/check, never the success of
        # the user's real-world plan or the acquisition of a character ability.
        Result(Disposition.COMPLETED, objective=Objective.ACHIEVED,
               reason='Registered operation results checked.', checks_passed=True, output=content)
        output.update(phase='completed', outcome='contributed', artifact=artifact,
                      checks_passed=True, objective='achieved',
                      reasons=['Registered operations produced checked results over recorded task inputs.'])
        return output


__all__ = ['Expression']
