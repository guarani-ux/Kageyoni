"""D13 native metadata validation: no campaign history or SQL tampering."""
import hashlib
import subprocess
from pathlib import Path

import pytest
from kageyoni.engine import Engine, Rejected


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def register_missing(engine, kind):
    engine.register_component(kind, 'synthetic:d13-missing-' + kind, '1', 'synthetic:no-implementation')
    result = engine.validate_registry()
    assert result['ok'] is False
    assert result['errors'][0]['error'] == ('missing module manifest' if kind == 'module' else 'missing rule implementation')
    return result


@pytest.mark.parametrize('kind', ['module', 'rule'])
def test_global_verify_rejects_native_missing_implementation_without_mutation(tmp_path, kind):
    path = tmp_path / (kind + '.sqlite')
    engine = Engine(path)
    register_missing(engine, kind)
    before = sha(path)
    changes = engine.db.total_changes
    with pytest.raises(Rejected, match='^registry validation failed$') as caught:
        engine.verify()
    assert caught.value.rejection_class == 'HARD_INVARIANT_VIOLATION'
    assert engine.db.total_changes == changes
    assert engine.db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
    assert engine.db.execute('SELECT revision FROM branches').fetchone()[0] == 0
    engine.close()
    assert sha(path) == before


@pytest.mark.parametrize('kind', ['module', 'rule'])
def test_read_only_reopen_rejects_same_native_invalid_metadata(tmp_path, kind):
    path = tmp_path / (kind + '.sqlite')
    engine = Engine(path)
    expected = register_missing(engine, kind)
    engine.close()
    before = sha(path)
    engine = Engine(path, read_only=True)
    assert engine.db.execute('PRAGMA query_only').fetchone()[0] == 1
    assert engine.validate_registry() == expected
    with pytest.raises(Rejected, match='^registry validation failed$'):
        engine.verify()
    assert engine.db.total_changes == 0
    engine.close()
    assert sha(path) == before


def test_healthy_registered_module_read_only_and_checked_backup_reopen(tmp_path):
    path = tmp_path / 'healthy.sqlite'
    engine = Engine(path)
    initial = engine.verify()
    engine.register_module('synthetic:d13-valid', '1', 'synthetic:entry', [], [], [], [], {})
    assert engine.validate_registry()['ok'] is True
    assert engine.verify() == initial  # Success shape/counts remain unchanged; metadata creates no event.
    before = sha(path)
    backup = tmp_path / 'healthy.backup.sqlite'
    assert engine.backup(backup) == str(backup)
    assert sha(path) == before
    engine.close()
    for db in (path, backup):
        digest = sha(db)
        opened = Engine(db, read_only=True)
        assert opened.verify() == initial
        assert opened.validate_registry()['ok'] is True
        assert opened.db.total_changes == 0
        opened.close()
        assert sha(db) == digest


def test_checked_backup_refuses_invalid_registry_without_publishing(tmp_path):
    path = tmp_path / 'invalid.sqlite'
    engine = Engine(path)
    register_missing(engine, 'module')
    before = sha(path)
    backup = tmp_path / 'must-not-publish.sqlite'
    with pytest.raises(subprocess.CalledProcessError) as caught:
        engine.backup(backup)
    assert 'registry validation failed' in caught.value.stderr
    assert not backup.exists()
    assert not list(tmp_path.glob('.kageyoni-check-*'))
    assert sha(path) == before
    assert engine.db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
    engine.close()
