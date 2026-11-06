#!/usr/bin/env python3
"""Check every member/hash of encrypted TS file backup without extracting data.

This proves archive integrity and coverage against its manifest, not a full
filesystem/application recovery. External symlink targets are never followed.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile

FILES = Path('.tmp/ts-baseline-backup')
AGE = '.tmp/full-project-snapshot-20261015/tools/age.exe'
IDENTITY = '.tmp/production-backup-20261015/age-identity.txt'


def main():
    public = json.loads((FILES / 'verification.json').read_text())
    archive = FILES / 'ts-files.tar.gz.age'
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    if digest.hexdigest() != public['artifacts'][archive.name]['sha256']:
        raise RuntimeError('Encrypted file backup hash mismatch')
    metadata = subprocess.run([AGE, '--decrypt', '--identity', IDENTITY,
                               str(FILES / 'ts-manifest-corrected.json.age')], capture_output=True)
    if metadata.returncode: raise RuntimeError('Cannot decrypt backup manifest')
    manifest = json.loads(metadata.stdout)
    process = subprocess.Popen([AGE, '--decrypt', '--identity', IDENTITY, str(archive)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seen = set();count = 0
    with tarfile.open(fileobj=process.stdout, mode='r|gz') as source:
        for member in source:
            if member.name in seen or member.name not in manifest['files']:
                raise RuntimeError('Unexpected or duplicate archive member')
            seen.add(member.name);expected = manifest['files'][member.name]
            if member.issym():
                if expected['kind'] != 'symlink' or member.linkname != expected['target']:
                    raise RuntimeError('Symlink metadata mismatch')
            elif member.isfile():
                if expected['kind'] != 'file' or member.size != expected['bytes']:
                    raise RuntimeError('File metadata mismatch')
                digest = hashlib.sha256()
                data = source.extractfile(member)
                for block in iter(lambda: data.read(1024 * 1024), b''): digest.update(block)
                if digest.hexdigest() != expected['sha256']:
                    raise RuntimeError('File content hash mismatch')
                count += 1
            else: raise RuntimeError('Unexpected archive member type')
    error = process.stderr.read()
    if process.wait(): raise RuntimeError('File backup decryption failed')
    if seen != set(manifest['files']): raise RuntimeError('Incomplete file backup archive')
    report = json.loads((FILES / 'restore-verification.json').read_text())
    report.update({'files_archive_verified': True, 'file_entries_verified': len(seen),
                   'regular_files_verified': count, 'external_symlinks_followed': False,
                   'full_filesystem_restore_performed': False,
                   'scope_note': 'TS public/storage refers to a separate test site; target data not copied or accessed'})
    (FILES / 'restore-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__': main()
