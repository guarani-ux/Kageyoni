"""Actual native private source inquiry/draft audience and budget controls."""
import pytest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.documents import Documents
from test_artifact_recipients import native, ingest, row


def citation(source):
    return {k: source[k] for k in ('source_id', 'revision', 'digest')} | {'start': 0, 'end': 5}


def brief(source):
    return dict(brief_id='private-test',title='Bounded scaffold',audience='Recipient',purpose='Provenance only',
        sections=[dict(id='one',heading='Captured statement',field='statement',claims=[citation(source)])])


def ask(n, request='ask', recipient=None, source=None, viewer=None, workspace=None):
    return n['documents'].inquire(workspace or n['shared'],request,'What is supported?', ['statement'],
        [{'field':'statement','evidence':citation(source)}] if source else [],viewer=viewer,recipient=recipient)


def counts(n):
    return tuple(n['engine'].db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                 for table in ('artifacts','document_sources','document_inquiries','document_drafts'))


def test_default_public_payload_result_and_exact_none_retry(native):
    source=ingest(native)
    result=ask(native,source=source)
    assert 'audience' not in result
    saved=native['engine'].db.execute('SELECT payload_hash,result_json FROM document_inquiries WHERE request_id=?',('ask',)).fetchone()
    payload=dict(workspace_id=native['shared'],question='What is supported?',required_fields=['statement'],
        claims=[{'field':'statement','evidence':citation(source)}],counters=[],viewer=None)
    assert saved['payload_hash']==digest(payload)
    assert ask(native,source=source,recipient=None)==result
    b=brief(source); draft=native['documents'].draft(native['shared'],'draft',b)
    assert row(native,draft['artifact']['artifact_id'])['viewer'] is None
    stored=native['engine'].db.execute('SELECT payload_hash FROM document_drafts WHERE request_id=?',('draft',)).fetchone()[0]
    assert stored==digest(dict(workspace_id=native['shared'],brief=b,viewer=None,transfer_trial_id=None))
    assert native['documents'].draft(native['shared'],'draft',b,recipient=None)['text']==draft['text']


@pytest.mark.parametrize('recipient',['visitor','keeper'])
def test_owner_private_native_passages_scaffold_and_retry(native,recipient):
    source=ingest(native,recipient=recipient)
    result=ask(native,recipient=recipient,source=source)
    assert result['audience']==recipient and result['fields']['statement']['supports'][0]['text']=='Exact'
    assert ask(native,recipient=recipient,source=source)==result
    d=native['documents'].draft(native['shared'],'draft',brief(source),recipient=recipient)
    assert row(native,d['artifact']['artifact_id'])['viewer']==recipient
    assert '> Exact' in d['text']
    assert native['documents'].read(d['draft_id'])['text']==d['text']
    assert native['documents'].draft(native['shared'],'draft',brief(source),recipient=recipient)['draft_id']==d['draft_id']
    for foreign in (None, 'keeper' if recipient=='visitor' else 'visitor'):
        before=counts(native)
        with pytest.raises(Rejected,match='inquiry request conflict'):ask(native,recipient=foreign,source=source)
        with pytest.raises(Rejected,match='draft request conflict'):
            native['documents'].draft(native['shared'],'draft',brief(source),recipient=foreign)
        assert counts(native)==before


@pytest.mark.parametrize('recipient',[None,'keeper'])
@pytest.mark.parametrize('operation',['inquiry','draft','obligation'])
def test_private_passage_cannot_emit_into_public_or_foreign_lane(native,recipient,operation):
    source=ingest(native,recipient='visitor'); before=counts(native)
    with pytest.raises(Rejected,match='source audience unavailable'):
        if operation=='inquiry':ask(native,recipient=recipient,source=source)
        else:
            b=brief(source)
            if operation=='obligation':
                b['sections'][0]['claims']=[]
                b['obligations']=[dict(id='keep',status='required',evidence=citation(source))]
            native['documents'].draft(native['shared'],'draft',b,recipient=recipient)
    assert counts(native)==before


@pytest.mark.parametrize('recipient',['', ' ', False, 9, [], {}, 'x'*1025])
def test_invalid_recipient_never_creates_inquiry_draft_or_artifact(native,recipient):
    source=ingest(native); before=counts(native)
    with pytest.raises(Rejected):ask(native,recipient=recipient,source=source)
    with pytest.raises(Rejected):native['documents'].draft(native['shared'],'draft',brief(source),recipient=recipient)
    assert counts(native)==before


def test_nonowner_only_same_recipient_in_its_authorized_workspace(native):
    source=ingest(native,workspace=native['visitor'],viewer='visitor',recipient='visitor')
    assert ask(native,workspace=native['visitor'],viewer='visitor',recipient='visitor',source=source)['audience']=='visitor'
    d=native['documents'].draft(native['visitor'],'draft',brief(source),viewer='visitor',recipient='visitor')
    assert row(native,d['artifact']['artifact_id'])['viewer']=='visitor'
    before=counts(native)
    for workspace,recipient in ((native['visitor'],'keeper'),(native['shared'],'visitor'),(native['keeper'],'visitor')):
        with pytest.raises(Rejected):ask(native,'foreign-'+workspace,workspace=workspace,viewer='visitor',recipient=recipient)
        with pytest.raises(Rejected):native['documents'].draft(workspace,'foreign-'+workspace,brief(source),viewer='visitor',recipient=recipient)
    assert counts(native)==before
    with pytest.raises(Rejected):native['documents'].read(d['draft_id'],viewer='keeper')


def test_each_audience_budget_independent_and_fourth_own_blocks(native,tmp_path):
    for recipient in ('visitor',None,'keeper'):
        for attempt in range(1,5):
            r=ask(native,str(recipient)+'-'+str(attempt),recipient=recipient)
            assert r['attempt']==attempt
            assert (r['phase']=='blocked')==(attempt==4)
    source=ingest(native,recipient='visitor')
    private_draft=native['documents'].draft(native['shared'],'before-backup',brief(source),recipient='visitor')
    backup=tmp_path/'backup.sqlite'; native['engine'].backup(backup)
    restored=Engine.restore(backup,tmp_path/'restored.sqlite'); assert restored['verification']['ok']
    reopened=Engine(tmp_path/'restored.sqlite')
    try:
        docs=Documents(reopened)
        assert docs.read(private_draft['draft_id'])['text']==private_draft['text']
        assert docs.source(native['shared'],source['source_id'])['digest']==source['digest']
        assert reopened.db.execute('SELECT viewer FROM artifacts WHERE artifact_id=?',(private_draft['artifact']['artifact_id'],)).fetchone()[0]=='visitor'
        for recipient in (None,'visitor','keeper'):
            r=docs.inquire(native['shared'],'after-'+str(recipient),'What is supported?',['statement'],[],recipient=recipient)
            assert r['attempt']==5 and r['phase']=='blocked'
        assert reopened.verify()['ok'] and reopened.validate_registry()['ok']
    finally:
        reopened.close()


def test_nested_outer_rollback_leaves_no_private_inquiry_draft_artifact(native):
    source=ingest(native,recipient='visitor'); before=counts(native)
    with pytest.raises(RuntimeError,match='outer interruption'):
        with UnitOfWork(native['engine'].db):
            ask(native,recipient='visitor',source=source)
            native['documents'].draft(native['shared'],'draft',brief(source),recipient='visitor')
            raise RuntimeError('outer interruption')
    assert counts(native)==before
    assert ask(native,recipient='visitor',source=source)['attempt']==1
    assert native['documents'].draft(native['shared'],'draft',brief(source),recipient='visitor')['text']


def test_historical_unmarked_inquiry_remains_default_not_inferred_private(native):
    # Genuine old-format public result has no marker. New private lane must not
    # retrospectively relabel it, even with identical question wording.
    old=ask(native,'historical')
    before=native['engine'].db.execute('SELECT result_json FROM document_inquiries WHERE request_id=?',('historical',)).fetchone()[0]
    assert 'audience' not in old
    assert ask(native,'new-private',recipient='visitor')['attempt']==1
    assert ask(native,'new-public')['attempt']==2
    assert native['engine'].db.execute('SELECT result_json FROM document_inquiries WHERE request_id=?',('historical',)).fetchone()[0]==before


def test_actor_authorized_workspace_still_cannot_read_other_audience_draft(native):
    source=ingest(native,workspace=native['visitor'])
    d=native['documents'].draft(native['visitor'],'draft',brief(source),recipient='keeper')
    before=counts(native)
    with pytest.raises(Rejected,match='artifact unavailable'):
        native['documents'].read(d['draft_id'],viewer='visitor')
    assert counts(native)==before
    assert native['documents'].read(d['draft_id'])['text']==d['text']


def test_unknown_or_foreign_workspace_passage_rejected_without_native_writes(native):
    foreign=ingest(native,workspace=native['keeper'],recipient='keeper')
    before=counts(native)
    for source in (foreign, dict(source_id='absent',revision=1,digest='0'*64)):
        with pytest.raises(Rejected):ask(native,recipient='visitor',source=source)
        with pytest.raises(Rejected):native['documents'].draft(native['shared'],'missing',brief(source),recipient='visitor')
    assert counts(native)==before
