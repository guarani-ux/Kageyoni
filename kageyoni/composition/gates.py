from __future__ import annotations
from typing import Any, Callable

from kageyoni.gate import GateEngine, GateRule, GateOperator

GateFn = Callable[[dict[str, Any]], dict[str, Any]]
_REGISTRY: dict[str, GateFn] = {}

class GateRegistryError(ValueError): pass

def register_gate(name: str, fn: GateFn, *, replace: bool = False) -> None:
    key = (name or '').strip().lower()
    if not key: raise GateRegistryError('gate name required')
    if not callable(fn): raise GateRegistryError('gate must be callable')
    if key in _REGISTRY and not replace: raise GateRegistryError(f'gate {key!r} already registered')
    _REGISTRY[key] = fn

def list_gates() -> list[str]: return sorted(_REGISTRY)

def run_gate(name: str, context: dict[str, Any]) -> dict[str, Any]:
    key = (name or '').strip().lower()
    fn = _REGISTRY.get(key)
    if fn is None:
        return {'gate': key, 'status': 'fail', 'code': 'UNKNOWN_GATE', 'reason': f'no verification gate registered for {key!r}'}
    try: 
        result = fn(context)
    except Exception as exc:
        return {'gate': key, 'status': 'fail', 'code': 'GATE_EXCEPTION', 'reason': f'{type(exc).__name__}: {exc}'}
    if not isinstance(result, dict) or result.get('status') not in {'pass', 'fail', 'unknown'}:
        return {'gate': key, 'status': 'fail', 'code': 'BAD_GATE_RESULT', 'reason': 'gate returned malformed result'}
    out = {'gate': key, 'code': 'OK' if result['status'] == 'pass' else result.get('code', 'REJECTED'), **result}
    return out

def _pass(ok: bool, reason: str = '') -> dict[str, Any]:
    return {'status': 'pass' if ok else 'fail', 'reason': reason if not ok else ''}

def required_slots_covered(ctx: dict[str, Any]) -> dict[str, Any]:
    slots = ctx.get('slots', [])
    rule = GateRule(field='status', op=GateOperator.NE, expected='UNKNOWN', error_message='required or active conditional slot unresolved')
    for s in slots:
        res = GateEngine.evaluate(s, [rule])
        if not res.passed:
            return _pass(False, rule.error_message)
    return _pass(True)

def authority_valid(ctx: dict[str, Any]) -> dict[str, Any]:
    bad = [
        v for s in ctx.get('slots', [])
        for v in s.get('violations', [])
        if 'authority' in v.get('reason', '') or 'host judgment' in v.get('reason', '')
    ]
    return _pass(not bad, 'authority policy violation')

def dependencies_closed(ctx: dict[str, Any]) -> dict[str, Any]:
    return _pass(not any('dependency closure' in s.get('reason', '') for s in ctx.get('slots', [])), 'slot dependency unresolved')

def cardinality_valid(ctx: dict[str, Any]) -> dict[str, Any]:
    return _pass(not any('cardinality violation' in s.get('reason', '') for s in ctx.get('slots', [])), 'slot cardinality invalid')

def no_unplaced(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get('unplaced'):
        return _pass(False, 'unplaced slot or aspect')
    rule = GateRule(field='status', op=GateOperator.NE, expected='UNPLACED', error_message='unplaced slot or aspect')
    for s in ctx.get('slots', []) :
        res = GateEngine.evaluate(s, [rule])
        if not res.passed:
            return _pass(False, rule.error_message)
    return _pass(True)

for _name, _fn in {
    'required_slots_covered': required_slots_covered,
    'authority_valid': authority_valid,
    'dependencies_closed': dependencies_closed,
    'cardinality_valid': cardinality_valid,
    'no_unplaced': no_unplaced,
}.items():
    register_gate(_name, _fn, replace=True)
