"""Apply qualified, scoped lessons as explicit operational interventions.

Storage owns outcome and review authority. This layer cannot qualify a lesson:
it combines only current eligible lessons into bounded parameter substitutions.
It never changes the stored method, its guards, a character ability, or a stat.
"""
from copy import deepcopy

from ..engine import digest, encoded, require
from ..execution import operations
from ..persistence.unit_of_work import UnitOfWork


def same_scalar(left, right):
    """JSON scalar equality with bool distinct from numeric values."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    return type(left) is type(right) and left == right


def context_matches(conditions, context):
    """V3 scope is the full evidenced context, not a semantic similarity guess."""
    if not isinstance(conditions, list) or not conditions:
        return False
    if not all(isinstance(c, dict) and set(c) == {'key', 'equals'} and isinstance(c['key'], str)
               for c in conditions):
        return False
    expected = {c['key']: c['equals'] for c in conditions}
    return len(expected) == len(conditions) and set(expected) == set(context) and all(
        key in context and same_scalar(context[key], value) for key, value in expected.items())


class Development:
    def __init__(self, engine, learning=None):
        self.engine, self.learning = engine, learning

    def _storage(self):
        if self.learning is not None:
            return self.learning
        row = self.engine.db.execute("SELECT version FROM engine_versions WHERE component='learning_interface'").fetchone()
        if row is None:
            return None
        require(row[0] == '1', 'unsupported learning interface')
        from .learning import Learning
        return Learning(self.engine)

    def applicable(self, branch, character_id, task_domain, context, methods,
                   viewer=None, workspace_id=None):
        with UnitOfWork(self.engine.db):
            storage = self._storage()
            if storage is None or not methods:
                return []
            rows = storage.applicable(branch, character_id, task_domain, context, methods,
                                      viewer=viewer, workspace_id=workspace_id)
            method_by_id = {method['method_id']: method for method in methods}
            selected, seen = [], set()
            for row in rows:
                definition = row['definition']
                intervention = row['intervention']
                method = method_by_id.get(intervention['method_id'])
                # Storage has already qualified and scoped the row. Recheck the
                # application boundary rather than broadening that authority.
                if method is None or method['revision'] != intervention['method_revision']:
                    continue
                if (row['status'] != 'qualified' or not row['source_fresh'] or not row['assignment_current']
                        or method['assignment_revision'] != row['method_assignment_revision']
                        or method['assignment_digest'] != row['method_assignment_digest']):
                    continue
                if (row['branch'] != branch or row['workspace_id'] != method['workspace_id']
                        or row['node_id'] != method['node_id']
                        or definition['task_domain'] != task_domain
                        or definition['method_id'] != method['method_id']
                        or definition['method_revision'] != method['revision']
                        or not context_matches(definition['context_conditions'], context)):
                    continue
                require(row['lesson_id'] not in seen, 'duplicate applicable lesson')
                seen.add(row['lesson_id'])
                require(type(row['revision']) is int and row['revision'] > 0
                        and type(row['review_revision']) is int and row['review_revision'] > 0,
                        'lesson and review revisions required')
                require(isinstance(row['digest'], str) and len(row['digest']) == 64
                        and isinstance(row['review_digest'], str) and len(row['review_digest']) == 64,
                        'lesson and review digests required')
                require(intervention['operation_params'] == definition['operation_params'], 'lesson intervention mismatch')
                operation = {'kind': method['definition']['operation']['kind'],
                             'params': deepcopy(intervention['operation_params'])}
                operations.validate_operation(operation)
                selected.append(deepcopy(row))
            return sorted(selected, key=lambda row: row['lesson_id'])

    def apply(self, branch, character_id, task_domain, context, methods,
              viewer=None, workspace_id=None):
        """Return effective copies and trace; incompatible lessons never win by order."""
        lessons = self.applicable(branch, character_id, task_domain, context, methods,
                                  viewer=viewer, workspace_id=workspace_id)
        method_by_id = {method['method_id']: method for method in methods}
        effective = {key: deepcopy(method['definition']['operation']) for key, method in method_by_id.items()}
        grouped = {}
        for lesson in lessons:
            grouped.setdefault(lesson['intervention']['method_id'], []).append(lesson)
        conflicts, applications = [], []
        for method_id, group in sorted(grouped.items()):
            variants = {digest(row['intervention']['operation_params']) for row in group}
            if len(variants) > 1:
                conflicts.append({'method_id': method_id, 'lesson_ids': [row['lesson_id'] for row in group],
                                  'reason': 'qualified_lessons_propose_incompatible_parameters'})
                continue
            base = deepcopy(effective[method_id])
            effective[method_id]['params'] = deepcopy(group[0]['intervention']['operation_params'])
            applications.append({'method_id': method_id, 'method_revision': method_by_id[method_id]['revision'],
                                 'lesson_ids': [row['lesson_id'] for row in group],
                                 'base_operation': base, 'effective_operation': deepcopy(effective[method_id])})
        bindings = [{key: row[key] for key in ('lesson_id', 'revision', 'digest', 'review_revision', 'review_digest')}
                    for row in lessons]
        # The reviewed lesson digest pins its complete outcome/counterevidence
        # history; the review digest pins the current qualification decision.
        for binding, row in zip(bindings, lessons):
            binding.update(method_id=row['intervention']['method_id'],
                           method_revision=row['intervention']['method_revision'],
                           qualification=row['status'], evidence_digest=row['evidence_digest'],
                           counterevidence_digest=digest(sorted(row['counter_outcome_ids'])))
        refs, historical = {}, {}
        for lesson in lessons:
            for ref in lesson['source_refs']:
                key = (ref['domain'], ref['id'])
                require(key not in refs or refs[key] == ref, 'conflicting lesson evidence references')
                refs[key] = deepcopy(ref)
            for ref in lesson['historical_source_refs']:
                # Contrary historical observations retain their exact old
                # versions without being rewritten as current supporting facts.
                historical[encoded(ref)] = deepcopy(ref)
        return {'lessons': bindings, 'operations': effective, 'applications': applications,
                'conflicts': conflicts, 'source_refs': [refs[key] for key in sorted(refs)],
                'historical_source_refs': [historical[key] for key in sorted(historical)]}


__all__ = ['Development', 'context_matches']
