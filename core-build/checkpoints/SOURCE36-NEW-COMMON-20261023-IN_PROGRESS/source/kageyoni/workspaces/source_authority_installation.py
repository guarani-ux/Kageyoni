"""Explicit optional layout only. Full facade/history verifier is mandatory.

No connection is opened here. Importing this module does not install or grant
authority. The incomplete source proposal has no runnable/build qualification.
"""
import hashlib
import json
import math
import re
import sqlite3
from .source_authority_schema import PROFILE, SourceAuthorityError

DOMAIN = 'source_authority'
INTERFACE = '1'
COMPONENT = 'source_authority_interface'
PREFIX = 'source-authority:'
OP_PREFIX = 'source-authority-operation:'
DOMAINS = {DOMAIN: {'contract': 'json'}}
REQUIRED = {DOMAIN: ['contract']}
LOCATOR = 'kageyoni/workspaces/source_authorities.py:DOMAINS[\'source_authority\']'


def _require(condition, message):
    if not condition:
        raise SourceAuthorityError(message)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate metadata JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise SourceAuthorityError('nonfinite metadata JSON')
    def finite_float(raw):
        value = float(raw)
        _require(math.isfinite(value), 'nonfinite metadata JSON number')
        return value
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite_float)
    except (TypeError, ValueError, RecursionError) as error:
        if isinstance(error, SourceAuthorityError):
            raise
        raise SourceAuthorityError('invalid metadata JSON') from error


def structured_signal(value, parent=None):
    """Reserved structured fields, not arbitrary source/narrative prose."""
    if type(value) is dict:
        for key, child in value.items():
            name = key.casefold() if type(key) is str else ''
            if name.startswith(('source_authority', 'source-authority')):
                return True
            if type(child) is str:
                word = child.casefold()
                if name == 'domain' and word.startswith(DOMAIN):
                    return True
                if name == 'profile' and word.startswith('samsara-source-authority/'):
                    return True
                if name in ('id', 'record_id') and word.startswith(PREFIX):
                    return True
                if name in ('request_id', 'kind') and word.startswith((OP_PREFIX, DOMAIN)):
                    return True
            if structured_signal(child, name):
                return True
    elif type(value) is list:
        for child in value:
            if parent in ('changed', 'record_ids') and type(child) is str and child.casefold().startswith(PREFIX):
                return True
            if structured_signal(child, parent):
                return True
    return False


def schema_objects(source):
    """Parse every complete fixed DDL statement, including same-line tails."""
    statement = ''
    result = {}
    aliases = set()
    for line in source.splitlines(keepends=True):
        if line.lstrip().startswith('--'):
            continue
        for character in line:
            statement += character
            if character != ';' or not sqlite3.complete_statement(statement):
                continue
            match = re.match(r'\s*CREATE\s+(?:UNIQUE\s+)?(TABLE|TRIGGER|INDEX)\s+"?(\w+)"?\b', statement, re.I)
            _require(match is not None, 'source authority migration must be explicit DDL only')
            key = (match[1].lower(), match[2])
            alias = (key[0], key[1].casefold())
            _require(alias not in aliases, 'duplicate or aliased source authority DDL object')
            aliases.add(alias)
            result[key] = statement.strip().rstrip(';')
            statement = ''
    _require(not statement.strip(), 'incomplete source authority migration')
    _require(('table', DOMAIN) in result, 'source authority projection missing')
    return result


def classify_optional_layout(objects, expected, *, nonempty=(), facts=False,
                             history=False, marker=False, checksum=False, registry=False):
    _require(type(objects) is dict and type(expected) is dict, 'exact source authority layout dictionaries required')
    _require(all(type(x) is bool for x in (facts, history, marker, checksum, registry)), 'strict optional state flags')
    if marker or checksum:
        _require(marker and checksum and registry and objects == expected, 'partial or mismatched source authority installation')
        return 'installed'
    _require(not facts and not history and not registry and not nonempty, 'unmarked source authority facts/history cannot be adopted')
    if not objects:
        return 'absent'
    tables = {k: v for k, v in expected.items() if k[0] == 'table'}
    _require(set(tables) == {('table', DOMAIN)} and objects == tables, 'partial or extra pristine source authority layout')
    return 'pristine'


def _related_schema_objects(db):
    result = {}
    implicit = set()
    related = re.compile(r'\b(?:source_authority|source_authority_interface|source-authority)\b', re.I)
    for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master'):
        kind, name, table, sql = tuple(row)
        if kind == 'index' and sql is None and table == DOMAIN and name == 'sqlite_autoindex_source_authority_1':
            implicit.add(table)
            continue
        if name.casefold().startswith(('source_authority', 'source-authority')) or table.casefold() == DOMAIN or sql is not None and related.search(sql):
            result[kind, name] = sql.strip().rstrip(';') if sql is not None else None
    tables = {name for kind, name in result if kind == 'table' and name == DOMAIN}
    _require(implicit == tables, 'source authority implicit primary-key index mismatch')
    return result


def projection_signal(db, row):
    """Canonical native JSON projection metadata, before optional absence.

    Fixed model columns only; never inspect artifacts.content or source prose.
    Missing/unknown domain, projection and JSON errors remain failures.
    """
    from ..model import DOMAINS as native_domains
    domain = row['domain']
    _require(domain in native_domains, 'unknown native domain during source authority classification')
    fields = [name for name, kind in native_domains[domain].items() if kind == 'json']
    if not fields:
        return False
    quote = lambda value: '"' + value.replace('"', '""') + '"'
    projection = db.execute('SELECT ' + ','.join(quote(field) for field in fields)
                            + ' FROM ' + quote(domain) + ' WHERE branch=? AND id=?',
                            (row['branch'], row['id'])).fetchone()
    _require(projection is not None, 'native JSON projection missing during source authority classification')
    return any(structured_signal(strict_json(projection[field]))
               for field in fields if projection[field] is not None)


def _fact_and_history_signals(db):
    facts = False
    history = False
    for row in db.execute('SELECT branch,id,domain,audience_json,evidence_json FROM records'):
        branch, rid, domain, audience, evidence = tuple(row)
        facts = facts or domain.casefold().startswith(DOMAIN) or rid.casefold().startswith(PREFIX)
        facts = (structured_signal(strict_json(audience)) or structured_signal(strict_json(evidence))
                 or facts or projection_signal(db, {'branch': branch, 'id': rid, 'domain': domain}))
    # Deliberately unjoined: missing or foreign event rows must not hide signals.
    for row in db.execute('SELECT record_id,before_json,after_json FROM changes'):
        rid, before, after = tuple(row)
        history = rid.casefold().startswith(PREFIX) or history
        for raw in (before, after):
            if raw is not None:
                history = structured_signal(strict_json(raw)) or history
    for row in db.execute('SELECT request_id,kind,command_json,receipt_json FROM events'):
        request, kind, command, receipt = tuple(row)
        history = request.casefold().startswith(OP_PREFIX) or kind.casefold().startswith(DOMAIN) or history
        history = structured_signal(strict_json(command)) or structured_signal(strict_json(receipt)) or history
    for row in db.execute('SELECT state_json FROM snapshots'):
        history = structured_signal(strict_json(row[0])) or history
    return bool(facts), bool(history)


def installation_state(engine):
    """One metadata-only classifier, shared by future APIs/global/installer.

    This checks layout and bidirectional current domain identity, not complete
    native fact authenticity. Call the mandatory full facade verifier afterward.
    """
    from ..resources import schema_path
    db = engine.db
    source = schema_path('migration_036.sql').read_bytes()
    expected = schema_objects(source.decode('utf-8'))
    objects = _related_schema_objects(db)
    markers = [row for row in db.execute('SELECT component,version FROM engine_versions')
               if row[0].casefold().startswith(('source_authority', 'source-authority'))]
    checks = list(db.execute('SELECT checksum,predecessor,script_name,engine_min FROM migration_checks WHERE version=36'))
    registry = []
    for row in db.execute('SELECT kind,stable_id,version,status,locator,compatibility_json FROM registry_entries'):
        kind, stable, version, status, locator, compatibility = tuple(row)
        decoded = strict_json(compatibility)
        if stable.casefold().startswith(('source_authority', 'source-authority', 'migration_036')) or 'source_authorit' in locator.casefold() or structured_signal(decoded):
            registry.append(tuple(row))
    facts, history = _fact_and_history_signals(db)
    present = ('table', DOMAIN) in objects
    nonempty = (DOMAIN,) if present and db.execute('SELECT 1 FROM source_authority LIMIT 1').fetchone() else ()
    state = classify_optional_layout(objects, expected, nonempty=nonempty, facts=facts, history=history,
                                     marker=bool(markers), checksum=bool(checks), registry=bool(registry))
    if state != 'installed':
        return state
    _require([tuple(r) for r in markers] == [(COMPONENT, INTERFACE)], 'source authority marker aliases/version mismatch')
    _require([tuple(r) for r in checks] == [(hashlib.sha256(source).hexdigest(), 35, 'migration_036.sql', '4')], 'source authority migration predecessor/checksum mismatch')
    _require(registry == [('domain', DOMAIN, '1', 'verified', LOCATOR, '{"source_authority_interface":"1"}')], 'source authority registry binding mismatch')
    from .. import model
    _require(model.DOMAINS.get(DOMAIN) == DOMAINS[DOMAIN] and model.REQUIRED.get(DOMAIN) == REQUIRED[DOMAIN], 'source authority common model binding missing')
    _require(not db.execute('SELECT 1 FROM source_authority p LEFT JOIN records r ON r.branch=p.branch AND r.id=p.id WHERE r.domain IS NULL OR r.domain<>? LIMIT 1', (DOMAIN,)).fetchone(), 'source authority projection attached to wrong/missing record domain')
    _require(not db.execute('SELECT 1 FROM records r LEFT JOIN source_authority p ON p.branch=r.branch AND p.id=r.id WHERE r.domain=? AND p.id IS NULL LIMIT 1', (DOMAIN,)).fetchone(), 'source authority record projection missing')
    return state


def _maintenance_token(engine):
    return (engine.db.total_changes, engine.db.execute('PRAGMA data_version').fetchone()[0],
            tuple(tuple(r) for r in engine.db.execute('SELECT id,revision,parent,fork_revision FROM branches ORDER BY id')),
            tuple(tuple(r) for r in engine.db.execute('SELECT version,checksum FROM migration_checks ORDER BY version')))


def install_source_authority(engine):
    """Explicit checked backup before any DDL; no open-time installation.

    Missing full facade is a hard refusal BEFORE verification/backup/mutation.
    This incomplete proposal deliberately cannot activate the optional service.
    """
    from .source_authorities import verify_source_authorities
    from pathlib import Path
    import stat
    from uuid import uuid4
    from ..resources import schema_path
    from ..persistence.unit_of_work import UnitOfWork
    from ..contests import verify_contests
    db = engine.db
    _require(not db.in_transaction and not db.execute('PRAGMA query_only').fetchone()[0], 'finish writable transaction before source authority installation')
    state = installation_state(engine)
    if state == 'installed':
        _require(engine.verify()['ok'] and engine.validate_registry()['ok'], 'installed source authority global/registry verification failed')
        return verify_source_authorities(engine)
    _require(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0] == 35 and verify_contests(engine)['installed'], 'actual checked Native035 predecessor required')
    token = _maintenance_token(engine)
    verification = engine.verify()
    registry = engine.validate_registry()
    _require(verification['ok'] and registry['ok'] and _maintenance_token(engine) == token, 'source authority preflight verification changed/failed')
    _require(str(engine.path) != ':memory:', 'source authority installation requires real file-backed checked backup')
    destination = Path(engine.path).with_name(Path(engine.path).name + '.pre-v36-' + uuid4().hex + '.bak')
    backup = engine.backup(destination)
    _require(Path(backup).resolve() == destination.resolve() and stat.S_ISREG(destination.lstat().st_mode), 'source authority checked backup publication mismatch')
    backup_proof = {'path': str(destination), 'bytes': destination.stat().st_size, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'producer': 'Engine.backup checked verifier/two read-only reopens'}
    source = schema_path('migration_036.sql').read_bytes()
    objects = schema_objects(source.decode('utf-8'))
    with UnitOfWork(db):
        _require(_maintenance_token(engine) == token and installation_state(engine) == state and state in ('absent', 'pristine'), 'source authority world/layout changed during checked backup')
        _require(schema_path('migration_036.sql').read_bytes() == source, 'source authority DDL changed before installation')
        for (kind, name), statement in objects.items():
            if kind == 'table' and state == 'pristine':
                continue
            db.execute(statement)
        db.execute('INSERT INTO engine_versions(component,version) VALUES(?,?)', (COMPONENT, INTERFACE))
        db.execute('INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(?,?,?,?,?)', (36, 35, 'migration_036.sql', hashlib.sha256(source).hexdigest(), '4'))
        engine.register_component('domain', DOMAIN, '1', LOCATOR, status='verified', readers=['SourceAuthorities.inspect', 'Engine.get'], writers=['SourceAuthorities.capture', 'SourceAuthorities.withdraw'], compatibility={COMPONENT: INTERFACE}, declared_by='explicit-source-authority-installer')
        result = verify_source_authorities(engine)
        _require(engine.verify()['ok'] and engine.validate_registry()['ok'], 'source authority post-install global/registry validation failed')
    result['maintenance'] = {'checked_backup': backup_proof, 'preflight_verification': verification, 'preflight_registry': registry}
    return result
