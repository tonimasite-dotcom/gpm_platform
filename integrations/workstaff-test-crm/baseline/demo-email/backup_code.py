#!/usr/bin/env python3
"""Encrypt only the exact TS code files covered by the demo overlay. No SQL."""
from pathlib import Path
import hashlib
import datetime
import io
import json
import os
import subprocess
import tarfile

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PRIVATE = Path('/root/gpm-ts-update/20261110-demo-06')
SEAL = Path('/root/gpm-snapshots/20261015-before-sync')
DEST = PRIVATE / 'code-backup'


def main():
    os.umask(0o077)
    if TS.resolve() != TS or PRIVATE.resolve() != PRIVATE or DEST.exists():
        raise RuntimeError('NEW_EXACT_CODE_BACKUP_REQUIRED')
    manifest = json.loads((PRIVATE / 'manifest.json').read_text())
    metadata = []
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w:gz') as tar:
        for row in manifest['files']:
            path = TS / row['file']
            if path.resolve() != path or path.is_symlink():
                raise RuntimeError('SYMLINK_REJECTED')
            if row['before_sha256'] is None:
                if path.exists():
                    raise RuntimeError('NEW_FILE_ALREADY_EXISTS')
                metadata.append({'file': row['file'], 'existed': False})
                continue
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != row['before_sha256']:
                raise RuntimeError('TS_CODE_CHANGED_REVIEW_REQUIRED')
            info = tar.gettarinfo(str(path), arcname=row['file'])
            tar.addfile(info, io.BytesIO(content))
            metadata.append({'file': row['file'], 'existed': True, 'sha256': digest,
                             'bytes': len(content), 'mode': info.mode, 'uid': info.uid, 'gid': info.gid})
        encoded = json.dumps({'files': metadata}, indent=2).encode()
        info = tarfile.TarInfo('CODE_BACKUP_MANIFEST.json')
        info.size = len(encoded)
        info.mode = 0o600
        tar.addfile(info, io.BytesIO(encoded))
    DEST.mkdir(mode=0o700)
    path = DEST / 'ts-demo-code-before.tar.gz.age'
    process = subprocess.run([str(SEAL / 'age'), '--encrypt', '--recipients-file', str(SEAL / 'age-recipient.txt'),
                              '--output', str(path)], input=archive.getvalue(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode:
        raise RuntimeError('ENCRYPTION_FAILED_DETAILS_WITHHELD')
    report = {'encrypted': True, 'kind': 'targeted_code_backup_no_database', 'files': metadata,
              'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'artifact': str(path), 'bytes': path.stat().st_size,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'plaintext_archive_written': False, 'restore_verified': False,
              'live_files_changed': False, 'database_accessed': False, 'main_crm_accessed': False}
    (DEST / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'TARGETED_CODE_BACKUP_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
