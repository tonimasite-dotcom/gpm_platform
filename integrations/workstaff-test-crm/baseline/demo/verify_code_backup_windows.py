#!/usr/bin/env python3
"""Decrypt in memory and restore into a NEW local private folder, never live TS."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import subprocess
import tarfile


def main():
    root = Path(__file__).resolve().parents[4]
    common = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'],
                            capture_output=True, check=True).stdout.decode().strip()
    git_directory = Path(common)
    if not git_directory.is_absolute():
        git_directory = root / git_directory
    original = git_directory.resolve().parent
    age = original / '.tmp/full-project-snapshot-20261015/tools/age.exe'
    key = original / '.tmp/production-backup-20261015/age-identity.txt'
    private = root / '.tmp/demo-code-backup-05'
    if private.exists() or not key.is_file() or not age.is_file():
        raise RuntimeError('NEW_PRIVATE_RESTORE_AND_EXISTING_KEY_REQUIRED')
    ssh = ['ssh', '-i', str(Path.home() / '.ssh/id_ed25519'), '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(original / '.tmp/test-crm-known-hosts'),
           'root@5.183.191.222']
    server = '/root/gpm-ts-update/20261110-demo-05/code-backup/'
    receipt = subprocess.run(ssh + ['cat ' + server + 'verification.json'], capture_output=True, check=True)
    report = json.loads(receipt.stdout)
    encrypted = subprocess.run(ssh + ['cat ' + server + 'ts-demo-code-before.tar.gz.age'], capture_output=True, check=True).stdout
    if hashlib.sha256(encrypted).hexdigest() != report['sha256']:
        raise RuntimeError('ENCRYPTED_HASH_MISMATCH')
    decoded = subprocess.run([str(age), '--decrypt', '--identity', str(key)], input=encrypted, capture_output=True)
    if decoded.returncode:
        raise RuntimeError('CODE_BACKUP_KEY_MISMATCH_DETAILS_WITHHELD')
    private.mkdir(mode=0o700, parents=True)
    (private / 'ts-demo-code-before.tar.gz.age').write_bytes(encrypted)
    restored = private / 'restored-code'
    restored.mkdir(mode=0o700)
    wanted = {row['file']: row for row in report['files'] if row['existed']}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(decoded.stdout), mode='r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name.startswith('/') or '..' in PurePosixPath(member.name).parts:
                raise RuntimeError('UNSAFE_ARCHIVE_ENTRY')
            if member.name == 'CODE_BACKUP_MANIFEST.json':
                continue
            if member.name not in wanted or member.name in seen:
                raise RuntimeError('UNEXPECTED_OR_DUPLICATE_ARCHIVE_ENTRY')
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != wanted[member.name]['sha256']:
                raise RuntimeError('RESTORE_CONTENT_HASH_MISMATCH')
            path = restored / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as out:
                out.write(data)
            if hashlib.sha256(path.read_bytes()).hexdigest() != wanted[member.name]['sha256']:
                raise RuntimeError('RESTORED_FILE_HASH_MISMATCH')
            seen.add(member.name)
    if seen != set(wanted):
        raise RuntimeError('RESTORE_FILES_MISSING')
    safe = {'passed': True, 'kind': report['kind'], 'encrypted_sha256': report['sha256'],
            'encrypted_bytes': len(encrypted), 'existing_files_restored': len(seen),
            'new_files_absence_recorded': sum(not row['existed'] for row in report['files']),
            'all_restored_sha256_match': True, 'key_stayed_separate': True,
            'database_backup_included': False, 'live_files_changed': False,
            'local_encrypted_backup': '.tmp/demo-code-backup-05/ts-demo-code-before.tar.gz.age',
            'key_location': 'original-checkout/.tmp/production-backup-20261015/age-identity.txt'}
    destination = root / 'audits/crm-ts-demo-rebase-2026-11-10/code-backup-restore.json'
    destination.write_text(json.dumps(safe, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(safe))


if __name__ == '__main__':
    main()
