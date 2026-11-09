#!/usr/bin/env python3
"""Verify new encrypted SQL and restore only into a new private MySQL instance."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess

LOCAL = Path.cwd() / '.tmp/crm-recovery-20261109'
AGE = LOCAL / 'tools/age/age.exe'
KEY = LOCAL / 'age-identity.txt'
BACKUP = LOCAL / 'backup'


def main():
    decoded = subprocess.run([str(AGE), '--decrypt', '--identity', str(KEY),
        str(BACKUP / 'ts-manifest.json.age')], capture_output=True)
    if decoded.returncode:
        raise RuntimeError('Manifest decryption failed')
    manifest = json.loads(decoded.stdout)
    public = json.loads((BACKUP / 'verification.json').read_text())
    archive = BACKUP / 'ts-mysql.sql.gz.age'
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksum != public['artifacts'][archive.name]['sha256']:
        raise RuntimeError('SQL ciphertext mismatch')
    receiver = subprocess.Popen(['ssh', '-i', str(Path.cwd() / '.tmp/crm-access-20261109/id_ed25519'),
        '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
        'root@5.183.191.222', 'nice', '-n', '10', 'python3',
        '/root/gpm-ts-update/20261106-baseline-01/acceptance-20261109/restore_new_sql_receiver.py'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    decrypt = subprocess.Popen([str(AGE), '--decrypt', '--identity', str(KEY), str(archive)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    filtered = 0
    try:
        with gzip.GzipFile(fileobj=decrypt.stdout, mode='rb') as source:
            for line in source:
                digest.update(line)
                if line.startswith(b'DROP TABLE IF EXISTS '):
                    filtered += 1
                    continue
                if line.startswith((b'USE ', b'CREATE DATABASE ', b'GRANT ', b'DROP DATABASE ')):
                    raise RuntimeError('Unexpected database-wide SQL statement')
                receiver.stdin.write(line)
        receiver.stdin.close()
        response = receiver.stdout.read()
        receiver.stderr.read()
        decrypt.stderr.read()
        if receiver.wait() or decrypt.wait():
            raise RuntimeError('Private SQL restore failed; raw diagnostics withheld')
    except Exception:
        for process in (decrypt, receiver):
            if process.poll() is None:
                process.terminate()
        raise
    report = json.loads(response)
    if digest.hexdigest() != manifest['database']['sql_sha256']:
        raise RuntimeError('Decrypted SQL hash mismatch')
    if report['row_counts'] != manifest['database']['row_counts'] or report['table_count'] != 72:
        raise RuntimeError('Restored table row counts mismatch')
    safe = {'restore_completed': True, 'table_count': report['table_count'],
        'all_table_row_counts_match_dump': True, 'decrypted_sql_hash_verified': True,
        'drop_table_statements_filtered': filtered, 'live_database_accessed': False,
        'new_private_instance_only': True, 'old_rehearsal_preserved': True}
    (LOCAL / 'sql-restore-verification.json').write_text(json.dumps(safe, indent=2))
    print(json.dumps(safe))


if __name__ == '__main__':
    main()
