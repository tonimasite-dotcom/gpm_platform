#!/usr/bin/env python3
"""Verify encrypted TS dump and stream restore over SSH; never write plaintext.

Owner's existing recovery key stays on Windows. The receiving program must have
already verified and created a separate, empty, network-isolated MySQL instance.
"""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess

ROOT = Path.cwd()
FILES = ROOT / '.tmp/ts-baseline-backup'
AGE = ROOT / '.tmp/full-project-snapshot-20261015/tools/age.exe'
IDENTITY = ROOT / '.tmp/production-backup-20261015/age-identity.txt'
REMOTE = '/root/gpm-ts-update/20261106-baseline-01'


def main():
    public = json.loads((FILES / 'verification.json').read_text())
    for name in ['ts-manifest.json.age', 'ts-mysql.sql.gz.age']:
        data = FILES / name
        digest = hashlib.sha256(data.read_bytes()).hexdigest()
        if digest != public['artifacts'][name]['sha256']:
            raise RuntimeError('Encrypted backup hash mismatch')
    result = subprocess.run([str(AGE), '--decrypt', '--identity', str(IDENTITY),
                             str(FILES / 'ts-manifest.json.age')], capture_output=True)
    if result.returncode: raise RuntimeError('Cannot decrypt encrypted manifest')
    manifest = json.loads(result.stdout)
    command = ['ssh', '-i', str(Path.home() / '.ssh/id_ed25519'),
               '-o', 'UserKnownHostsFile=' + str(ROOT / '.tmp/test-crm-known-hosts'),
               '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
               'root@5.183.191.222', 'python3', REMOTE + '/restore_receiver.py']
    decrypt = subprocess.Popen([str(AGE), '--decrypt', '--identity', str(IDENTITY),
                                str(FILES / 'ts-mysql.sql.gz.age')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    receiver = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256();filtered = 0
    with gzip.GzipFile(fileobj=decrypt.stdout, mode='rb') as source:
        for line in source:
            digest.update(line)
            # mysqldump's default DROP statements are unnecessary in our empty
            # target. Do not execute deletions even as part of a rehearsal.
            if line.startswith(b'DROP TABLE IF EXISTS '):
                filtered += 1;continue
            if line.startswith((b'USE ', b'CREATE DATABASE ', b'GRANT ', b'DROP DATABASE ')):
                raise RuntimeError('Unexpected database-wide statement in dump')
            receiver.stdin.write(line)
    receiver.stdin.close()
    output = receiver.stdout.read();error = receiver.stderr.read()
    receiver_code = receiver.wait();decrypt_error = decrypt.stderr.read();decrypt_code = decrypt.wait()
    if receiver_code or decrypt_code: raise RuntimeError('Private stream restore failed; diagnostics withheld')
    if digest.hexdigest() != manifest['database']['sql_sha256']:
        raise RuntimeError('Decrypted SQL hash mismatch')
    restore = json.loads(output)
    if restore['row_counts'] != manifest['database']['row_counts']:
        raise RuntimeError('Restored row counts differ from dump snapshot')
    summary = {'ts_mysql_restore_verified': True, 'table_count': restore['table_count'],
               'all_dump_row_counts_match': True, 'sql_sha256_verified': True,
               'encrypted_hashes_verified': True, 'plaintext_files_created': False,
               'drop_table_statements_not_executed': filtered, 'live_database_changed': False}
    (FILES / 'restore-verification.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__': main()
