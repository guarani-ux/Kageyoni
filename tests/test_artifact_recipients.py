"""Immutable recipient-at-creation over real disposable native workspaces.

The shared owner workspace stays owner-mediated. This is not a workspace ACL
change, transitive product authorization check, or filesystem isolation claim.
"""
import hashlib
from pathlib import Path

import pytest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.nodes import Nodes
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.persistence.migrations import install_workspaces
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.documents import Documents
from kageyoni.workspaces.registry import Registry


CAPTURED = '2000-01-01T00:00:00+00:00'


@pytest.fixture
def native(tmp_path):
    engine = Engine(tmp_path / 'synthetic.sqlite')
    assert engine.verify()['ok'] and engine.validate_registry()['ok']
    engine.apply(dict(api_version=3, branch='main', request_id='seed', expected_revision=0,
        kind='scene', actor='fixture', narrative='Explicit disposable native recipient fixture',
        changes=[dict(op='create', id=actor, domain='character', status='proposed',
                      visibility='public', evidence=[{'note': 'Synthetic identity, not campaign canon.'}],
                      data={'name': actor, 'entity_kind': 'person'}) for actor in ('visitor', 'keeper')]))
    install_workspaces(engine)
    for actor in ('visitor', 'keeper'):
        Nodes(engine).bind('main', actor, 'node:' + actor, 1, {'note': 'Synthetic fixture binding.'})
    registry = Registry(engine)
    shared = registry.open('main', 'visitor', 'document', 'workspace:shared', source_ids=[])
    visitor = registry.open('main', 'visitor', 'document', 'workspace:visitor', viewer='visitor', source_ids=[])
    keeper = registry.open('main', 'keeper', 'document', 'workspace:keeper', viewer='keeper', source_ids=[])
    value = dict(engine=engine, artifacts=Artifacts(engine), documents=Documents(engine),
                 shared=shared['workspace_id'], visitor=visitor['workspace_id'], keeper=keeper['workspace_id'])
    try:
        yield value
        assert engine.verify()['ok']
        assert engine.validate_registry()['ok']
    finally:
        engine.close()


def row(native, artifact_id):
    return dict(native['engine'].db.execute('SELECT * FROM artifacts WHERE artifact_id=?', (artifact_id,)).fetchone())


def ingest(native, request='source', source='source', workspace=None, **kw):
    return native['documents'].ingest(workspace or native['shared'], request, source,
        'Exact captured source bytes.', 'Synthetic source', 'Synthetic source', CAPTURED, **kw)


@pytest.mark.parametrize('viewer', [None, 'visitor'])
def test_default_and_explicit_none_preserve_historical_artifact_payload_and_shape(native, viewer):
    body = 'Legacy Unicode bytes・旅'; blob = body.encode()
    workspace = native['visitor'] if viewer else native['shared']
    artifact = native['artifacts'].put(body, 'text/plain', 'legacy', workspace_id=workspace, viewer=viewer)
    saved = row(native, artifact['artifact_id'])
    legacy_payload = dict(workspace_id=workspace, viewer=viewer, media_type='text/plain',
                          digest=hashlib.sha256(blob).hexdigest(), size=len(blob))
    assert saved['payload_hash'] == digest(legacy_payload) and saved['viewer'] == viewer
    assert set(artifact) == {'artifact_id', 'workspace_id', 'digest', 'media_type', 'size', 'path', 'relative_path'}
    assert native['artifacts'].put(blob, 'text/plain', 'legacy', workspace_id=workspace, viewer=viewer, recipient=None) == artifact
    assert row(native, artifact['artifact_id']) == saved
    assert native['artifacts'].read(artifact['artifact_id'])['content'] == blob


def test_owner_sets_private_immutable_audience_in_shared_workspace_at_creation(native):
    artifact = native['artifacts'].put(b'Private captured bytes', 'text/plain', 'private',
                                     workspace_id=native['shared'], viewer=None, recipient='visitor')
    saved = row(native, artifact['artifact_id'])
    assert saved['viewer'] == 'visitor' and saved['workspace_id'] == native['shared']
    assert native['artifacts'].read(artifact['artifact_id'], viewer=None)['content'] == b'Private captured bytes'
    for actor in ('visitor', 'keeper'):
        with pytest.raises(Rejected, match='workspace unavailable'):
            native['artifacts'].read(artifact['artifact_id'], viewer=actor)
    # No alternate actor workspace or fictional event was created by put.
    assert native['engine'].branch('main')['revision'] == 1
    assert native['engine'].db.execute('SELECT COUNT(*) FROM operational_workspaces').fetchone()[0] == 3


def test_explicit_same_recipient_retains_callers_workspace_authority(native):
    artifact = native['artifacts'].put('For visitor', 'text/plain', 'same',
                                     workspace_id=native['visitor'], viewer='visitor', recipient='visitor')
    assert native['artifacts'].read(artifact['artifact_id'], viewer='visitor')['content'] == b'For visitor'
    assert row(native, artifact['artifact_id'])['viewer'] == 'visitor'
    with pytest.raises(Rejected):native['artifacts'].read(artifact['artifact_id'], viewer='keeper')
    with pytest.raises(Rejected, match='workspace unavailable'):
        native['artifacts'].put('Must not write', 'text/plain', 'wrong-workspace',
            workspace_id=native['shared'], viewer='visitor', recipient='visitor')
    assert native['engine'].db.execute("SELECT COUNT(*) FROM artifacts WHERE request_id='wrong-workspace'").fetchone()[0] == 0


def test_nonowner_cannot_select_another_recipient_even_in_authorized_workspace(native):
    with pytest.raises(Rejected, match='only owner'):
        native['artifacts'].put('Forbidden', 'text/plain', 'other-reader',
            workspace_id=native['visitor'], viewer='visitor', recipient='keeper')
    with pytest.raises(Rejected, match='only owner'):
        ingest(native, workspace=native['visitor'], viewer='visitor', recipient='keeper')
    assert native['engine'].db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0
    assert native['engine'].db.execute('SELECT COUNT(*) FROM document_sources').fetchone()[0] == 0


@pytest.mark.parametrize('recipient', ['', '   ', 3, False, [], {}, 'x' * 1025, ' ' * 1025 + 'visitor'])
def test_malformed_or_unbounded_recipient_creates_no_artifact_or_source(native, recipient):
    with pytest.raises(Rejected):
        native['artifacts'].put('Do not persist', 'text/plain', 'bad-recipient',
                               workspace_id=native['shared'], recipient=recipient)
    with pytest.raises(Rejected):ingest(native, recipient=recipient)
    assert native['engine'].db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0
    assert native['engine'].db.execute('SELECT COUNT(*) FROM document_sources').fetchone()[0] == 0


def test_explicit_recipient_binds_exact_retry_and_does_not_retarget_existing_artifact(native):
    artifact = native['artifacts'].put('Stable bytes', 'text/plain', 'private-retry',
                                     workspace_id=native['shared'], recipient='visitor')
    saved = row(native, artifact['artifact_id'])
    assert native['artifacts'].put('Stable bytes', 'text/plain', 'private-retry',
                                  workspace_id=native['shared'], recipient='visitor') == artifact
    for recipient in ('keeper', None):
        with pytest.raises(Rejected, match='artifact request conflict'):
            native['artifacts'].put('Stable bytes', 'text/plain', 'private-retry',
                                   workspace_id=native['shared'], recipient=recipient)
    with pytest.raises(Rejected, match='artifact request conflict'):
        native['artifacts'].put('Altered bytes', 'text/plain', 'private-retry',
                               workspace_id=native['shared'], recipient='visitor')
    assert row(native, artifact['artifact_id']) == saved
    assert native['engine'].db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 1


def test_default_artifact_cannot_be_restricted_by_reusing_old_request_id(native):
    artifact = native['artifacts'].put('Legacy bytes', 'text/plain', 'old-request', workspace_id=native['shared'])
    saved = row(native, artifact['artifact_id'])
    with pytest.raises(Rejected, match='artifact request conflict'):
        native['artifacts'].put('Legacy bytes', 'text/plain', 'old-request',
                               workspace_id=native['shared'], recipient='visitor')
    assert row(native, artifact['artifact_id']) == saved and saved['viewer'] is None


def test_explicit_same_audience_is_distinct_from_omitted_argument_retry(native):
    artifact = native['artifacts'].put('Same audience', 'text/plain', 'explicit',
        workspace_id=native['visitor'], viewer='visitor', recipient='visitor')
    with pytest.raises(Rejected, match='artifact request conflict'):
        native['artifacts'].put('Same audience', 'text/plain', 'explicit',
                               workspace_id=native['visitor'], viewer='visitor')
    assert row(native, artifact['artifact_id'])['viewer'] == 'visitor'


def test_content_deduplication_does_not_merge_recipient_authority(native):
    shared_bytes = b'Identical content, two independent immutable audiences'
    visitor = native['artifacts'].put(shared_bytes, 'text/plain', 'visitor-object',
                                    workspace_id='world:main', recipient='visitor')
    keeper = native['artifacts'].put(shared_bytes, 'text/plain', 'keeper-object',
                                   workspace_id='world:main', recipient='keeper')
    assert visitor['artifact_id'] != keeper['artifact_id'] and visitor['digest'] == keeper['digest']
    assert visitor['relative_path'] == keeper['relative_path']
    for own, other, actor in ((visitor, keeper, 'visitor'), (keeper, visitor, 'keeper')):
        assert native['artifacts'].read(own['artifact_id'], viewer=actor)['content'] == shared_bytes
        with pytest.raises(Rejected, match='artifact unavailable'):
            native['artifacts'].read(other['artifact_id'], viewer=actor)
    assert native['artifacts'].read(keeper['artifact_id'])['content'] == shared_bytes


def test_unknown_or_different_workspace_cannot_replay_private_artifact(native):
    artifact = native['artifacts'].put('Original bytes', 'text/plain', 'workspace-bound',
        workspace_id=native['shared'], recipient='visitor'); saved = row(native, artifact['artifact_id'])
    with pytest.raises(Rejected, match='workspace unavailable'):
        native['artifacts'].put('Original bytes', 'text/plain', 'workspace-bound',
                               workspace_id='missing-workspace', recipient='visitor')
    with pytest.raises(Rejected, match='artifact request conflict'):
        native['artifacts'].put('Original bytes', 'text/plain', 'workspace-bound',
                               workspace_id=native['keeper'], recipient='visitor')
    assert row(native, artifact['artifact_id']) == saved


@pytest.mark.parametrize('viewer', [None, 'visitor'])
def test_default_document_payload_and_child_artifact_remain_legacy_compatible(native, viewer):
    workspace = native['visitor'] if viewer else native['shared']
    source = ingest(native, workspace=workspace, viewer=viewer)
    payload = dict(workspace_id=workspace, source_id='source', text='Exact captured source bytes.',
        identity='Synthetic source', expected_identity='Synthetic source', captured_at=CAPTURED,
        expires_at=None, viewer=viewer, locator='subscription-host supplied')
    saved = dict(native['engine'].db.execute("SELECT * FROM document_sources WHERE request_id='source'").fetchone())
    assert saved['payload_hash'] == digest(payload)
    assert row(native, source['artifact_id'])['viewer'] == viewer
    assert ingest(native, workspace=workspace, viewer=viewer, recipient=None) == source
    assert dict(native['engine'].db.execute("SELECT * FROM document_sources WHERE request_id='source'").fetchone()) == saved


def test_restricted_document_ingest_stores_source_audience_at_creation(native):
    source = ingest(native, recipient='visitor')
    saved = row(native, source['artifact_id'])
    assert saved['viewer'] == 'visitor' and bytes(saved['content']) == b'Exact captured source bytes.'
    assert native['documents'].source(native['shared'], 'source')['text'] == source['text']
    assert ingest(native, recipient='visitor') == source
    for actor in ('visitor', 'keeper'):
        with pytest.raises(Rejected, match='workspace unavailable'):
            native['documents'].source(native['shared'], 'source', viewer=actor)
    for recipient in ('keeper', None):
        with pytest.raises(Rejected, match='source request conflict'):ingest(native, recipient=recipient)
    assert row(native, source['artifact_id']) == saved


def test_actor_ingest_same_recipient_works_only_in_its_authorized_workspace(native):
    source = ingest(native, workspace=native['visitor'], viewer='visitor', recipient='visitor')
    assert native['documents'].source(native['visitor'], 'source', viewer='visitor') == source
    with pytest.raises(Rejected):native['documents'].source(native['visitor'], 'source', viewer='keeper')
    with pytest.raises(Rejected, match='workspace unavailable'):
        ingest(native, request='shared-denied', viewer='visitor', recipient='visitor')
    with pytest.raises(Rejected, match='source request conflict'):
        ingest(native, workspace=native['keeper'], recipient='visitor')


def test_private_artifact_materialization_failure_retains_exact_audience_for_recovery(native, monkeypatch):
    original = native['artifacts']._materialize
    def interrupted(*args, **kw):raise RuntimeError('Interruption after native immutable row commit')
    monkeypatch.setattr(native['artifacts'], '_materialize', interrupted)
    with pytest.raises(RuntimeError, match='immutable row commit'):
        native['artifacts'].put('Recover exact private bytes', 'text/plain', 'recover',
                               workspace_id=native['shared'], recipient='visitor')
    saved = dict(native['engine'].db.execute("SELECT * FROM artifacts WHERE request_id='recover'").fetchone())
    assert saved['viewer'] == 'visitor'
    monkeypatch.setattr(native['artifacts'], '_materialize', original)
    assert native['artifacts'].recover()['pending_materialization'] == 0
    artifact = native['artifacts'].put('Recover exact private bytes', 'text/plain', 'recover',
                                     workspace_id=native['shared'], recipient='visitor')
    assert artifact['artifact_id'] == saved['artifact_id'] and row(native, artifact['artifact_id']) == saved
    assert native['artifacts'].read(artifact['artifact_id'])['content'] == b'Recover exact private bytes'


def test_outer_rollback_does_not_accept_private_artifact_or_document(native):
    with pytest.raises(RuntimeError, match='outer rollback'):
        with UnitOfWork(native['engine'].db):
            artifact = native['artifacts'].put('Unaccepted private bytes', 'text/plain', 'outer-artifact',
                                             workspace_id=native['shared'], recipient='visitor')
            source = ingest(native, recipient='visitor')
            assert row(native, artifact['artifact_id'])['viewer'] == 'visitor'
            assert row(native, source['artifact_id'])['viewer'] == 'visitor'
            raise RuntimeError('outer rollback')
    assert native['engine'].db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0
    assert native['engine'].db.execute('SELECT COUNT(*) FROM document_sources').fetchone()[0] == 0
    assert ingest(native, recipient='visitor')['revision'] == 1


def test_document_materialization_failure_rolls_back_both_native_rows(native, monkeypatch):
    original = Artifacts._materialize
    def interrupted(*args, **kw):raise RuntimeError('Interruption inside native ingest transaction')
    monkeypatch.setattr(Artifacts, '_materialize', interrupted)
    with pytest.raises(RuntimeError, match='ingest transaction'):ingest(native, recipient='visitor')
    assert native['engine'].db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0
    assert native['engine'].db.execute('SELECT COUNT(*) FROM document_sources').fetchone()[0] == 0
    monkeypatch.setattr(Artifacts, '_materialize', original)
    source = ingest(native, recipient='visitor')
    assert source['revision'] == 1 and row(native, source['artifact_id'])['viewer'] == 'visitor'
