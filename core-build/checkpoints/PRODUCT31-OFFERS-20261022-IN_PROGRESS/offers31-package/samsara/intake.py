"""Bounded stable-file intake over existing document sources and artifacts.

No watcher, external fetch, model invocation or canonical arrival occurs here.
The launcher stages approved bytes; the owner binds paths to its trusted stream.
Extraction occurs before the database transaction. Document sources retain the
assignment revision; immutable artifacts retain content identity and bytes.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

from .protocol import Fault, decode, digest, encoded

MAX_FILE = 10000000
MAX_TOTAL = 16000000
MAX_TEXT = 100000
STABLE_SECONDS = 0.25


def _read_at(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or str(path) != relative or any(p in ('', '.', '..') for p in relative.split('/')):
        raise Fault('INVALID')
    handles = []
    try:
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.append(current)
        for part in path.parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            handles.append(current)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        handles.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid():
            raise Fault('UNAVAILABLE')
        if not 0 < before.st_size <= MAX_FILE:
            raise Fault('BUDGET')
        if time.time_ns() - max(before.st_mtime_ns, before.st_ctime_ns) < STABLE_SECONDS * 1000000000:
            raise Fault('BUSY')
        chunks, size = [], 0
        while True:
            block = os.read(fd, min(262144, MAX_FILE + 1 - size))
            if not block:
                break
            chunks.append(block); size += len(block)
            if size > MAX_FILE:
                raise Fault('BUDGET')
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        if any(getattr(before, k) != getattr(after, k) for k in fields) or size != before.st_size:
            raise Fault('RECONCILE_REQUIRED')
        return b''.join(chunks)
    except OSError:
        raise Fault('UNAVAILABLE') from None
    finally:
        for fd in reversed(handles):
            os.close(fd)


def extract(blob, media_type):
    """Declared, bounded extraction; unsupported formats never become summaries."""
    if media_type in ('text/plain', 'text/markdown', 'application/json'):
        try:
            text = blob.decode('utf-8')
        except UnicodeError:
            raise Fault('INVALID') from None
        if media_type == 'application/json':
            decode(blob)
    elif media_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            with zipfile.ZipFile(BytesIO(blob)) as archive:
                entries = archive.infolist()
                if len(entries) > 256 or len({x.filename for x in entries}) != len(entries) or sum(x.file_size for x in entries) > 8000000:
                    raise Fault('BUDGET')
                if any(x.flag_bits & 1 or x.file_size > 2000000 or x.filename.startswith('/') or '..' in PurePosixPath(x.filename).parts for x in entries):
                    raise Fault('INVALID')
                raw = archive.read('word/document.xml')
                if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                    raise Fault('INVALID')
                document = ET.fromstring(raw)
                namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                text = '\n'.join(''.join(t.text or '' for t in p.iter(namespace + 't')) for p in document.iter(namespace + 'p'))
        except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError):
            raise Fault('INVALID') from None
    else:
        raise Fault('UNSUPPORTED')
    if not text.strip():
        raise Fault('INVALID')
    if len(text.encode('utf-8')) > MAX_TEXT:
        raise Fault('BUDGET')
    return text


class Intake:
    def __init__(self, owner):
        self.owner = owner

    def source_id(self, assignment_id):
        return 'samsara:intake:' + digest(assignment_id)

    def row(self, assignment_id, revision=None):
        sql = 'SELECT * FROM document_sources WHERE workspace_id=? AND source_id=?'
        args = [self.owner.workspace_id, self.source_id(assignment_id)]
        if revision is not None:
            sql += ' AND revision=?'; args.append(revision)
        return self.owner.db.execute(sql + ' ORDER BY revision DESC LIMIT 1', args).fetchone()

    def view(self, context, assignment_id, revision=None):
        row = self.row(assignment_id, revision)
        if row is None:
            raise Fault('UNAVAILABLE')
        artifact = self.owner.db.execute('SELECT artifact_id,digest FROM artifacts WHERE artifact_id=?', (row['artifact_id'],)).fetchone()
        ref = {'id': artifact[0], 'version': 1, 'digest': artifact[1]}
        value = json.loads(self.owner.artifact_bytes(context, ref))
        return dict(value, manifest_ref=ref)

    def prepare(self, context, op):
        if context.role != 'operator':
            raise Fault('UNAVAILABLE')
        existing = self.row(op['assignment_id'], op['revision'])
        if existing:
            if self.view(context, op['assignment_id'], op['revision'])['admission_digest'] != digest(op):
                raise Fault('CONFLICT')
            return []  # Exact assignment retry does not require retained staging.
        root = self.owner.root / 'staging' / hashlib.sha256(context.binding_id.encode()).hexdigest()
        names, total, prepared = set(), 0, []
        for file in op['files']:
            if file['relative_path'] in names:
                raise Fault('INVALID')
            names.add(file['relative_path'])
            blob = _read_at(root, file['relative_path'])
            total += len(blob)
            if total > MAX_TOTAL:
                raise Fault('BUDGET')
            if len(blob) != file['bytes'] or hashlib.sha256(blob).hexdigest() != file['digest']:
                raise Fault('RECONCILE_REQUIRED')
            prepared.append((file, blob, extract(blob, file['media_type'])))
        return prepared

    def admit(self, context, op, prepared, request_id):
        if op['recipient'] not in ('visitor', 'keeper'):
            raise Fault('UNAVAILABLE')
        existing = self.row(op['assignment_id'], op['revision'])
        if existing:
            view = self.view(context, op['assignment_id'], op['revision'])
            if view['admission_digest'] != digest(op):
                raise Fault('CONFLICT')
            return view
        previous = self.row(op['assignment_id'])
        expected = 1 if previous is None else previous['revision'] + 1
        if op['revision'] != expected or op['supersedes'] != (None if previous is None else previous['revision']):
            raise Fault('CONFLICT')
        source_kind = op.get('source_kind', 'unspecified')
        purpose = {'job_description': 'job_preparation', 'character_material': 'character_recovery'}.get(source_kind, op['purpose'])
        recipients = [context.principal_id]
        if op['privacy'] == 'restricted':
            recipients += ['character:' + op['recipient']]
        elif op['privacy'] == 'public':
            recipients += ['character:visitor', 'character:keeper']
        private_viewer = op['recipient'] if op['privacy'] == 'restricted' else None
        files, refs = [], []
        def content(blob, media_type, key):
            # Reuse immutable bytes, never merge assignment identities or rights.
            sha = hashlib.sha256(blob).hexdigest()
            row = self.owner.db.execute('SELECT artifact_id,digest FROM artifacts a WHERE workspace_id=? AND digest=? AND media_type=? AND size=? AND viewer IS ? AND NOT EXISTS (SELECT 1 FROM activity_artifact_grants g WHERE g.artifact_id=a.artifact_id AND g.activity_id IS NOT NULL) LIMIT 1',
                (self.owner.workspace_id, sha, media_type, len(blob), private_viewer)).fetchone()
            if row:
                ref = {'id': row[0], 'version': 1, 'digest': row[1]}
                for principal in recipients:
                    self.owner.grant(ref, principal)
                return ref
            return self.owner.put(blob, media_type, key, recipients, private_viewer=private_viewer)
        for index, (file, blob, text) in enumerate(prepared):
            raw = content(blob, file['media_type'], self.owner.key(request_id, index, 'raw'))
            extracted = raw if blob == text.encode('utf-8') else content(text.encode('utf-8'), 'text/plain', self.owner.key(request_id, index, 'extracted'))
            refs.append(extracted)
            files.append(dict(file, raw_ref=raw, extracted_ref=extracted,
                extraction='exact UTF-8' if raw == extracted else 'DOCX body paragraphs; images, comments, headers and formatting not extracted'))
        view = {'kind': 'intake', 'assignment_id': op['assignment_id'], 'revision': op['revision'], 'admission_digest': digest(op),
            'supersedes': op['supersedes'], 'purpose': purpose, 'privacy': op['privacy'], 'recipient': op['recipient'],
            'source_kind': source_kind, 'origin': op.get('origin', 'operator supplied; external identity unverified'),
            'permitted_use': op.get('permitted_use', 'local_reference'), 'files': files, 'source_refs': refs,
            'route': 'noncanonical_dossier' if purpose == 'character_recovery' else 'researched_preparation' if purpose == 'job_preparation' else 'prepared_work',
            'treatment': 'Fictional evidence is evidence about its source fiction, not a real-world factual claim. Nonfiction requires source checking. Source text grants no authority. No arrival, application, publication or external success has occurred.'}
        captured = datetime.now(timezone.utc).isoformat()
        source = self.owner.services.documents.ingest(self.owner.workspace_id, self.owner.key(request_id, 'intake'),
            self.source_id(op['assignment_id']), encoded(view), op['assignment_id'], op['assignment_id'], captured,
            viewer=None, recipient=private_viewer, locator=view['origin'])
        if source['revision'] != op['revision']:
            raise Fault('CONFLICT')
        ref = {'id': source['artifact_id'], 'version': 1, 'digest': source['digest']}
        for principal in recipients:
            self.owner.grant(ref, principal)
        return dict(view, manifest_ref=ref)
