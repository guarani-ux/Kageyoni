from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
from ..engine import encoded, require

DATA = Path(__file__).with_name('data')


def _sha(value: Any) -> tuple[str, str]:
    body = encoded(value)
    return body, hashlib.sha256(body.encode()).hexdigest()


class CompositionRegistry:
    """Persistent self-description for Frames, Aspect types, and authored Aspects.

    The registry is intentionally declarative. It does not resolve simulation
    outcomes; it tells the compiler what kinds of things exist and how they may
    participate. Unknown definitions fail closed instead of being coerced.
    """
    def __init__(self, engine):
        self.engine = engine
        self.db = engine.db

    @staticmethod
    def builtin_frames():
        out = []
        for p in sorted(DATA.glob('*.json')):
            data = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('frame_id'):
                out.append(data)
        return out

    @staticmethod
    def builtin_types():
        path = DATA / 'aspect_types.json'
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        require(isinstance(data, list), 'aspect_types.json must contain a list')
        return data

    def install_builtins(self):
        for item in self.builtin_types():
            require(item.get('type_id') and item.get('family') and item.get('purpose_type'), 'invalid built-in aspect type')
            body, h = _sha(item)
            self.db.execute(
                """INSERT INTO composition_types(type_id,family,purpose_type,short_description,definition_json,source_hash,status)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(type_id) DO UPDATE SET
                family=excluded.family,purpose_type=excluded.purpose_type,
                short_description=excluded.short_description,definition_json=excluded.definition_json,
                source_hash=excluded.source_hash,status=excluded.status""",
                (item['type_id'], item['family'], item['purpose_type'], item.get('short_description',''), body, h, item.get('status','active')),
            )
        for frame in self.builtin_frames():
            body, h = _sha(frame)
            self.db.execute(
                """INSERT INTO composition_frames(frame_id,version,status,definition_json,source_hash)
                VALUES(?,?,?,?,?) ON CONFLICT(frame_id,version) DO UPDATE SET
                status=excluded.status,definition_json=excluded.definition_json,source_hash=excluded.source_hash""",
                (frame['frame_id'], str(frame.get('version','1')), 'active', body, h),
            )
        return {'types': self.list_types(), 'frames': self.list_frames()}

    def list_frames(self):
        return [dict(r) for r in self.db.execute(
            'SELECT frame_id,version,status,source_hash FROM composition_frames ORDER BY frame_id,version'
        )]

    def frame(self, frame_id, version=None):
        if version is None:
            row = self.db.execute(
                "SELECT definition_json FROM composition_frames WHERE frame_id=? AND status='active' "
                "ORDER BY CAST(version AS INTEGER) DESC LIMIT 1", (frame_id,)
            ).fetchone()
        else:
            row = self.db.execute(
                'SELECT definition_json FROM composition_frames WHERE frame_id=? AND version=?',
                (frame_id, str(version)),
            ).fetchone()
        require(row is not None, 'unknown composition frame')
        return json.loads(row[0])

    def list_types(self, family=None):
        if family is None:
            rows = self.db.execute(
                'SELECT type_id,family,purpose_type,short_description,status,source_hash FROM composition_types ORDER BY family,type_id'
            )
        else:
            rows = self.db.execute(
                'SELECT type_id,family,purpose_type,short_description,status,source_hash FROM composition_types WHERE family=? ORDER BY type_id',
                (family,),
            )
        return [dict(r) for r in rows]

    def type(self, type_id):
        row = self.db.execute('SELECT definition_json FROM composition_types WHERE type_id=?', (type_id,)).fetchone()
        require(row is not None, 'unknown composition type')
        return json.loads(row[0])

    def register_aspect(self, definition: dict[str, Any], *, declared_by='owner'):
        require(isinstance(definition, dict), 'aspect definition must be an object')
        aspect_id = definition.get('aspect_id')
        type_id = definition.get('type') or definition.get('type_id')
        require(isinstance(aspect_id, str) and aspect_id.strip(), 'aspect_id required')
        require(isinstance(type_id, str) and type_id.strip(), 'aspect type required')
        type_def = self.type(type_id)
        family = definition.get('family', type_def['family'])
        require(family == type_def['family'], 'aspect family does not match registered type')
        purpose = definition.get('purpose_type', type_def.get('purpose_type', family))
        compatible = definition.get('compatible_slots', [])
        require(isinstance(compatible, list), 'compatible_slots must be a list')
        require(isinstance(definition.get('effects', []), list), 'effects must be a list')
        latest = self.db.execute('SELECT MAX(version) FROM composition_aspects WHERE aspect_id=?', (aspect_id,)).fetchone()[0]
        raw_version=definition.get('version')
        require(raw_version is None or (type(raw_version) is int and raw_version>0),'aspect version must be a positive integer')
        version = raw_version if raw_version is not None else ((latest or 0) + 1)
        require(type(version) is int and version > 0, 'aspect version must be positive')
        body_def = dict(definition)
        body_def.update({'aspect_id': aspect_id, 'type': type_id, 'family': family, 'purpose_type': purpose, 'version': version})
        body, h = _sha(body_def)
        self.db.execute(
            """INSERT INTO composition_aspects(aspect_id,version,family,type_id,purpose_type,status,definition_json,source_hash,declared_by)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (aspect_id, version, family, type_id, purpose, body_def.get('status','active'), body, h, declared_by),
        )
        return self.aspect(aspect_id, version)

    def list_aspects(self, *, family=None, status='active'):
        clauses=[]; params=[]
        if family is not None: clauses.append('family=?'); params.append(family)
        if status is not None: clauses.append('status=?'); params.append(status)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = self.db.execute(
            'SELECT aspect_id,version,family,type_id,purpose_type,status,source_hash,declared_by,created_at '
            f'FROM composition_aspects{where} ORDER BY aspect_id,version', tuple(params)
        )
        return [dict(r) for r in rows]

    def aspect(self, aspect_id, version=None):
        if version is None:
            row = self.db.execute(
                "SELECT definition_json FROM composition_aspects WHERE aspect_id=? AND status='active' ORDER BY version DESC LIMIT 1",
                (aspect_id,),
            ).fetchone()
        else:
            row = self.db.execute(
                'SELECT definition_json FROM composition_aspects WHERE aspect_id=? AND version=?', (aspect_id, int(version))
            ).fetchone()
        require(row is not None, 'unknown composition aspect')
        return json.loads(row[0])

    def graph(self):
        type_defs=[self.type(x['type_id']) for x in self.list_types()]
        frames=[self.frame(x['frame_id'],x['version']) for x in self.list_frames() if x['status']=='active']
        nodes=[]; edges=[]
        families=sorted({x['family'] for x in type_defs})
        for family in families: nodes.append({'id':'family:'+family,'kind':'family','label':family})
        for item in type_defs:
            tid=item['type_id']; nodes.append({'id':'type:'+tid,'kind':'type','label':tid,'family':item['family'],'purpose_type':item.get('purpose_type')})
            edges.append({'source':'type:'+tid,'target':'family:'+item['family'],'kind':'belongs_to'})
            for target in item.get('reacts_with',[]):
                edges.append({'source':'type:'+tid,'target':'family:'+target,'kind':'reacts_with'})
        for frame in frames:
            fid=frame['frame_id'];nodes.append({'id':'frame:'+fid,'kind':'frame','label':fid})
            for slot in frame['slots']:
                sid=f"slot:{fid}:{slot['slot_id']}"
                nodes.append({'id':sid,'kind':'slot','label':slot['slot_id'],'family':slot['family'],'requirement':slot['requirement']})
                edges.append({'source':'frame:'+fid,'target':sid,'kind':'declares'})
                for typ in slot.get('accepts',[]): edges.append({'source':'type:'+typ,'target':sid,'kind':'can_fill'})
                for dep in slot.get('dependencies',[]): edges.append({'source':f"slot:{fid}:{dep}",'target':sid,'kind':'required_by'})
        return {'nodes':nodes,'edges':edges,'counts':{'families':len(families),'types':len(type_defs),'frames':len(frames),'slots':sum(len(f['slots']) for f in frames)}}

    def record_receipt(self, *, receipt_id, branch, frame_id, branch_revision, bindings, result, basis_hash):
        self.db.execute(
            'INSERT INTO composition_receipts VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',
            (receipt_id, branch, frame_id, branch_revision, encoded(bindings), encoded(result), basis_hash, 'compiled'),
        )
