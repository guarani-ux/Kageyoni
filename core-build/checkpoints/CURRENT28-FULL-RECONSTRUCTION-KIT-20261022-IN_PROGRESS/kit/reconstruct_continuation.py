"""Exact archive reconstruction only. No candidate imports, extraction, native/DB or remote effects.

Inputs are separately obtained verified provider files and a verified delta. Existing
authorization governs ordinary recovery; check actual ownership/resources before use.
"""
from pathlib import Path,PurePosixPath
import argparse,contextlib,hashlib,json,os,shutil,zipfile
BLOCK=1024*1024
def stream_file(path):
    return os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|getattr(os,'O_NOATIME',0)),'rb')
def digest_file(path):
    with stream_file(path) as f:return hashlib.file_digest(f,'sha256').hexdigest()
class Inputs:
    def __init__(self,providers,paths,delta):
        self.providers=providers;self.paths={k:Path(v) for k,v in paths.items()};self.delta=delta
        self.zips={};self.handles=[]
    def verify_raw_inputs(self):
        for p in self.providers:
            path=self.paths[p['id']]
            assert path.is_file() and not path.is_symlink()
            assert path.stat().st_size==p['bytes'] and digest_file(path)==p['sha256'],p['id']
    def zip(self,pid):
        if pid not in self.zips:
            f=stream_file(self.paths[pid]);self.handles.append(f);self.zips[pid]=zipfile.ZipFile(f)
        return self.zips[pid]
    @contextlib.contextmanager
    def body(self,ref):
        kind=ref['kind']
        if kind=='provider-raw':
            with stream_file(self.paths[ref['provider']]) as f:yield f
        elif kind=='provider-member':
            with self.zip(ref['provider']).open(ref['member']) as f:yield f
        elif kind=='delta-member':
            with self.delta.open(ref['member']) as f:yield f
        elif kind=='provider-slice':
            with self.body(ref['source']) as f:
                remaining=ref.get('offset',0)
                while remaining:
                    b=f.read(min(BLOCK,remaining));assert b;remaining-=len(b)
                yield Limited(f,ref['bytes'])
        else:raise ValueError('Unsupported body source '+kind)
    def close(self):
        for z in self.zips.values():z.close()
        for f in self.handles:f.close()
class Limited:
    def __init__(self,f,count):self.f=f;self.remaining=count
    def read(self,count):
        if not self.remaining:return b''
        data=self.f.read(min(count,self.remaining));assert data
        self.remaining-=len(data);return data
def chunks(f):
    for block in iter(lambda:f.read(BLOCK),b''):yield block
def check_body(inputs,entry,consumer=None):
    h=hashlib.sha256();count=0
    if not entry['is_directory']:
        with inputs.body(entry['body']) as f:
            for block in chunks(f):
                count+=len(block);h.update(block)
                if consumer:consumer(block)
    assert count==entry['body_bytes'] and h.hexdigest()==entry['body_sha256'],entry['path']
def codec_check(inputs,entries):
    tested=[]
    for empty in [False,True]:
        e=next((e for e in entries if not e['is_directory'] and e['zip_metadata']['compress_type']==zipfile.ZIP_LZMA and (e['body_bytes']==0)==empty and e['body_bytes']<=4096),None)
        if e is None:continue
        compressor=zipfile.LZMACompressor();h=hashlib.sha256();count=0
        def accept(block):
            nonlocal count
            encoded=compressor.compress(block);h.update(encoded);count+=len(encoded)
        check_body(inputs,e,accept);tail=compressor.flush();h.update(tail);count+=len(tail)
        assert count==e['compressed_bytes'] and h.hexdigest()==e['compressed_sha256'], 'LZMA encoder mismatch; matching codec required'
        tested.append(e['path'])
    assert tested
    return tested
def main():
    a=argparse.ArgumentParser();a.add_argument('--recipe',required=True,type=Path);a.add_argument('--delta',required=True,type=Path)
    a.add_argument('--providers-json',required=True,type=Path);a.add_argument('--verify-only',action='store_true')
    a.add_argument('--output',type=Path);a.add_argument('--reserve-bytes',type=int,default=1024**3);args=a.parse_args()
    recipe=json.loads(args.recipe.read_bytes());paths=json.loads(args.providers_json.read_bytes())
    assert args.delta.stat().st_size==recipe['delta']['bytes'] and digest_file(args.delta)==recipe['delta']['sha256']
    with stream_file(args.delta) as delta_stream,zipfile.ZipFile(delta_stream) as delta:
        assert delta.testzip() is None
        mapping=delta.read(recipe['entry_map']['member']);assert hashlib.sha256(mapping).hexdigest()==recipe['entry_map']['sha256']
        entries=json.loads(mapping);assert len(entries)==12688 and len({e['path'] for e in entries})==12688
        layout=delta.read(recipe['container_layout']['member']);assert hashlib.sha256(layout).hexdigest()==recipe['container_layout']['sha256']
        inputs=Inputs(recipe['providers'],paths,delta)
        try:
            inputs.verify_raw_inputs();calibration=codec_check(inputs,entries)
            if args.verify_only:
                for e in entries:check_body(inputs,e)
                print(json.dumps(dict(status='ALL_EXPLICIT_ENTRY_BODY_SOURCES_AND_CODEC_CALIBRATIONS_VERIFIED',entries=len(entries),files=sum(not e['is_directory'] for e in entries),raw_file_bytes=sum(e['body_bytes'] for e in entries),codec_calibrations=calibration,full_archive_reconstruction_executed=False,remote_custody_of_new_delta=recipe['remote_custody_of_new_recipe_and_delta'])))
                return
            assert args.output is not None and args.reserve_bytes>=0
            output=args.output.absolute();partial=output.with_name(output.name+'.partial')
            assert output.parent.is_dir() and not output.exists() and not partial.exists()
            assert shutil.disk_usage(output.parent).free>=recipe['target']['bytes']+args.reserve_bytes
            whole=hashlib.sha256()
            with partial.open('xb') as out:
                def write(data):out.write(data);whole.update(data)
                for e in entries:
                    path=PurePosixPath(e['path']);assert not path.is_absolute() and '..' not in path.parts and path.parts[0]=='samsara_core'
                    assert out.tell()==e['target_header_offset']
                    start=e['local_header_layout_offset'];write(layout[start:start+e['local_header_bytes']])
                    compressed=hashlib.sha256();count=0;method=e['zip_metadata']['compress_type']
                    encoder=zipfile.LZMACompressor() if method==zipfile.ZIP_LZMA else None
                    assert method in [zipfile.ZIP_LZMA,zipfile.ZIP_STORED]
                    def encode(block):
                        nonlocal count
                        data=encoder.compress(block) if encoder else block
                        write(data);compressed.update(data);count+=len(data)
                    check_body(inputs,e,encode)
                    if encoder:
                        data=encoder.flush();write(data);compressed.update(data);count+=len(data)
                    assert count==e['compressed_bytes'] and compressed.hexdigest()==e['compressed_sha256'],e['path']
                trailer=recipe['container_layout'];assert out.tell()==trailer['trailer_target_offset']
                start=trailer['trailer_layout_offset'];write(layout[start:start+trailer['trailer_bytes']])
                assert out.tell()==recipe['target']['bytes'] and whole.hexdigest()==recipe['target']['sha256']
                out.flush();os.fsync(out.fileno())
            with zipfile.ZipFile(partial) as z:
                assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==12688
            os.link(partial,output)
            print(json.dumps(dict(status='EXACT_COMPLETE_ARCHIVE_RECONSTRUCTED',output=str(output),bytes=output.stat().st_size,sha256=whole.hexdigest(),fullCRC=True,all_per_entry_raw_and_compressed_SHA_verified=True,source_or_DB_or_Git_or_Library_effects=False)))
        finally:inputs.close()
if __name__=='__main__':main()
