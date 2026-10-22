"""Opt-in local instructional media component; structure is not quality.

Host production/decoding is deliberately outside the owner. Sources, audiences,
job fences and immutable bytes remain owned by existing native services.
"""
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import json
import re
import struct

from .protocol import Fault, decode, validate


PROFILE = {'version': 1, 'profile': 'local_instruction_mp4'}
ROLES = {'video': 'video/mp4', 'transcript': 'text/plain',
         'captions': 'application/x-subrip', 'technical_checks': 'application/json'}
MAX_VIDEO = 10000000
MAX_TEXT = 100000


def _require(value, code='INVALID'):
    if not value:
        raise Fault(code)


def _text(value, cap=2048):
    _require(isinstance(value, str) and value.strip() and '\x00' not in value and len(value) <= cap)
    return value


def _utf8(blob, cap=MAX_TEXT):
    _require(type(blob) is bytes and len(blob) <= cap, 'BUDGET')
    try:
        value = blob.decode('utf-8')
    except UnicodeError:
        raise Fault('INVALID') from None
    return _text(value, cap)


def _u32(blob, offset):
    _require(offset >= 0 and offset + 4 <= len(blob))
    return int.from_bytes(blob[offset:offset+4], 'big')


def _boxes(blob, start=0, end=None):
    """Bounded ISO-BMFF box framing; never execute or trust embedded metadata."""
    end = len(blob) if end is None else end
    _require(0 <= start <= end <= len(blob))
    result=[]
    while start < end:
        _require(len(result) < 4096 and end-start >= 8)
        size=_u32(blob,start);kind=blob[start+4:start+8];header=8
        if size == 1:
            _require(end-start >= 16)
            size=int.from_bytes(blob[start+8:start+16], 'big');header=16
        # Size-zero boxes and ambiguous trailing data are outside this profile.
        _require(size >= header and start+size <= end)
        result.append((kind,start+header,start+size,start))
        start += size
    _require(start == end)
    return result


def _one(boxes, kind):
    matches=[box for box in boxes if box[0] == kind]
    _require(len(matches) == 1)
    return matches[0]


def _body(blob, box):
    return blob[box[1]:box[2]]


def mp4_profile(blob):
    """Validate one silent 720p24 AVC container's bounded sample-table structure.

    This does not decode H.264 or establish that a frame is meaningful, legible,
    accessible, faithful to a brief, or suitable for publication.
    """
    _require(type(blob) is bytes and 24 <= len(blob) <= MAX_VIDEO, 'BUDGET')
    top=_boxes(blob)
    _require(all(box[0] in (b'ftyp',b'moov',b'mdat',b'free',b'wide') for box in top), 'UNSUPPORTED')
    _require(top[0][0]==b'ftyp')
    ftyp=_body(blob,_one(top,b'ftyp'))
    _require(len(ftyp) >= 12 and (len(ftyp)-8) % 4 == 0)
    brands=[ftyp[:4]]+[ftyp[n:n+4] for n in range(8,len(ftyp),4)]
    _require(any(brand in (b'isom',b'iso2',b'avc1',b'mp41',b'mp42') for brand in brands), 'UNSUPPORTED')
    moov=_one(top,b'moov');mdat=_one(top,b'mdat')
    _require(mdat[2] > mdat[1] and moov[3]<mdat[3], 'UNSUPPORTED')
    children=_boxes(blob,moov[1],moov[2])
    tracks=[box for box in children if box[0] == b'trak']
    _require(len(tracks) == 1, 'UNSUPPORTED')
    track=_boxes(blob,tracks[0][1],tracks[0][2]);mdia=_one(track,b'mdia')
    media=_boxes(blob,mdia[1],mdia[2]);hdlr=_body(blob,_one(media,b'hdlr'))
    _require(len(hdlr) >= 12 and hdlr[8:12] == b'vide', 'UNSUPPORTED')
    mdhd=_body(blob,_one(media,b'mdhd'))
    _require(mdhd and mdhd[0] in (0,1))
    if mdhd[0] == 0:
        timescale=_u32(mdhd,12);duration=_u32(mdhd,16)
    else:
        timescale=_u32(mdhd,20);_require(len(mdhd) >= 32)
        duration=int.from_bytes(mdhd[24:32],'big')
    _require(timescale > 0 and 0 < duration <= timescale*300, 'UNSUPPORTED')
    minf=_one(media,b'minf');stbl=_one(_boxes(blob,minf[1],minf[2]),b'stbl')
    tables=_boxes(blob,stbl[1],stbl[2])
    stsd=_body(blob,_one(tables,b'stsd'));_require(len(stsd) >= 8 and _u32(stsd,4) == 1)
    sample=_one(_boxes(stsd,8),b'avc1')
    _require(sample[3] == 8 and sample[1]-sample[3] == 8 and sample[2] == len(stsd), 'UNSUPPORTED')
    entry=stsd[sample[3]:sample[2]]
    _require(len(entry) >= 86)
    width=int.from_bytes(entry[32:34],'big');height=int.from_bytes(entry[34:36],'big')
    _require((width,height) == (1280,720), 'UNSUPPORTED')
    avcc=_body(entry,_one(_boxes(entry,86),b'avcC'))
    _require(len(avcc) >= 7 and avcc[0] == 1, 'UNSUPPORTED')
    _require(avcc[4]&3 == 3 and avcc[5]&31 > 0, 'UNSUPPORTED')
    cursor=6
    for _ in range(avcc[5]&31):
        _require(cursor+2<=len(avcc));length=int.from_bytes(avcc[cursor:cursor+2],'big');cursor+=2
        _require(length>0 and cursor+length<=len(avcc) and avcc[cursor]&31==7)
        cursor+=length
    _require(cursor<len(avcc));pps=avcc[cursor];cursor+=1;_require(pps>0)
    for _ in range(pps):
        _require(cursor+2<=len(avcc));length=int.from_bytes(avcc[cursor:cursor+2],'big');cursor+=2
        _require(length>0 and cursor+length<=len(avcc) and avcc[cursor]&31==8)
        cursor+=length
    stsz=_body(blob,_one(tables,b'stsz'));_require(len(stsz) >= 12)
    fixed,count=_u32(stsz,4),_u32(stsz,8)
    _require(1 <= count <= 7200, 'BUDGET')
    _require(len(stsz) == (12 if fixed else 12+4*count))
    sizes=[fixed]*count if fixed else [_u32(stsz,12+4*n) for n in range(count)]
    _require(all(size > 0 for size in sizes))
    stts=_body(blob,_one(tables,b'stts'));_require(len(stts) >= 8)
    time_count=_u32(stts,4);_require(1 <= time_count <= count and len(stts)==8+8*time_count)
    timing=[(_u32(stts,8+8*n),_u32(stts,12+8*n)) for n in range(time_count)]
    _require(all(n > 0 and delta > 0 and Fraction(timescale,delta)==24 for n,delta in timing), 'UNSUPPORTED')
    _require(sum(n for n,_ in timing)==count and sum(n*delta for n,delta in timing)==duration)
    # Sample locations must actually fit inside the sole admitted mdat payload.
    offsets=[box for box in tables if box[0] in (b'stco',b'co64')]
    _require(len(offsets)==1)
    offset_box=offsets[0];offsets_body=_body(blob,offset_box)
    _require(len(offsets_body)>=8)
    chunks=_u32(offsets_body,4);unit=4 if offset_box[0]==b'stco' else 8
    _require(1<=chunks<=count and len(offsets_body)==8+unit*chunks)
    locations=[int.from_bytes(offsets_body[8+n*unit:8+(n+1)*unit],'big') for n in range(chunks)]
    stsc=_body(blob,_one(tables,b'stsc'));_require(len(stsc)>=8)
    maps=_u32(stsc,4);_require(1<=maps<=chunks and len(stsc)==8+12*maps)
    mapping=[(_u32(stsc,8+12*n),_u32(stsc,12+12*n),_u32(stsc,16+12*n)) for n in range(maps)]
    _require(mapping[0][0]==1 and all(1<=first<=chunks and 1<=n<=count and desc==1 for first,n,desc in mapping))
    _require(all(a[0]<b[0] for a,b in zip(mapping,mapping[1:])))
    cursor=0;active=0;previous_end=mdat[1]
    for number,location in enumerate(locations,1):
        while active+1<len(mapping) and mapping[active+1][0]<=number:active+=1
        n=mapping[active][1];_require(cursor+n<=count)
        end=location+sum(sizes[cursor:cursor+n]);cursor+=n
        _require(mdat[1]<=location<end<=mdat[2] and location>=previous_end)
        previous_end=end
    _require(cursor==count)
    return {'profile':'local_instruction_mp4','codec_container':'avc1','width':width,'height':height,
        'fps':24,'frames':count,'duration_numerator':duration,'duration_denominator':timescale,
        'audio_tracks':0,'bytes':len(blob),
        'limit':'Bounded container/sample-table structure only; no decoder, frame, editorial or accessibility certification.'}


def captions_profile(blob, transcript, duration):
    value=_utf8(blob).replace('\r\n','\n').replace('\r','\n').strip()
    blocks=re.split(r'\n[ \t]*\n',value)
    _require(1<=len(blocks)<=1000,'BUDGET')
    normalized=' '.join(transcript.split());previous=0
    stamp=r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    for index,block in enumerate(blocks,1):
        lines=block.splitlines();_require(len(lines)>=3 and lines[0]==str(index))
        match=re.fullmatch(stamp+r' --> '+stamp,lines[1]);_require(match is not None)
        numbers=[int(x) for x in match.groups()]
        def ms(values):
            h,m,s,millis=values;_require(m<60 and s<60)
            return ((h*60+m)*60+s)*1000+millis
        start,end=ms(numbers[:4]),ms(numbers[4:])
        _require(previous<=start<end and Fraction(end,1000)<=duration)
        previous=end
        for line in lines[2:]:
            _text(line,10000);_require(' '.join(line.split()) in normalized)
    return {'cues':len(blocks),'last_end_ms':previous,
        'limit':'SRT timing and literal transcript correspondence only; no human reading-pace or accessibility result.'}


class MediaWork:
    def __init__(self,owner):
        self.owner=owner

    def enabled(self,activity):
        definition=self.owner.catalog[activity['spec']['definition']['id']]
        return (definition['id']=='synthetic:media_work' and definition.get('kind')=='real_work'
            and definition.get('handler')=='text_work' and definition.get('media_work')==PROFILE)

    def prepare(self,activity,job_id):
        o=self.owner
        _require(self.enabled(activity),'UNSUPPORTED')
        bindings,refs=o.source_work._bindings(activity)
        audience=o.source_work._scope(activity,refs)
        sources=[];brief=None
        for binding in bindings:
            prior=o.db.execute('SELECT metadata_json FROM document_sources WHERE request_id=?',(binding['request'],)).fetchone()
            captured=binding['captured_at'] or (json.loads(prior[0])['captured_at'] if prior else datetime.now(timezone.utc).isoformat())
            source=o.services.documents.ingest(o.workspace_id,binding['request'],binding['source_id'],binding['text'],
                binding['identity'],binding['identity'],captured,viewer=None,locator=binding['origin'],recipient=binding['recipient'])
            current=o.services.documents.source(o.workspace_id,binding['source_id'],viewer=None)
            _require(current['status']=='available' and all(current[k]==source[k] for k in ('revision','digest','text')),'STALE')
            native={'id':source['artifact_id'],'version':1,'digest':source['digest']}
            recipients={'character:'+a for a in o.text_recipients(activity['spec'])}
            for principal in recipients:o.grant(native,principal,activity['activity_id'])
            o.properties.inherit(native,recipients,refs)
            sources.append({k:source[k] for k in ('source_id','revision','digest','text')}|{
                'source_ref':binding['source_ref'],'manifest_ref':binding['manifest_ref'],
                'native_ref':native,'origin':binding['origin']})
            refs.append(native)
            if brief is None and binding['manifest_ref'] is not None:
                manifest=decode(o.services.artifacts.read(binding['manifest_ref']['id'],viewer=None)['content'])
                brief={'assignment_id':binding['identity'],'revision':manifest['revision'],
                    'manifest_ref':binding['manifest_ref'],'brief_source_ref':binding['source_ref']}
        _require(brief is not None,'DEPENDENCY')
        actor=activity['spec']['participants'][0]
        return actor,{'type':'real_work','media_work':deepcopy(PROFILE),'objective':activity['spec']['purpose'],
            'work_record_ref':activity['native']['work_record_ref'],'sources':sources,'source_refs':deepcopy(refs),
            '_source_refs':refs,'brief_binding':brief,'return_contract':'MediaReturn/1: current staged envelope plus typed outputs; no publication or self-certified quality.',
            'acceptance':'Local silent720p24 AVC container, UTF8 transcript/SRT and attributed technical report. Native structure and source provenance are not decoder, editorial, human or whole-purpose certification.'}

    def _current(self,activity,prepared):
        o=self.owner;packet=o.packet(prepared)['input']
        _require(self.enabled(activity) and packet.get('media_work')==PROFILE,'DEPENDENCY')
        bindings,refs=o.source_work._bindings(activity)
        sources=packet.get('sources')
        _require(isinstance(sources,list) and len(sources)==len(bindings),'STALE')
        expected_brief=None
        for binding,source in zip(bindings,sources):
            _require(source.get('source_id')==binding['source_id'] and source.get('source_ref')==binding['source_ref']
                and source.get('manifest_ref')==binding['manifest_ref'],'STALE')
            current=o.services.documents.source(o.workspace_id,source['source_id'],viewer=None)
            _require(current['status']=='available' and all(current.get(k)==source.get(k) for k in ('revision','digest','text')),'STALE')
            _require(source.get('native_ref')=={'id':current['artifact_id'],'version':1,'digest':current['digest']},'STALE')
            refs.append(source['native_ref'])
            if expected_brief is None and binding['manifest_ref'] is not None:
                manifest=decode(o.services.artifacts.read(binding['manifest_ref']['id'],viewer=None)['content'])
                expected_brief={'assignment_id':binding['identity'],'revision':manifest['revision'],
                    'manifest_ref':binding['manifest_ref'],'brief_source_ref':binding['source_ref']}
        _require(packet.get('brief_binding')==expected_brief and expected_brief is not None,'STALE')
        _require(packet.get('source_refs')==refs,'STALE')
        o.source_work._scope(activity,refs+[prepared['input_ref']])
        return packet,refs

    def _artifact(self,context,ref,media_type,admitted):
        o=self.owner
        row=o.db.execute('SELECT request_id,media_type,size FROM artifacts WHERE workspace_id=? AND artifact_id=? AND digest=?',
            (o.workspace_id,ref.get('id'),ref.get('digest'))).fetchone()
        _require(row is not None and ref.get('version')==1 and row['request_id'] in admitted,'UNAVAILABLE')
        _require(row['media_type']==media_type)
        blob=o.artifact_bytes(context,ref)
        _require(len(blob)==row['size'])
        return blob

    def _validate(self,activity,prepared,result,context):
        o=self.owner;packet,refs=self._current(activity,prepared)
        outputs=result.get('output_refs')
        _require(isinstance(outputs,list) and len(outputs) in (2,5))
        # Use canonical structured identity; references themselves may not be hashable.
        identities=[json.dumps(ref,sort_keys=True) for ref in outputs]
        _require(len(set(identities))==len(outputs))
        stages=o.db.execute('SELECT staging_ref FROM activity_staging WHERE job_id=? AND generation=? AND consumed=1 AND binding_id=?',
            (prepared['job_id'],prepared['attempt_generation'],context.binding_id)).fetchall()
        admitted={o.key(row[0],'admit') for row in stages}
        for ref in outputs:
            _require(isinstance(ref,dict) and set(ref)=={'id','version','digest'})
            validate(ref,'Reference')
            o.source_work._scope(activity,[ref])
        raw=self._artifact(context,outputs[0],'application/json',admitted)
        _require(len(raw)<=MAX_TEXT,'BUDGET');envelope=decode(raw)
        fields={'type','version','job_id','attempt_generation','input_digest','brief_binding','disposition','outputs','attribution','limits'}
        _require(isinstance(envelope,dict) and set(envelope)==fields)
        _require(envelope['type']=='MediaReturn/1' and type(envelope['version']) is int and envelope['version']==1)
        _require(envelope['job_id']==prepared['job_id'] and type(envelope['attempt_generation']) is int
            and envelope['attempt_generation']==prepared['attempt_generation'] and envelope['input_digest']==prepared['input_ref']['digest'],'STALE')
        brief=envelope['brief_binding']
        _require(isinstance(brief,dict) and set(brief)=={'assignment_id','revision','manifest_ref','brief_source_ref'})
        _text(brief['assignment_id']);_require(type(brief['revision']) is int and brief['revision']>=1)
        validate(brief['manifest_ref'],'Reference');validate(brief['brief_source_ref'],'Reference')
        _require(brief==packet['brief_binding'],'STALE')
        _text(envelope['attribution']);_text(envelope['limits'],4096)
        _require(envelope['disposition'] in ('returned','partial','refused'))
        declared=envelope['outputs'];_require(isinstance(declared,list) and len(declared)==len(outputs)-1)
        allowed=ROLES if envelope['disposition']=='returned' else {'assessment':'text/plain'}
        _require(len(declared)==len(allowed))
        by_role={}
        for entry,ref in zip(declared,outputs[1:]):
            _require(isinstance(entry,dict) and set(entry)=={'role','reference','media_type'})
            role=entry['role'];_require(isinstance(role,str) and role in allowed and role not in by_role and entry['reference']==ref
                and entry['media_type']==allowed[role])
            by_role[role]=(ref,self._artifact(context,ref,allowed[role],admitted))
        _require(set(by_role)==set(allowed))
        structural=None;captions=None;host=None
        if envelope['disposition']=='returned':
            video=by_role['video'];structural=mp4_profile(video[1])
            transcript=_utf8(by_role['transcript'][1])
            captions=captions_profile(by_role['captions'][1],transcript,
                Fraction(structural['duration_numerator'],structural['duration_denominator']))
            _require(len(by_role['technical_checks'][1])<=MAX_TEXT,'BUDGET')
            host=decode(by_role['technical_checks'][1])
            _require(isinstance(host,dict) and set(host)=={'type','version','video_digest','attribution','observations','limits'})
            _require(host['type']=='MediaTechnicalChecks/1' and type(host['version']) is int and host['version']==1
                and host['video_digest']==video[0]['digest'])
            _text(host['attribution']);_text(host['limits'],4096)
            _require(isinstance(host['observations'],list) and len(host['observations'])<=64)
            names=set()
            for check in host['observations']:
                _require(isinstance(check,dict) and set(check)=={'name','result','detail'})
                _text(check['name'],128);_text(check['detail'],2048)
                _require(check['name'] not in names and check['result'] in ('passed','failed','not_run','inconclusive'))
                names.add(check['name'])
        else:
            _utf8(by_role['assessment'][1])
        return {'outputs':deepcopy(outputs),'checks':deepcopy(result.get('check_results',[])),
            'media_disposition':envelope['disposition'],'media_work':envelope,
            'media_metadata':{'brief_binding':deepcopy(packet['brief_binding']),
                'sources':[{k:s[k] for k in ('source_id','revision','digest','source_ref','native_ref','manifest_ref')} for s in packet['sources']],
                'structural_profile':structural,'caption_structure':captions,
                'host_technical_report':None if host is None else {'attribution':host['attribution'],
                    'reference':by_role['technical_checks'][0],
                    'limit':'Attributed host statements only; owner did not execute a decoder or judge quality.'}},
            '_media_result':deepcopy(result)}

    def receive(self,activity,prepared,result,context):
        return self._validate(activity,prepared,result,context)

    def commit(self,activity,prepared,proposal,context):
        # Re-run all current source/staging/byte checks at the actual commit seam.
        checked=self._validate(activity,prepared,proposal['_media_result'],context)
        o=self.owner;packet,refs=self._current(activity,prepared)
        sources=refs+[prepared['input_ref']]+checked['outputs']
        o.source_work._scope(activity,sources)
        receipt={'kind':'media_work_receipt','version':1,'profile':'local_instruction_mp4',
            'job_id':prepared['job_id'],'attempt_generation':prepared['attempt_generation'],
            'input_ref':deepcopy(prepared['input_ref']),
            'disposition':checked['media_disposition'],'attribution':checked['media_work']['attribution'],
            'declared_limits':checked['media_work']['limits'],'declared_outputs':deepcopy(checked['media_work']['outputs']),
            **checked['media_metadata'],'purpose':'unresolved',
            'limit':'Native current-source provenance and bounded media structure. Host production, decoding, editorial quality, recipient use, human review and publication are separate evidence.'}
        ref=o.put_json(receipt,o.key(prepared['job_id'],'media-work-receipt'),activity=activity,source_refs_override=sources)
        return {'outputs':checked['outputs']+[ref],'checks':checked['checks'],
            'media_disposition':checked['media_disposition'],'native_receipt_ref':ref,
            'media_metadata':checked['media_metadata']}
