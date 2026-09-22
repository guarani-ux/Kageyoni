"""Explicit unfinished handoff; preparing a packet never claims host execution."""
from copy import deepcopy


def judgment_packet(binding, task, methods, pending):
    return {
        'mode': 'manual_or_subscription_native_host',
        'state': 'waiting',
        'binding': deepcopy(binding),
        'objective': task['objective'],
        'task_domain': task['domain'],
        'candidates': deepcopy(task['candidates']),
        'methods': [{'method_id': m['method_id'], 'revision': m['revision'],
                     'operation': deepcopy(m['definition']['operation']),
                     'rationale': m['definition']['rationale'],
                     'qualification': m['qualification']} for m in methods],
        'pending': deepcopy(pending),
        'expected_response': {
            'disposition': 'supported | unsupported | unresolved',
            'rationale': 'Explain the interpretation and remaining limitations.',
            'evidence': 'Identify permitted supplied evidence for each claim.',
        },
        'resume_condition': 'A human or current authorized host resolves the listed judgments; this V2 packet does not auto-accept a reply.',
        'execution_claim': 'No host or external model has run.',
    }
