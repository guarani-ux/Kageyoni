"""Opt-in scoped source work over the single native Documents service.

Passage checking establishes literal provenance, never learning or quality.
"""
import json
from copy import deepcopy
from .protocol import Fault, digest, decode


class SourceWork:
    def __init__(self, owner):
        self.owner = owner

    def enabled(self, activity):
        definition = self.owner.catalog[activity['spec']['definition']['id']]
        return definition.get('source_work') in ({'version': 1, 'mode': m} for m in ('study', 'research', 'script'))

    def _scope(self, activity, refs):
        o = self.owner
        audiences = set()
        for ref in refs:
            audience = o.artifact_audience(ref)
            if audience is not None:
                audiences.add(audience)
        if len(audiences) > 1:
            raise Fault('UNAVAILABLE')
        o.text_sources(activity['spec'], refs)
        if audiences:
            return next(iter(audiences))
        # Preserve the public lane only where both established recipients can
        # actually read its inherited C2/causal scope. A single-reader activity
        # can instead retain that scope in a private native artifact.
        recipients = o.text_recipients(activity['spec'])
        try:
            for ref in refs:
                for actor in {'visitor', 'keeper'} | recipients:
                    o.artifact_scope_for_actor(actor, ref, prospective=True)
        except Fault as error:
            if error.code != 'UNAVAILABLE' or len(recipients) != 1:
                raise
            return next(iter(recipients))
        return None

    def _inherited(self, activity):
        refs = list(activity['spec']['source_refs']) + list(activity['native'].get('reconciled_returns', []))
        for row in self.owner.db.execute("SELECT payload_json FROM activity_outbox WHERE workspace_id=? AND parent_id=? AND status='pending'", (self.owner.workspace_id, activity['activity_id'])):
            refs += json.loads(row[0])['result_refs']
        return refs

    def _bindings(self, activity):
        o = self.owner
        inherited = self._inherited(activity)
        self._scope(activity, inherited)  # All inherited bytes checked BEFORE native ingest.
        bindings, all_refs, manifests = [], list(inherited), 0
        for ref in activity['spec']['source_refs']:
            row = o.db.execute('SELECT * FROM document_sources WHERE workspace_id=? AND source_id LIKE ? AND artifact_id=?', (o.workspace_id, 'samsara:intake:%', ref['id'])).fetchone()
            if row:
                raw = o.services.artifacts.read(ref['id'], viewer=None)['content']
                manifest = decode(raw)
                if not isinstance(manifest, dict) or manifest.get('kind') != 'intake':
                    raise Fault('INVALID')
                current = o.intake.row(manifest['assignment_id'])
                if current is None or current['artifact_id'] != ref['id'] or row['revision'] != manifest['revision'] or current['revision'] != row['revision']:
                    raise Fault('STALE')
                if row['source_id'] != o.intake.source_id(manifest['assignment_id']):
                    raise Fault('INVALID')
                manifests += 1
                metadata = json.loads(row['metadata_json'])
                for file in manifest['files']:
                    extracted = file['extracted_ref']; all_refs += [file['raw_ref'], extracted]
                    blob = o.services.artifacts.read(extracted['id'], viewer=None)['content']
                    bindings.append({'source_id': 'samsara:source-work:' + digest([manifest['assignment_id'], file['relative_path']]),
                        'text': self._utf8(blob, 256000), 'source_ref': extracted, 'origin': manifest['origin'],
                        'identity': manifest['assignment_id'], 'captured_at': metadata['captured_at'],
                        'request': o.key('source-work-ingest', ref, file['relative_path'], extracted), 'manifest_ref': ref})
            else:
                blob = o.services.artifacts.read(ref['id'], viewer=None)['content']
                # Non-manifest returned artifacts supplement, never replace intake.
                bindings.append({'source_id': 'samsara:returned:' + ref['id'], 'text': self._utf8(blob, 256000),
                    'source_ref': ref, 'origin': 'Returned artifact; attributed content, not verified truth',
                    'identity': ref['id'], 'captured_at': None, 'request': o.key('source-work-returned', ref), 'manifest_ref': None})
        if not manifests:
            raise Fault('DEPENDENCY')
        if not 1 <= len(bindings) <= 32 or sum(len(x['text'].encode()) for x in bindings) > 256000:
            raise Fault('BUDGET')
        audience = self._scope(activity, all_refs)
        for binding in bindings:
            binding['recipient'] = audience
            if audience is not None:
                # Never relabel/reuse an earlier public native binding. Source
                # and retry identity distinguish immutable audience as well as
                # the authentic original source/ref/intake generation.
                binding['source_id'] += ':recipient:' + digest(audience)
                binding['request'] = o.key(binding['request'], 'recipient', audience)
        return bindings, all_refs

    @staticmethod
    def _utf8(blob, cap):
        if len(blob) > cap:
            raise Fault('BUDGET')
        try:
            text = blob.decode('utf-8')
        except UnicodeError:
            raise Fault('UNSUPPORTED') from None
        if not text.strip():
            raise Fault('INVALID')
        return text

    def prepare(self, activity, job_id):
        from datetime import datetime, timezone
        o = self.owner
        bindings, refs = self._bindings(activity)
        sources = []
        for binding in bindings:
            existing = o.db.execute('SELECT metadata_json FROM document_sources WHERE request_id=?', (binding['request'],)).fetchone()
            captured = binding['captured_at'] or (json.loads(existing[0])['captured_at'] if existing else datetime.now(timezone.utc).isoformat())
            source = o.services.documents.ingest(o.workspace_id, binding['request'], binding['source_id'], binding['text'],
                binding['identity'], binding['identity'], captured, viewer=None, locator=binding['origin'],
                recipient=binding['recipient'])
            latest = o.services.documents.source(o.workspace_id, binding['source_id'], viewer=None)
            if latest['revision'] != source['revision'] or latest['digest'] != source['digest']:
                raise Fault('STALE')
            native_ref = {'id': source['artifact_id'], 'version': 1, 'digest': source['digest']}
            recipients = {'character:' + a for a in o.text_recipients(activity['spec'])}
            for principal in recipients:
                o.grant(native_ref, principal, activity['activity_id'])
            o.properties.inherit(native_ref, recipients, refs)
            sources.append({k: source[k] for k in ('source_id', 'revision', 'digest', 'text') } | {
                'source_ref': binding['source_ref'], 'manifest_ref': binding['manifest_ref'], 'origin': binding['origin']})
            refs.append(native_ref)
        actor = activity['spec']['participants'][0]
        mode = o.catalog[activity['spec']['definition']['id']]['source_work']['mode']
        return actor, {'type': activity['spec']['kind'], 'mode': mode, 'source_work': {'version': 1, 'mode': mode},
            'objective': activity['spec']['purpose'], 'work_record_ref': activity['native']['work_record_ref'], 'sources': sources,
            '_source_refs': refs, 'acceptance': 'Return actual authored work, attributed assessment and exact current native passages. No mastery, truth or whole-purpose certification.',
            'return_contract': 'Two current-job staged outputs: exact version-1 envelope and substantive authored UTF-8 artifact. Native inquiry and optional source scaffold are separate from authored work.'}

    @staticmethod
    def _text(value, cap=2048):
        if not isinstance(value, str) or not value.strip() or len(value) > cap:
            raise Fault('INVALID')

    def _validate(self, activity, prepared, envelope):
        o = self.owner
        packet = o.packet(prepared)['input']
        self._bindings(activity)  # Latest intake and inherited permissions still hold.
        self._scope(activity, [x['source_ref'] for x in packet['sources']] + [prepared['input_ref']])
        sources = {x['source_id']: x for x in packet['sources']}
        for source in sources.values():
            current = o.services.documents.source(o.workspace_id, source['source_id'], viewer=None)
            if current['status'] != 'available' or any(current[k] != source[k] for k in ('revision', 'digest', 'text')):
                raise Fault('STALE')
        def passage(value):
            if not isinstance(value, dict) or set(value) != {'source_id','revision','digest','start','end'}:
                raise Fault('INVALID')
            if not isinstance(value['source_id'], str):
                raise Fault('INVALID')
            source = sources.get(value['source_id'])
            if source is None or type(value['revision']) is not int or value['revision'] != source['revision'] or value['digest'] != source['digest']:
                raise Fault('STALE')
            if type(value['start']) is not int or type(value['end']) is not int or not 0 <= value['start'] < value['end'] <= len(source['text']):
                raise Fault('INVALID')
        if not isinstance(envelope, dict) or set(envelope) != {'version','job_id','attempt_generation','input_digest','disposition','authored_ref','assessment','inquiry','draft'}:
            raise Fault('INVALID')
        if type(envelope['version']) is not int or envelope['version'] != 1 or envelope['job_id'] != prepared['job_id'] or type(envelope['attempt_generation']) is not int or envelope['attempt_generation'] != prepared['attempt_generation'] or envelope['input_digest'] != prepared['input_ref']['digest']:
            raise Fault('STALE')
        if envelope['disposition'] not in ('returned','no_gain','refused'):
            raise Fault('INVALID')
        assessment = envelope['assessment']
        if not isinstance(assessment, dict) or set(assessment) != {'attribution','limit'}:
            raise Fault('INVALID')
        for value in assessment.values(): self._text(value)
        inquiry = envelope['inquiry']
        if not isinstance(inquiry, dict) or set(inquiry) != {'question','required_fields','claims','counters'}:
            raise Fault('INVALID')
        self._text(inquiry['question'])
        fields = inquiry['required_fields']
        if not isinstance(fields, list) or not 1 <= len(fields) <= 64 or any(not isinstance(x,str) or not x or len(x)>256 for x in fields) or len(set(fields)) != len(fields):
            raise Fault('INVALID')
        for key in ('claims','counters'):
            if not isinstance(inquiry[key],list): raise Fault('INVALID')
            for claim in inquiry[key]:
                if not isinstance(claim,dict) or set(claim) != {'field','evidence'} or claim['field'] not in fields: raise Fault('INVALID')
                passage(claim['evidence'])
        if len(inquiry['claims'])+len(inquiry['counters'])>256: raise Fault('BUDGET')
        brief = envelope['draft']
        if packet['mode']=='script' and envelope['disposition']=='returned' and brief is None: raise Fault('INVALID')
        if brief is not None:
            if not isinstance(brief,dict) or not {'brief_id','title','audience','purpose','sections'} <= set(brief) <= {'brief_id','title','audience','purpose','sections','obligations'}: raise Fault('INVALID')
            for key in ('brief_id','title','audience','purpose'): self._text(brief[key])
            if not isinstance(brief['sections'],list) or not 1<=len(brief['sections'])<=100: raise Fault('INVALID')
            ids=set()
            for section in brief['sections']:
                if not isinstance(section,dict) or not {'id','heading','field'} <= set(section) <= {'id','heading','field','required','claims','metrics'}: raise Fault('INVALID')
                for key in ('id','heading','field'): self._text(section[key],256)
                if section['id'] in ids or type(section.get('required',True)) is not bool: raise Fault('INVALID')
                ids.add(section['id'])
                if not isinstance(section.get('claims',[]),list) or len(section.get('claims',[]))>32: raise Fault('INVALID')
                for citation in section.get('claims',[]): passage(citation)
                # Metrics have no effect without transfer; do not admit unvalidated hidden citations.
                if section.get('metrics',{}) != {}: raise Fault('UNSUPPORTED')
            obligations=brief.get('obligations',[])
            if not isinstance(obligations,list) or len(obligations)>128: raise Fault('INVALID')
            for obligation in obligations:
                if not isinstance(obligation,dict) or set(obligation)!={'id','status','evidence'} or obligation['status'] not in ('required','cancelled'): raise Fault('INVALID')
                self._text(obligation['id']); passage(obligation['evidence'])

    def receive(self, activity, prepared, result, context):
        o=self.owner
        if len(result['output_refs'])!=2 or result['output_refs'][0]==result['output_refs'][1]: raise Fault('INVALID')
        stages=o.db.execute('SELECT staging_ref FROM activity_staging WHERE job_id=? AND generation=? AND consumed=1', (prepared['job_id'],prepared['attempt_generation'])).fetchall()
        admitted={o.key(row[0],'admit') for row in stages}
        for ref in result['output_refs']:
            row=o.db.execute('SELECT request_id FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',(o.workspace_id,ref['id'],ref['digest'])).fetchone()
            if row is None or row[0] not in admitted: raise Fault('UNAVAILABLE')
            self._scope(activity,[ref])
        raw=o.artifact_bytes(context,result['output_refs'][0])
        if len(raw)>100000: raise Fault('BUDGET')
        envelope=decode(raw)
        if not isinstance(envelope, dict) or envelope.get('authored_ref')!=result['output_refs'][1]: raise Fault('INVALID')
        self._utf8(o.artifact_bytes(context,result['output_refs'][1]),256000)
        self._validate(activity,prepared,envelope)
        return {'outputs':deepcopy(result['output_refs']),'checks':deepcopy(result['check_results']),'source_work':envelope}

    def commit(self, activity, prepared, proposal, context):
        o=self.owner; envelope=proposal['source_work']
        self._validate(activity,prepared,envelope)
        sources=activity['spec']['source_refs']+o.text_input_sources(activity,prepared)+[prepared['input_ref']]+proposal['outputs']
        audience=self._scope(activity,sources)
        inquiry=o.services.documents.inquire(o.workspace_id,o.key(prepared['job_id'],'source-inquiry'),viewer=None,
            recipient=audience,**envelope['inquiry'])
        if inquiry['phase'] == 'blocked':
            # Native diagnostics retain their historical blocked result. An
            # operational source-work return must actually respect that stop;
            # the enclosing unit rolls this rejected inquiry back as well.
            raise Fault('BUDGET')
        outputs=list(proposal['outputs']); scaffold=None; draft=None
        if envelope['draft'] is not None:
            draft=o.services.documents.draft(o.workspace_id,o.key(prepared['job_id'],'source-draft'),envelope['draft'],viewer=None,
                recipient=audience)
            meta=draft['artifact']; scaffold={'id':meta['artifact_id'],'version':1,'digest':meta['digest']}
            recipients={'character:'+a for a in o.text_recipients(activity['spec'])}
            for principal in recipients: o.grant(scaffold,principal,activity['activity_id'])
            o.properties.inherit(scaffold,recipients,sources)
            outputs.append(scaffold)
        receipt={'kind':'source_work_receipt','version':1,'mode':o.packet(prepared)['input']['mode'],
            'disposition':envelope['disposition'],'assessment':envelope['assessment'],'authored_ref':envelope['authored_ref'],
            'inquiry':inquiry,'draft_id':draft['draft_id'] if draft else None,'scaffold_ref':scaffold,
            'sources':[{k:x[k] for k in ('source_id','revision','digest','source_ref')} for x in o.packet(prepared)['input']['sources']],
            'purpose':'unresolved','limit':'Native literal provenance and coverage; authored quality, learning and real-world truth are not certified.'}
        ref=o.put_json(receipt,o.key(prepared['job_id'],'source-work-receipt'),activity=activity,source_refs_override=sources)
        outputs.append(ref)
        return dict(proposal,outputs=outputs,native_receipt_ref=ref)
