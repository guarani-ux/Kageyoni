"""Reconstruct inspected Samsara files from three exact immutable inputs.

No network, credentials, database opening, migration or gameplay occurs.
The caller supplies verified Libraryv15, exact ca04 source ZIP and Git parts.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

PARENT_SHA='73738ee2b30962cf461e7c04c499524286b0a81715dbca7f12820618545690b4'
CA04_SHA='13ece8efa26451511b85eb61e67615b374557a4310157636cb395ca3a0fe4132'

def sha(data):return hashlib.sha256(data).hexdigest()

CURRENT_WHEELS={'samsara_world-0.5.3.dev19-py3-none-any.whl',
                'kageyoni_engine-11.1.0.dev11-py3-none-any.whl'}

def plan_archive(archive,plan):
    names=archive.namelist()
    if len(names)!=len(set(names)) or archive.testzip() is not None:
        raise ValueError('Invalid or duplicate ZIP entries')
    for item in archive.infolist():
        path=Path(item.filename)
        if path.is_absolute() or '..' in path.parts or ((item.external_attr>>16)&0o170000)==0o120000:
            raise ValueError('Unsafe ZIP entry')
        if item.is_dir():continue
        if item.filename=='samsara_core/MANIFEST.json':continue
        if (len(path.parts)==3 and path.parts[:2]==('samsara_core','distributions')
                and path.name.endswith('.whl') and path.name not in CURRENT_WHEELS
                and path.name.startswith(('samsara_world-','kageyoni_engine-'))):
            path=Path('samsara_core/distributions/history/reconstructed-parents')/path.name
        plan[path]=(archive,item)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--ca04',type=Path,required=True)
    parser.add_argument('--parts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    recipe=json.loads((args.parts.parent/'overlay-recipe.json').read_text())
    if sha(args.parent.read_bytes())!=PARENT_SHA or sha(args.ca04.read_bytes())!=CA04_SHA:
        raise ValueError('Immutable predecessor identity mismatch')
    blocks=[]
    for entry in recipe['parts']:
        raw=base64.b64decode((args.parts.parent/entry['path']).read_bytes(),validate=True)
        if len(raw)!=entry['bytes'] or sha(raw)!=entry['sha256']:
            raise ValueError('Changed Git overlay part')
        blocks.append(raw)
    overlay=b''.join(blocks)
    if len(overlay)!=recipe['overlay']['bytes'] or sha(overlay)!=recipe['overlay']['sha256']:
        raise ValueError('Changed overlay archive')
    args.output.mkdir(parents=True,exist_ok=False)
    archive_path=args.output/'D11-overlay.zip';archive_path.write_bytes(overlay)
    # Resolve all immutable layers before writing. Each final path is written
    # once; historical wheels go directly into history, never into current.
    with zipfile.ZipFile(args.parent) as parent, zipfile.ZipFile(args.ca04) as ca04, zipfile.ZipFile(archive_path) as current:
        plan={}
        for archive in (parent,ca04,current):plan_archive(archive,plan)
        for path,(archive,item) in plan.items():
            dest=args.output/path;dest.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(item) as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst)
    receipt=json.loads((args.output/'snapshot-receipt.json').read_text())
    root=args.output/'samsara_core'
    for entry in receipt['files']:
        data=(root/entry['path']).read_bytes()
        if len(data)!=entry['bytes'] or sha(data)!=entry['sha256']:
            raise ValueError('Changed snapshot member')
    files=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p!=root/'MANIFEST.json':
            data=p.read_bytes();files.append(dict(path=str(p.relative_to(root)),bytes=len(data),sha256=sha(data)))
    (root/'MANIFEST.json').write_text(json.dumps({'files':files},indent=2)+'\n')
    print(json.dumps({'ok':True,'snapshot_files':len(receipt['files']),
        'source_identity':receipt['source_identity'],'root':str(root),
        'status':'IN_PROGRESS; no new Library version or full release qualified',
        'next':'Inspect CONTINUE/ledger and run tools/verify_candidate.py + tools/next_round.py. This script never executes recovered code.'}))

if __name__=='__main__':main()
