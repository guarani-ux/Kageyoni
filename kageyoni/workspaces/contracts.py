"""Common destination envelopes; source material is always data."""
from datetime import datetime, timezone
from ..engine import digest, encoded, require, Rejected

KINDS = ('document', 'repository', 'pipeline')

def text(value, label, limit=20000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, label + ' required or too long')
    return value

def finite(value, limit=2000000):
    try:
        result = encoded(value)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise Rejected('finite JSON required') from None
    require(len(result) <= limit, 'bounded input exceeded')
    return result

def timestamp(value):
    text(value, 'timestamp', 100)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(result.tzinfo is not None, 'timestamp requires timezone')
        return result.astimezone(timezone.utc)
    except ValueError:
        raise Rejected('invalid timestamp') from None

def checkpoint(engine, branch):
    state = {'records': engine.state(branch), 'context': engine.context(branch)}
    head = engine.db.execute('SELECT event_hash FROM events WHERE branch=? ORDER BY revision DESC LIMIT 1', (branch,)).fetchone()
    return {'branch': branch, 'revision': engine.branch(branch)['revision'],
            'event_hash': head[0] if head else None, 'state_digest': digest(state)}
