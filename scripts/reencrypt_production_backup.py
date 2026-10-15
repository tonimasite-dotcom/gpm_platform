#!/usr/bin/env python3
"""Recovery transfer: emit only ciphertext for an owner's new public recipient."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from production_backup import validate_recipient
from verify_production_backup import inspect_tar, run

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--identity',type=Path,required=True)
    parser.add_argument('--age',type=Path,required=True)
    parser.add_argument('--recipient',required=True)
    args=parser.parse_args()
    validate_recipient(args.recipient)
    os.umask(0o077)
    previous=json.loads((args.source/'verification.json').read_text())
    if not previous.get('ok') or not previous.get('isolated_database_restore'):
        raise ValueError('Source backup has no successful restore verification')
    args.target.mkdir(mode=0o700,exist_ok=False)
    def sha(path):
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        return digest.hexdigest()
    with tempfile.TemporaryDirectory(prefix='gpm-recovery-private-',dir=args.target.parent) as temp:
        for component in ['backend','frontend']:
            encrypted=args.source/(component+'.tar.gz.age')
            metadata=json.loads((args.source/(component+'-manifest.json')).read_text())
            if encrypted.stat().st_size!=metadata['bytes'] or sha(encrypted)!=metadata['sha256']:
                raise ValueError('Source artifact checksum mismatch')
            plain=Path(temp)/(component+'.tar.gz')
            run([str(args.age),'--decrypt','--identity',str(args.identity),'--output',str(plain),str(encrypted)],timeout=900)
            manifest=inspect_tar(plain)
            if manifest['component']!=component or manifest['run_id']!=metadata['run_id']:
                raise ValueError('Decrypted backup identity mismatch')
            target=args.target/encrypted.name
            run([str(args.age),'--encrypt','--recipient',args.recipient,'--output',str(target),str(plain)],timeout=900)
            metadata.update({'sha256':sha(target),'bytes':target.stat().st_size,'age_recipient':args.recipient,
                             'recovery_transfer':True})
            (args.target/(component+'-manifest.json')).write_text(json.dumps(metadata,indent=2)+'\n')
            plain.unlink()
    previous['recovery_transfer']=True
    previous['recovery_recipient']=args.recipient
    (args.target/'verification.json').write_text(json.dumps(previous,indent=2)+'\n')
    files=sorted(p for p in args.target.iterdir() if p.is_file())
    (args.target/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files))
    print('Recovery transfer verified and re-encrypted; no plaintext/key was exported.')

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Recovery transfer failed ('+type(error).__name__+'); no private contents printed.')
        raise SystemExit(1)
