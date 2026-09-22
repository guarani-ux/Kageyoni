"""Small deterministic operations over already scoped, checked claim inputs.

These operations calculate from recorded inputs. They do not establish what a
field means, establish source truth, or grant competence to a character.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import math

from ..engine import require


SUPPORTED = frozenset({'constraint_rank', 'counterexample_check'})
GUARDS = {
    'preconditions': frozenset({'task_domain_matches', 'sources_current',
                               'claims_match_recorded_fields', 'numeric_criteria'}),
    'failure_conditions': frozenset({'missing_support', 'conflicting_evidence', 'stale_source'}),
    'checking_procedure': frozenset({'check_source_fields', 'recompute_scores', 'compare_counterclaims'}),
}


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def validate_operation(operation):
    """Validate known operations only; unknown operations require human/host work."""
    require(isinstance(operation, dict) and isinstance(operation.get('kind'), str), 'method operation required')
    require(set(operation) <= {'kind', 'params'}, 'unknown operation field')
    params = operation.get('params', {})
    require(isinstance(params, dict), 'operation params must be an object')
    if operation['kind'] == 'constraint_rank':
        require(set(params) <= {'criteria', 'max_results'}, 'unknown ranking parameter')
        criteria = params.get('criteria')
        require(isinstance(criteria, list) and 1 <= len(criteria) <= 32, 'ranking needs 1 to 32 criteria')
        seen = set()
        for criterion in criteria:
            require(isinstance(criterion, dict) and set(criterion) <= {'field', 'weight', 'direction', 'required'}, 'invalid ranking criterion')
            field = criterion.get('field')
            require(isinstance(field, str) and 0 < len(field) <= 128 and field not in seen, 'criterion fields must be distinct')
            seen.add(field)
            require(finite_number(criterion.get('weight')) and 0 < criterion['weight'] <= 1e6, 'criterion weight must be finite and positive')
            require(criterion.get('direction') in ('maximize', 'minimize'), 'criterion direction required')
            require(type(criterion.get('required', True)) is bool, 'criterion required flag must be boolean')
        limit = params.get('max_results', 100)
        require(type(limit) is int and 1 <= limit <= 100, 'max_results must be 1 to 100')
    elif operation['kind'] == 'counterexample_check':
        require(set(params) <= {'fields'}, 'unknown counterexample parameter')
        fields = params.get('fields')
        require(isinstance(fields, list) and 1 <= len(fields) <= 32, 'counterexample check needs 1 to 32 fields')
        require(all(isinstance(f, str) and 0 < len(f) <= 128 for f in fields), 'invalid counterexample field')
        require(len(set(fields)) == len(fields), 'counterexample fields must be distinct')
    return operation


def pending_guards(definition):
    operation = definition['operation']['kind']
    disallowed = {'numeric_criteria', 'recompute_scores', 'missing_support', 'conflicting_evidence'} if operation != 'constraint_rank' else set()
    return [{'kind': kind, 'condition': value}
            for kind, supported in GUARDS.items()
            for value in definition.get(kind, []) if value not in supported or value in disallowed]


def failed_guards(definition, candidates):
    """Evaluate recognized preconditions that are stricter than operation defaults."""
    failures = []
    preconditions = definition.get('preconditions', [])
    if 'claims_match_recorded_fields' in preconditions:
        if any(claim['support'] != 'matched' for candidate in candidates
               for kind in ('claims', 'counterclaims') for claim in candidate[kind].values()):
            failures.append('claims_match_recorded_fields')
    if 'numeric_criteria' in preconditions and definition['operation']['kind'] == 'constraint_rank':
        fields = [c['field'] for c in definition['operation']['params']['criteria']]
        if any(field in candidate['claims'] and not finite_number(candidate['claims'][field]['value'])
               for candidate in candidates for field in fields):
            failures.append('numeric_criteria')
    return failures


def _decimal(value):
    # Decimal avoids overflowing otherwise finite values during weighted sums.
    return Decimal(str(value))


def _conflict(claim, counter):
    if not claim or not counter or claim['support'] != 'matched' or counter['support'] != 'matched':
        return False
    # Bool and numeric values are different types, even though Python says 1 == True.
    left, right = claim['value'], counter['value']
    if type(left) is bool or type(right) is bool:
        return type(left) is not type(right) or left != right
    return left != right


def _constraint_rank(params, candidates):
    """Weighted recorded values, without normalizing unrelated units or guessing."""
    rows, excluded = [], []
    criteria = params['criteria']
    for candidate in candidates:
        reasons, terms, unknowns = [], [], []
        total = Decimal(0)
        for criterion in criteria:
            field = criterion['field']
            claim = candidate['claims'].get(field)
            counter = candidate['counterclaims'].get(field)
            problem = None
            if not claim or claim['support'] != 'matched':
                problem = 'missing_or_unmatched_evidence'
            elif not finite_number(claim['value']):
                problem = 'criterion_is_not_a_finite_number'
            elif _conflict(claim, counter):
                problem = 'conflicting_recorded_values'
            elif counter and counter['support'] != 'matched':
                # An unsupported objection is an unresolved objection, not proof
                # that the candidate is bad and not permission to ignore it.
                problem = 'unresolved_counterclaim'
            if problem:
                issue = {'field': field, 'reason': problem}
                (reasons if criterion.get('required', True) else unknowns).append(issue)
                continue
            sign = 1 if criterion['direction'] == 'maximize' else -1
            term = _decimal(claim['value']) * _decimal(criterion['weight']) * sign
            total += term
            terms.append({'field': field, 'recorded_value': claim['value'],
                          'weight': criterion['weight'], 'direction': criterion['direction'],
                          'term': str(term), 'evidence': deepcopy(claim['evidence'])})
        if reasons or not terms:
            excluded.append({'candidate_id': candidate['id'], 'reasons': reasons or [
                {'reason': 'no_supported_numeric_criteria'}], 'unknowns': unknowns})
        else:
            rows.append({'candidate_id': candidate['id'], 'score': str(total),
                         'terms': terms, 'unknowns': unknowns})
    # Candidate IDs break ties predictably; names, prose, and list order do not.
    rows.sort(key=lambda row: (Decimal(row['score']).copy_negate(), row['candidate_id']))
    eligible_count = len(rows)
    rows = rows[:params.get('max_results', 100)]
    for index, row in enumerate(rows, 1):
        row['rank'] = index
    return {'operation': 'constraint_rank', 'phase': 'completed' if rows else 'blocked',
            'ranked': rows, 'excluded': excluded, 'eligible_count': eligible_count,
            'reason': 'weighted_recorded_inputs' if rows else 'no_supported_candidate',
            'score_policy': 'sum(value * weight * direction); no unit conversion',
            'selection_policy': 'required missing/conflicting values exclude; optional unknowns add no score'}


def constraint_rank(params, candidates):
    # Every permitted finite float/int and positive <=1e6 weight fits in this
    # precision even at opposite exponent extremes. Do not let ambient Decimal
    # context silently turn a meaningful difference into an ID-based tie.
    with localcontext() as context:
        context.prec = 1024
        result = _constraint_rank(params, candidates)
    # Recompute using exact rational arithmetic, separately from Decimal scoring.
    for row in result['ranked']:
        exact = sum((Fraction(str(term['recorded_value'])) * Fraction(str(term['weight']))
                     * (1 if term['direction'] == 'maximize' else -1) for term in row['terms']), Fraction(0))
        require(exact == Fraction(row['score']), 'score recomputation failed')
    return result


def counterexample_check(params, candidates):
    observations = []
    for candidate in candidates:
        fields = []
        for field in params['fields']:
            claim = candidate['claims'].get(field)
            counter = candidate['counterclaims'].get(field)
            if not claim or claim['support'] != 'matched':
                state = 'unsupported_claim'
            elif counter and counter['support'] != 'matched':
                state = 'unresolved_counterclaim'
            elif _conflict(claim, counter):
                state = 'conflicting_recorded_values'
            else:
                state = 'no_supplied_conflict'
            fields.append({'field': field, 'state': state,
                           'claim_evidence': deepcopy(claim['evidence']) if claim else [],
                           'counter_evidence': deepcopy(counter['evidence']) if counter else []})
        observations.append({'candidate_id': candidate['id'], 'fields': fields})
    return {'operation': 'counterexample_check', 'phase': 'completed',
            'observations': observations, 'reason': 'supplied_claims_examined',
            'coverage': 'supplied evidence only; absence of a supplied conflict does not prove a claim'}


def run(operation, candidates):
    validate_operation(operation)
    require(operation['kind'] in SUPPORTED, 'operation requires external judgment')
    return {'constraint_rank': constraint_rank,
            'counterexample_check': counterexample_check}[operation['kind']](operation.get('params', {}), candidates)
