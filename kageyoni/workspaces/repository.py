"""Owner-authorized local candidate repair; tests bind the exact source tree.

Test code executes with the operator's OS permissions, not a security sandbox.
Only use authorized local repositories. No network/API/push integration.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork


def safe_path(root, relative):
    root=Path(root).absolute()
    require(not any(p.is_symlink() for p in (root,*root.parents)),'symlink root forbidden')
    rel=Path(relative)
    require(not rel.is_absolute() and rel.parts and '..' not in rel.parts,'unsafe relative path')
    current=root
    for part in rel.parts:
        current=current/part
        require(not current.is_symlink(),'symlinks forbidden')
    require(current.resolve().is_relative_to(root.resolve()),'path escapes root')
    return current


def tree_digest(root):
    root=Path(root)
    require(not any(p.is_symlink() for p in (root,*root.parents)),'symlink repository root forbidden')
    require(root.is_dir() and not root.is_symlink(),'repository unavailable')
    rows=[]; total=0
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(),'symlinks forbidden')
        if p.is_file():
            if '__pycache__' in p.parts or '.git' in p.parts or p.suffix=='.pyc':continue
            total+=p.stat().st_size
            require(total<=20_000_000 and len(rows)<2000,'repository exceeds bounded size')
            rows.append([p.relative_to(root).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()])
    return digest(rows)


class Repository:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def _owner(self,viewer):
        require(viewer is None,'local repository operations require owner')
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='pipeline_interface'").fetchone(),'pipeline interface not installed')
        require(not self.db.in_transaction,'local effects require standalone transaction')
    def _save(self,p):
        with UnitOfWork(self.db):self.db.execute('UPDATE repository_candidates SET payload_json=?,payload_hash=? WHERE candidate_id=?',(encoded(p),digest(p),p['candidate_id']))
    def read(self,branch,candidate_id,viewer=None):
        self._owner(viewer)
        row=self.db.execute('SELECT * FROM repository_candidates WHERE branch=? AND candidate_id=?',(branch,candidate_id)).fetchone()
        require(row is not None,'candidate unavailable');p=json.loads(row['payload_json'])
        require(digest(p)==row['payload_hash'],'candidate integrity failure');return p
    def _location(self,p):
        require(p.get('origin_database')==str(Path(self.engine.path).resolve()),'relocated repository requires explicit root rebind')
    def rebind(self,branch,candidate_id,source_dir,workspace_dir,destination=None,viewer=None):
        p=self.read(branch,candidate_id,viewer)
        require(tree_digest(source_dir)==p['source_digest'],'relocated source digest mismatch')
        require(tree_digest(workspace_dir)==p.get('candidate_digest',p['expected_candidate_digest']),'relocated candidate digest mismatch')
        if p.get('destination'):
            require(destination is not None and tree_digest(destination)==p['candidate_digest'],'relocated promoted artifact required')
        previous=dict(origin_database=p.get('origin_database'),source_dir=p['request']['source_dir'],workspace_dir=p['request']['workspace_dir'],destination=p.get('destination'))
        p['request']['source_dir']=str(Path(source_dir).absolute());p['request']['workspace_dir']=str(Path(workspace_dir).absolute())
        if destination is not None:p['destination']=str(Path(destination).absolute())
        p['origin_database']=str(Path(self.engine.path).resolve());p.setdefault('rebindings',[]).append(dict(previous=previous,current=dict(origin_database=p['origin_database'],source_dir=p['request']['source_dir'],workspace_dir=p['request']['workspace_dir'],destination=p.get('destination'))))
        self._save(p);return p
    def _qualification(self,branch,qualification_id,qualified=False):
        # Destination competence is checked by the V5 transfer registry.
        from ..intelligence.transfer import Transfers
        transfers=Transfers(self.engine);result=transfers.read(qualification_id)
        require(result.get('destination_domain')=='repository' and result.get('status') in ('candidate','qualified'),'repository destination transfer required')
        require(result.get('branch',branch)==branch,'transfer branch mismatch')
        if qualified:transfers.require_qualified(qualification_id,result['workspace_id'],'repository',viewer=None)
        return digest({key:result.get(key) for key in ('transfer_id','workspace_id','method_id','method_revision','destination_domain','mapping')})
    def prepare(self,branch,request_id,source_dir,workspace_dir,patches,test_argv,qualification_id,viewer=None):
        self._owner(viewer);self.engine.branch(branch)
        require(isinstance(request_id,str) and request_id,'request_id required')
        require(test_argv in (['python','-m','unittest'],['python','-m','unittest','discover']), 'only bounded unittest discovery supported')
        require(isinstance(patches,list) and 0<len(patches)<=30,'bounded patches required')
        payload=dict(source_dir=str(Path(source_dir).absolute()),workspace_dir=str(Path(workspace_dir).absolute()),patches=patches,test_argv=test_argv,qualification_id=qualification_id)
        old=self.db.execute('SELECT * FROM repository_candidates WHERE request_id=?',(request_id,)).fetchone()
        if old:
            require(old['branch']==branch and old['request_hash']==digest(payload),'request conflict');return self.read(branch,old['candidate_id'])
        q=self._qualification(branch,qualification_id)
        source=Path(payload['source_dir']);target=Path(payload['workspace_dir'])
        before=tree_digest(source)
        require(not any(p.is_symlink() for p in target.parents),'symlink workspace parent forbidden')
        require(not target.exists() and not target.is_symlink() and not target.resolve().is_relative_to(source.resolve()),'new separate workspace required')
        for patch in patches:
            path=safe_path(source,patch['path']);require(path.is_file(),'patch target missing')
            file_bytes=path.read_bytes()
            require(hashlib.sha256(file_bytes).hexdigest()==patch['before_sha256'] or hashlib.sha256(file_bytes.replace(b'\r\n',b'\n')).hexdigest()==patch['before_sha256'],'patch base changed')
            require(isinstance(patch['content'],str) and len(patch['content'])<1_000_000,'bounded replacement required')
            require(not Path(patch['path']).name.startswith('test') and 'tests' not in Path(patch['path']).parts,'repair cannot edit acceptance tests')
        replacements={patch['path']:hashlib.sha256(patch['content'].encode()).hexdigest() for patch in patches}
        expected=[]
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and '.git' not in path.parts and path.suffix!='.pyc':
                name=path.relative_to(source).as_posix();expected.append([name,replacements.get(name,hashlib.sha256(path.read_bytes()).hexdigest())])
        p=dict(origin_database=str(Path(self.engine.path).resolve()),expected_candidate_digest=digest(expected),candidate_id='candidate:'+uuid4().hex,branch=branch,request=payload,source_digest=before,qualification_digest=q,phase='preparing',attempts=[],candidate_digest=None)
        with UnitOfWork(self.db):self.db.execute('INSERT INTO repository_candidates VALUES(?,?,?,?,?,?)',(p['candidate_id'],branch,request_id,digest(payload),encoded(p),digest(p)))
        shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
        for patch in patches:safe_path(target,patch['path']).write_bytes(patch['content'].encode('utf-8'))
        require(tree_digest(target)==p['expected_candidate_digest'],'candidate differs from declared patch')
        p.update(phase='prepared',candidate_digest=tree_digest(target));self._save(p);return p
    def _method_effect(self,p,attempt):
        from ..intelligence.transfer import Transfers
        from ..execution.operations import pending_guards,failed_guards,run,SUPPORTED
        transfer=Transfers(self.engine).read(p['request']['qualification_id'])
        operation=transfer['operation'];definition=dict(transfer['method_guards'],operation=operation)
        result=dict(operation=operation,method_guards=transfer['method_guards'],transfer_id=transfer['transfer_id'])
        pending=pending_guards(definition)
        if pending or operation['kind'] not in SUPPORTED:
            return dict(result,phase='waiting',pending=pending,reason='method requires unresolved judgment')
        if not transfer['source_current'] or transfer['destination_domain']!='repository':
            return dict(result,phase='blocked',reason='method source or domain unavailable')
        fields=[c['field'] for c in operation['params']['criteria']] if operation['kind']=='constraint_rank' else operation['params']['fields']
        metrics=attempt.get('metrics',{})
        if not set(fields)<=set(metrics):return dict(result,phase='waiting',reason='unsupported destination metric',missing_fields=sorted(set(fields)-set(metrics)))
        evidence=dict(candidate_id=p['candidate_id'],tested_digest=attempt['tested_digest'],attempt=attempt['number'],metrics_digest=digest(metrics))
        candidates=[dict(id=p['candidate_id'],claims={field:dict(value=metrics[field],support='matched',evidence=[dict(evidence,field=field)]) for field in fields},counterclaims={})]
        failures=failed_guards(definition,candidates)
        if failures:return dict(result,phase='blocked',failed_guards=failures)
        executed=run(operation,candidates)
        return dict(result,phase=executed['phase'],inputs=candidates,result=executed,scope='executed test metrics only')
    def check(self,branch,candidate_id,timeout_seconds=30,viewer=None):
        p=self.read(branch,candidate_id,viewer);self._location(p);require(0<timeout_seconds<=60,'timeout out of range')
        require(p['phase'] in ('prepared','failed','checked'),'candidate requires preparation/reconciliation')
        require(self._qualification(branch,p['request']['qualification_id'])==p['qualification_digest'],'qualification changed')
        root=Path(p['request']['workspace_dir']);before=tree_digest(root)
        require(before==p['candidate_digest'],'candidate changed before test')
        attempt=dict(number=len(p['attempts'])+1,phase='running',tested_digest=before)
        p['attempts'].append(attempt);p['phase']='testing';self._save(p)
        try:
            with tempfile.TemporaryFile() as capture:
                result=subprocess.run([sys.executable,'-B','-m','unittest','discover'],cwd=root,stdout=capture,stderr=subprocess.STDOUT,timeout=timeout_seconds,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                capture.seek(0,2);capture.seek(max(0,capture.tell()-50000));output=capture.read().decode('utf-8','replace')
            code=result.returncode
            # unittest returns success on zero tests; that is not acceptance evidence.
            import re
            count=re.search(r'Ran (\d+) tests?',output)
            passed=code==0 and count is not None and int(count.group(1))>0
            attempt.update(returncode=code,output=output,tests=int(count.group(1)) if count else 0)
        except subprocess.TimeoutExpired as error:
            passed=False;attempt.update(returncode=None,output=str(error.output)[-50000:],reason='timeout')
        after=tree_digest(root);passed=passed and before==after
        if attempt.get('tests') is not None:
            import re
            issues=sum(int(n) for n in re.findall(r'(?:failures|errors)=(\d+)',attempt.get('output','')))
            skipped=sum(int(n) for n in re.findall(r'skipped=(\d+)',attempt.get('output','')))
            attempt['metrics']=dict(tests=attempt['tests'],checks=max(0,attempt['tests']-issues-skipped) if attempt.get('returncode')==0 else 0,failures=issues)
        attempt['method_effect']=self._method_effect(p,attempt)
        passed=passed and attempt['method_effect']['phase']=='completed'
        attempt.update(phase='completed' if passed else 'failed',after_digest=after)
        p['phase']='checked' if passed else 'failed';self._save(p);return p
    def validate_trial(self,branch,report):
        require(isinstance(report,dict),'trial report required')
        row=self.db.execute('SELECT payload_json,payload_hash FROM repository_candidates WHERE branch=? AND candidate_id=?',(branch,report.get('candidate_id'))).fetchone()
        require(row is not None,'executed repository trial required')
        p=json.loads(row['payload_json']);require(digest(p)==row['payload_hash'],'candidate integrity failure')
        self._location(p)
        require(p['phase'] in ('checked','promoted') and p['attempts'] and p['attempts'][-1]['phase']=='completed','passed executed repository check required')
        require(p['attempts'][-1].get('method_effect',{}).get('phase')=='completed','executed mapped method required')
        require(p['request']['qualification_id']==report.get('transfer_id') and report.get('destination_domain')=='repository','repository trial scope mismatch')
        require(report.get('candidate_digest')==p['candidate_digest'] and report.get('check_digest')==digest(p['attempts'][-1]),'repository trial receipt mismatch')
        require(report.get('method_effect')==p['attempts'][-1]['method_effect'],'trial mapped method effect mismatch')
        require(tree_digest(p['request']['workspace_dir'])==p['candidate_digest'],'checked repository has changed')
        require(report.get('checks')==[dict(name='exact_candidate_unittest',passed=True)],'repository check declaration mismatch')
        return dict(candidate_id=p['candidate_id'],candidate_digest=p['candidate_digest'],check_digest=report['check_digest'])
    def trial_artifact(self,branch,candidate_id,request_id,viewer=None):
        p=self.read(branch,candidate_id,viewer)
        self._location(p)
        require(p['phase']=='checked' and tree_digest(p['request']['workspace_dir'])==p['candidate_digest'],'checked unchanged candidate required')
        from ..intelligence.transfer import Transfers
        from ..persistence.artifacts import Artifacts
        transfer=Transfers(self.engine).read(p['request']['qualification_id'])
        content=dict(transfer_id=transfer['transfer_id'],destination_domain='repository',candidate_id=candidate_id,candidate_digest=p['candidate_digest'],check_digest=digest(p['attempts'][-1]),method_effect=p['attempts'][-1]['method_effect'],checks=[dict(name='exact_candidate_unittest',passed=True)])
        artifact=Artifacts(self.engine).put(encoded(content),'application/json',request_id,workspace_id=transfer['workspace_id'])
        return dict(artifact=artifact,checks=content['checks'])
    def _qualified_candidate(self,p):
        from ..intelligence.transfer import Transfers
        from ..persistence.artifacts import Artifacts
        transfer=Transfers(self.engine).read(p['request']['qualification_id'])
        trial=transfer.get('latest_trial') or {}
        artifact=Artifacts(self.engine).read(trial.get('artifact_id'))
        content=json.loads(artifact['content'])
        require(content.get('candidate_id')==p['candidate_id'] and content.get('candidate_digest')==p['candidate_digest'] and content.get('check_digest')==digest(p['attempts'][-1]),'qualification trial does not bind this checked candidate')
    def promote(self,branch,candidate_id,destination,viewer=None):
        p=self.read(branch,candidate_id,viewer)
        self._location(p)
        require(p['phase']=='checked','exact candidate must pass checks')
        require(self._qualification(branch,p['request']['qualification_id'],qualified=True)==p['qualification_digest'],'qualification changed')
        self._qualified_candidate(p)
        source=Path(p['request']['workspace_dir']);dest=Path(destination).absolute()
        require(tree_digest(source)==p['candidate_digest'],'tested artifact changed')
        require(not any(p.is_symlink() for p in dest.parents),'symlink destination parent forbidden')
        require(not dest.exists() and not dest.is_symlink(),'promotion destination must be new')
        p.update(phase='promoting',destination=str(dest));self._save(p)
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        require(tree_digest(dest)==p['candidate_digest'],'promoted artifact mismatch')
        p['phase']='promoted';p['promoted_digest']=p['candidate_digest'];self._save(p);return p
    def reconcile(self,branch,candidate_id,viewer=None):
        p=self.read(branch,candidate_id,viewer)
        self._location(p)
        if p['phase']=='preparing':
            target=Path(p['request']['workspace_dir'])
            if target.is_dir() and tree_digest(target)==p['expected_candidate_digest']:
                p.update(phase='prepared',candidate_digest=p['expected_candidate_digest'])
            else:p.update(phase='blocked',resume_condition='Partial preparation retained. Inspect workspace; create a new request with a new destination to retry.')
            self._save(p)
        elif p['phase']=='promoting':
            require(tree_digest(p['destination'])==p['candidate_digest'],'promotion incomplete; manual recovery required')
            p.update(phase='promoted',promoted_digest=p['candidate_digest']);self._save(p)
        elif p['phase']=='testing':
            p['phase']='failed';p['attempts'][-1].update(phase='failed',reason='interrupted; explicit retry required');self._save(p)
        return p
