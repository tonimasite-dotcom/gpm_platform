#!/usr/bin/env python3
"""Correct row-count metadata for column-list INSERTs; preserve original backup.

Verify the entire original SQL hash and the existing private restore. Decrypted
manifest/SQL are streamed or held in memory, never written to disk.
"""
from pathlib import Path
import gzip
import hashlib
import json
import re
import subprocess

FILES = Path('.tmp/ts-baseline-backup')
AGE = '.tmp/full-project-snapshot-20261015/tools/age.exe'
IDENTITY = '.tmp/production-backup-20261015/age-identity.txt'


def main():
    result = subprocess.run([AGE, '--decrypt', '--identity', IDENTITY, str(FILES / 'ts-manifest.json.age')], capture_output=True)
    if result.returncode: raise RuntimeError('Cannot decrypt original manifest')
    manifest = json.loads(result.stdout)
    expected = {key: 0 for key in manifest['database']['row_counts']}
    digest = hashlib.sha256()
    process = subprocess.Popen([AGE, '--decrypt', '--identity', IDENTITY, str(FILES / 'ts-mysql.sql.gz.age')],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    insert = re.compile(rb'^INSERT INTO `([^`]+)`(?:\s|\()')
    with gzip.GzipFile(fileobj=process.stdout) as source:
        for line in source:
            digest.update(line)
            match = insert.match(line)
            if match:
                table = match[1].decode()
                if table not in expected: raise RuntimeError('Unexpected INSERT target')
                expected[table] += 1
    error = process.stderr.read()
    if process.wait() or digest.hexdigest() != manifest['database']['sql_sha256']:
        raise RuntimeError('Original SQL hash/decryption failed')
    actual = json.loads((FILES / 'restore-private-result.json').read_text())
    if actual['row_counts'] != expected: raise RuntimeError('Actual private restore does not match original dump')
    changes = sum(expected[key] != manifest['database']['row_counts'][key] for key in expected)
    manifest['database']['row_counts'] = expected
    manifest['metadata_correction'] = {'reason': 'Explicit column-list INSERTs were not counted in original manifest',
                                       'affected_table_count': changes, 'sql_changed': False}
    corrected = FILES / 'ts-manifest-corrected.json.age'
    result = subprocess.run([AGE, '--encrypt', '--recipients-file', str(FILES / 'age-recipient.txt'),
                             '--output', str(corrected)], input=json.dumps(manifest, ensure_ascii=False).encode(), capture_output=True)
    if result.returncode: raise RuntimeError('Cannot encrypt corrected manifest')
    report = {'ts_mysql_restore_verified': True, 'table_count': len(expected), 'all_dump_row_counts_match': True,
              'sql_sha256_verified': True, 'sql_unchanged': True, 'plaintext_files_created': False,
              'live_database_changed': False, 'metadata_correction_tables': changes,
              'corrected_manifest': {'file': corrected.name, 'sha256': hashlib.sha256(corrected.read_bytes()).hexdigest(),
                                     'bytes': corrected.stat().st_size},
              'original_manifest_preserved': True,
              'files_archive_verified': False}
    (FILES / 'restore-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__': main()
