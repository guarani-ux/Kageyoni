"""Portable standard-library terminal menus for the bundled Kageyoni v8 engine."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid

from kageyoni.engine import Engine, Rejected
from kageyoni.model import DOMAINS, REQUIRED
from kageyoni import characters

ROOT = Path(__file__).resolve().parent

def safe(value):
    # Never execute terminal control sequences contained in story text.
    return ''.join(c if c in '\n\t' or (ord(c) >= 32 and not 127 <= ord(c) <= 159) else '?' for c in str(value))

def pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str)

def atomic_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.settings-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(pretty(data) + '\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def clone_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file(): raise ValueError('Source database does not exist.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents overwriting an existing save.
    with destination.open('xb'): pass
    try:
        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        try:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'schema_version', 'branches', 'events'} <= tables:
                raise ValueError('Not a Kageyoni database.')
            dst = sqlite3.connect(destination)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination

class Session:
    def __init__(self, path, branch='main', viewer=None):
        self.path = Path(path).resolve()
        if not self.path.is_file(): raise ValueError('Database missing. Import a copy first.')
        self.recovery = self.path.parent / 'backups' / ('before-open-' + uuid.uuid4().hex + '.sqlite')
        clone_database(self.path, self.recovery)  # Engine opening may migrate old databases.
        self.engine = Engine(self.path)
        try:
            self.engine.branch(branch)
            if not self.engine.verify()['ok']: raise ValueError('Verification failed.')
            self.engine.context(branch, viewer=viewer)
        except Exception:
            self.engine.close(); raise
        self.branch, self.viewer, self.pending = branch, viewer, None

    def close(self): self.engine.close()
    def owner(self):
        if self.viewer is not None: raise Rejected('Switch to owner view to author or inspect private history.')
    def records(self, domain=None):
        return self.engine.context(self.branch, domain=domain, viewer=self.viewer)['records']
    def stage(self, command):
        self.owner(); self.pending = None
        if command.get('branch') != self.branch: raise Rejected('Command must target the selected branch.')
        frozen = copy.deepcopy(command)
        result = self.engine.apply(frozen, preview=True)
        self.pending = frozen
        return result
    def commit(self):
        self.owner()
        if self.pending is None: raise Rejected('No validated preview.')
        command = copy.deepcopy(self.pending)
        self.engine.backup(self.path.parent / 'backups' / ('before-commit-' + uuid.uuid4().hex + '.sqlite'))
        result = self.engine.apply(command)
        self.pending = None
        return result
    def patch(self, rid, field, value, note):
        self.owner()
        record = self.engine.get(self.branch, rid)
        if record is None: raise ValueError('Unknown record.')
        if field not in DOMAINS[record['domain']]: raise ValueError('Unknown schema field.')
        return dict(api_version=3, branch=self.branch, expected_revision=self.engine.branch(self.branch)['revision'],
                    request_id='terminal:' + uuid.uuid4().hex, kind='maintenance', actor='gm', narrative=note,
                    changes=[dict(op='patch', id=rid, expected_version=record['version'], data={field:value},
                                  evidence=[{'note':note}])])

def parse_value(raw, kind):
    if kind in ('json','number','integer'):
        value = json.loads(raw)
        if kind == 'integer' and type(value) is not int: raise ValueError('An integer is required.')
        if kind == 'number' and (type(value) not in (int,float) or not math.isfinite(value)):
            raise ValueError('A finite number is required.')
        return value
    if kind.startswith('enum:') and raw not in kind[5:].split('|'): raise ValueError('Choose one of the listed values.')
    return raw

class App:
    def __init__(self, data, db=None):
        self.data = Path(data).resolve(); self.data.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data / 'settings.json'
        self.settings = {'page_size':20, 'last_db':None, 'branch':'main'}
        if self.settings_path.exists():
            loaded = json.loads(self.settings_path.read_text(encoding='utf-8'))
            if not isinstance(loaded, dict): raise ValueError('Settings must be an object.')
            self.settings.update({k:v for k,v in loaded.items() if k in self.settings})
        if type(self.settings['page_size']) is not int or not 5 <= self.settings['page_size'] <= 100:
            raise ValueError('page_size must be an integer from 5 to 100.')
        self.session = None
        if db: self.open(db)
    def say(self, text): print(safe(text))
    def ask(self, text): return input(safe(text + ': ')).strip()
    def choose(self, title, options):
        self.say('\n' + title)
        for i, label in enumerate(options,1): self.say(f'  {i}. {label}')
        self.say('  0. Back / cancel')
        answer = self.ask('Select')
        if answer in ('0',''): return None
        if not answer.isdigit() or not 1 <= int(answer) <= len(options): raise ValueError('Choose a listed number.')
        return int(answer)-1
    def show(self, value):
        lines = safe(pretty(value)).splitlines(); size = self.settings['page_size']
        for start in range(0,len(lines),size):
            print('\n'.join(lines[start:start+size]))
            if start+size < len(lines) and self.ask('Enter for more; q to stop').lower() == 'q': break
    def open(self, path):
        candidate = Session(path)
        if self.session: self.session.close()
        self.session = candidate
        self.settings.update(last_db=str(candidate.path),branch='main'); atomic_json(self.settings_path,self.settings)
    def pick_record(self, domain=None):
        records = self.session.records(domain)
        query = self.ask('Search name or ID (blank lists all)').casefold()
        records = [r for r in records if query in (r['id']+' '+str(r['data'].get('name',''))).casefold()]
        size=self.settings['page_size']; offset=0
        while records:
            page=records[offset:offset+size]
            labels=[r['id']+' — '+str(r['data'].get('name',r['domain'])) for r in page]
            if offset+size<len(records): labels.append('Next page')
            if offset: labels.append('Previous page')
            choice=self.choose('Records',labels)
            if choice is None:return None
            if choice<len(page):return page[choice]
            if labels[choice]=='Next page':offset+=size
            else:offset-=size
        self.say('No matching records.'); return None
    def workspace(self):
        i=self.choose('Workspace',[ 'Open existing working database','Import database into a new working copy',
                                    'Start a copy of the bundled revision-60 checkpoint','Switch branch',
                                    'Document, repository and pipeline workspaces'])
        if i==0:self.open(Path(self.ask('Database path')).expanduser())
        elif i in (1,2):
            source=ROOT/'build/kageyoni.sqlite' if i==2 else Path(self.ask('Source database path')).expanduser()
            if i==2:self.say('This is the packaged revision-60 checkpoint. Import your newer save if play has continued.')
            target=self.data/('world-'+uuid.uuid4().hex[:10]+'.sqlite')
            clone_database(source,target); self.open(target); self.say('Opened working copy: '+str(target))
        elif i==3 and self.session:
            self.session.owner()
            branches=[r['id'] for r in self.session.engine.db.execute('SELECT id FROM branches ORDER BY id')]
            choice=self.choose('Branch',branches)
            if choice is not None:
                self.session.branch=branches[choice]; self.session.pending=None
        elif i==4:
            if self.session:self.daily()
            else:self.say('Open a working database first.')
    def character(self):
        r=self.pick_record('character')
        if r:self.show(characters.read(self.session.engine,self.session.branch,r['id'],viewer=self.session.viewer))
    def nodes(self):
        from kageyoni.application import Application
        s=self.session
        installed=s.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='node_interface'").fetchone()
        if not installed:
            s.owner()
            self.say('Adds persistent node tables; retains the world and creates a recovery copy.')
            if self.ask('Type INSTALL to initialize nodes')!='INSTALL':return
        app=Application(s.engine,migrate=not bool(installed))
        choice=self.choose('Persistent nodes',['List visible nodes','Read a character node','Bind an existing character'])
        if choice==0:self.show(app.nodes.list(s.branch,viewer=s.viewer))
        elif choice in (1,2):
            if choice==2:s.owner()
            r=self.pick_record('character')
            if not r:return
            if choice==2:
                note=self.ask('Source note for this identity link')
                self.show(app.nodes.bind(s.branch,r['id'],'terminal-node:'+uuid.uuid4().hex,
                    s.engine.branch(s.branch)['revision'],{'note':note},viewer=s.viewer))
            else:self.show(app.nodes.read(s.branch,r['id'],viewer=s.viewer))
    def methods(self):
        from kageyoni.application import Application
        s=self.session
        installed=s.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='contribution_interface'").fetchone()
        if not installed:
            s.owner()
            self.say('Initialize method and contribution storage with a recovery copy.')
            if self.ask('Type INSTALL to initialize methods')!='INSTALL':return
        app=Application(s.engine,migrate_methods=not bool(installed))
        choice=self.choose('Methods and contributions',[
            'List character methods','Read method revision','Register method from JSON',
            'Revise method from JSON','Assign method from JSON','Prepare task from JSON',
            'Run task and save contribution','List contributions','Read contribution'])
        if choice is None:return
        if choice==7:
            self.show(app.contributions.list(s.branch,viewer=s.viewer));return
        if choice==8:
            self.show(app.contributions.read(s.branch,self.ask('Contribution ID'),viewer=s.viewer));return
        r=self.pick_record('character')
        if not r:return
        node=app.nodes.read(s.branch,r['id'],viewer=s.viewer)
        if choice==0:
            self.show(app.methods.list(s.branch,r['id'],viewer=s.viewer));return
        if choice==1:
            mid=self.ask('Method ID');revision=self.ask('Revision (blank for latest)')
            self.show(app.methods.read(s.branch,mid,method_revision=int(revision) if revision else None,viewer=s.viewer));return
        if choice in (2,3,4):s.owner()
        payload=json.loads(Path(self.ask('JSON input file path')).expanduser().read_text(encoding='utf-8'))
        if not isinstance(payload,dict):raise ValueError('Input must be a JSON object.')
        if choice in (2,3,4):
            payload.update(branch=s.branch,node_id=node['node_id'],viewer=s.viewer)
            self.show(getattr(app.methods,{2:'create',3:'revise',4:'assign'}[choice])(**payload))
        elif choice==5:
            self.show(app.expression.prepare(s.branch,r['id'],payload,viewer=s.viewer))
        elif choice==6:
            self.show(app.contributions.run(s.branch,r['id'],'terminal-contribution:'+uuid.uuid4().hex,payload,viewer=s.viewer))
    def learning(self):
        from kageyoni.application import Application
        s=self.session
        installed=s.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='learning_interface'").fetchone()
        if not installed:
            s.owner()
            self.say('Initialize outcome and lesson storage with a recovery copy.')
            if self.ask('Type INSTALL to initialize learning')!='INSTALL':return
        app=Application(s.engine,migrate_learning=not bool(installed))
        choice=self.choose('Outcomes and lessons',[
            'List character outcomes','Read outcome','Record outcome from JSON',
            'List character lessons','Read lesson','Propose lesson from JSON',
            'Revise lesson from JSON','Review or contest lesson from JSON'])
        if choice is None:return
        if choice==1:
            self.show(app.learning.read_outcome(s.branch,self.ask('Outcome ID'),viewer=s.viewer));return
        if choice==4:
            lesson_id=self.ask('Lesson ID');revision=self.ask('Revision (blank for latest)')
            self.show(app.learning.read(s.branch,lesson_id,lesson_revision=int(revision) if revision else None,viewer=s.viewer));return
        if choice in (0,3):
            record=self.pick_record('character')
            if record:self.show(getattr(app.learning,'list_outcomes' if choice==0 else 'list')(s.branch,record['id'],viewer=s.viewer))
            return
        s.owner()
        payload=json.loads(Path(self.ask('JSON input file path')).expanduser().read_text(encoding='utf-8'))
        if not isinstance(payload,dict):raise ValueError('Input must be a JSON object.')
        payload.update(branch=s.branch,viewer=s.viewer)
        operation={2:'record_outcome',5:'propose',6:'revise',7:'review'}[choice]
        self.show(getattr(app.learning,operation)(**payload))
    def daily(self):
        from kageyoni.application import Application
        from kageyoni.console import menu
        s=self.session
        s.owner()
        installed=s.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='operations_interface'").fetchone()
        if not installed:
            self.say('Initialize the remaining engine workspaces with recovery copies.')
            if self.ask('Type INSTALL to initialize all interfaces')!='INSTALL':return
            Application(s.engine,migrate_all=True)
        menu(s.engine)
    def inspect(self):
        r=self.pick_record()
        if r:self.show(r)
    def edit(self):
        s=self.session; s.owner(); r=self.pick_record()
        if not r:return
        fields=list(DOMAINS[r['domain']])
        choice=self.choose('Edit field',[f'{f} ({DOMAINS[r["domain"]][f]})' for f in fields])
        if choice is None:return
        field=fields[choice]; kind=DOMAINS[r['domain']][field]
        self.show({'current':r['data'].get(field),'type':kind})
        value=parse_value(self.ask('New value (JSON for structured/numeric fields)'),kind)
        note=self.ask('Reason / source for this administrative edit')
        if not note:raise ValueError('A reason is required.')
        command=s.patch(r['id'],field,value,note)
        self.show({'before':r['data'].get(field),'after':value,'command':command})
        self.show(s.stage(command)); self.say('Validated preview only. Use Commit to save.')
    def import_command(self):
        self.session.owner()
        path=Path(self.ask('Engine event-command JSON path')).expanduser()
        command=json.loads(path.read_text(encoding='utf-8'))
        self.show(command); self.show(self.session.stage(command))
        self.say('Preview only; semantic correctness remains your responsibility.')
    def commit(self):
        s=self.session; s.owner()
        if s.pending is None:raise ValueError('No pending preview.')
        self.show(s.pending)
        if self.ask('Type COMMIT to save this exact change')=='COMMIT':self.show(s.commit())
        else:self.say('Not committed. Preview remains available.')
    def history(self):
        self.session.owner()
        self.show([dict(r) for r in self.session.engine.causal_history(self.session.branch)])
    def settings_menu(self):
        i=self.choose('Settings',['Page size','Perspective: owner or character','AI connection status'])
        if i==0:
            size=int(self.ask('Lines per page (5–100)'))
            if not 5<=size<=100:raise ValueError('Use 5–100.')
            self.settings['page_size']=size; atomic_json(self.settings_path,self.settings)
        elif i==1 and self.session:
            viewer=self.ask('Character ID, or blank for owner') or None
            self.session.engine.context(self.session.branch,viewer=viewer)
            self.session.viewer=viewer; self.session.pending=None
            self.say('Perspective is a display filter, not account authentication.')
        elif i==2:self.say('No AI provider connected. No API keys or paid calls. Use your authorized AI tool to prepare engine commands, then import and review them here.')
    def export(self):
        destination=Path(self.ask('New JSON destination')).expanduser()
        data=self.session.engine.context(self.session.branch,viewer=self.session.viewer)
        with destination.open('x',encoding='utf-8') as f:f.write(pretty(data)+'\n')
        self.say('Context exported with the selected perspective.')
    def backup(self):
        self.session.owner()
        self.show({'backup':self.session.engine.backup(Path(self.ask('New backup path')).expanduser())})
    def run(self):
        try:
            while True:
                s=self.session
                title='KAGEYONI TERMINAL — '+(f'{s.path.name} / {s.branch} / {s.viewer or "owner"} / revision {s.engine.branch(s.branch)["revision"]}' if s else 'No workspace open')
                actions=[('Workspace',self.workspace),('Characters',self.character),('Inspect records',self.inspect),
                         ('Edit a record field',self.edit),('Preview imported event command',self.import_command),
                         ('Commit preview',self.commit),('Discard preview',lambda:setattr(self.session,'pending',None)),
                         ('History (owner)',self.history),('Verify database',lambda:self.show(self.session.engine.verify())),
                         ('Export current context',self.export),('Backup',self.backup),('Settings',self.settings_menu),('Persistent nodes',self.nodes),('Methods and contributions',self.methods),('Outcomes and lessons',self.learning),('Engine workspaces and daily operation',self.daily)]
                try:
                    choice=self.choose(title,[x[0] for x in actions])
                    if choice is None:break
                    if not s and choice not in (0,11):self.say('Open a workspace first.');continue
                    actions[choice][1]()
                except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as exc:self.say('Could not complete: '+str(exc))
        except (EOFError,KeyboardInterrupt):self.say('\nClosed. Uncommitted previews were discarded.')
        finally:
            if self.session:self.session.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',help='Existing database to open; automatically backed up before opening')
    parser.add_argument('--data-dir',default=str(ROOT/'terminal-data'),help='Settings and imported working databases')
    args=parser.parse_args()
    try:App(args.data_dir,args.db).run()
    except (ValueError,OSError,sqlite3.Error) as exc:parser.exit(2,'Could not start: '+str(exc)+'\n')

if __name__=='__main__':main()
