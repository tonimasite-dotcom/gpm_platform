"""Verify the fresh TS backup in memory and restore only a new private old-host DB."""
import argparse
import base64
import gzip
import hashlib
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

from sql_snapshot import Snapshot, DROP

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'maintenance'))
from verify_ts_backup_stream import BACKUP, Decrypted, SSH

SSH = SSH[:-1] + ['-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=6'] + SSH[-1:]


def read_manifest(public):
    source = Decrypted('ts-manifest.json.age', public['artifacts']['ts-manifest.json.age'])
    try:
        body = source.decrypt.stdout.read(64 * 1024**2 + 1)
        if len(body) > 64 * 1024**2:
            raise RuntimeError('BOUNDED_MANIFEST_REQUIRED')
        manifest = json.loads(body)
        source.finish()
        return manifest['database']
    except Exception:
        source.abort()
        raise


def fingerprint(public, database):
    source = Decrypted('ts-mysql.sql.gz.age', public['artifacts']['ts-mysql.sql.gz.age'])
    snapshot = Snapshot()
    try:
        with gzip.GzipFile(fileobj=source.decrypt.stdout) as stream:
            for line in stream:
                snapshot.line(line)
        source.finish()
        result = snapshot.finish()
        if (result['sql_sha256'] != database['sql_sha256'] or result['sql_bytes'] != database['sql_bytes']
                or {name: row['rows'] for name, row in result['tables'].items()} != database['row_counts']
                or len(result['tables']) != 72):
            raise RuntimeError('VERIFIED_SOURCE_SQL_MANIFEST_MISMATCH')
        return result
    except Exception:
        source.abort()
        raise


def tools_directory():
    root = Path(__file__).parent
    files = {name: base64.b64encode((root / name).read_bytes()).decode()
             for name in ['sql_snapshot.py', 'receive_ts_backup_restore.py']}
    version = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    remote = '/root/gpm-ts-runtime-20261113-01/ts-restore-tools-20261117-' + version
    code = ("import base64,json,os;from pathlib import Path;os.umask(0o077)\n"
            f"p=Path('{remote}');assert p.resolve()==p\n"
            "p.mkdir(mode=0o700,exist_ok=True)\n"
            f"files=json.loads({json.dumps(files)!r})\n"
            "for name,value in files.items():\n"
            " target=p/name;body=base64.b64decode(value);assert not target.is_symlink()\n"
            " if target.exists():assert target.read_bytes()==body\n"
            " else:\n  with target.open('xb') as stream:stream.write(body)\n")
    result = subprocess.run(SSH + ['python3 -B -'], input=code.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('PRIVATE_RESTORE_TOOL_UPLOAD_FAILED')
    return remote


def restore(public, expected, run_id):
    remote = tools_directory()
    process = subprocess.Popen(SSH + ['unshare --net -- python3 -B ' + remote
        + '/receive_ts_backup_restore.py --run-id ' + run_id], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    receipts = []

    def read_output():
        for line in process.stdout:
            value = json.loads(line)
            receipts.append(value)
            print(json.dumps(value), flush=True)

    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()
    source = None
    try:
        process.stdin.write(json.dumps(dict(kind='verified_ts_sql_restore', **expected)).encode() + b'\n')
        source = Decrypted('ts-mysql.sql.gz.age', public['artifacts']['ts-mysql.sql.gz.age'])
        digest = hashlib.sha256()
        filtered = hashlib.sha256()
        sent = 0
        with gzip.GzipFile(fileobj=source.decrypt.stdout) as stream:
            for line in stream:
                digest.update(line)
                if DROP.fullmatch(line):
                    continue
                process.stdin.write(line)
                filtered.update(line)
                sent += len(line)
        source.finish()
        if digest.hexdigest() != expected['sql_sha256'] or sent != expected['filtered_sql_bytes']:
            raise RuntimeError('IMPORT_SOURCE_CHANGED')
        process.stdin.write((json.dumps(dict(source_integrity_verified=True,
                            filtered_sql_sha256=filtered.hexdigest())) + '\n').encode())
        process.stdin.close()
        error = process.stderr.read()
        code = process.wait(timeout=300)
        thread.join(timeout=15)
        if code or not receipts or receipts[-1].get('status') != 'PASS':
            if receipts and receipts[-1].get('error'):
                raise RuntimeError('RESTORE_FAILED:' + receipts[-1]['error'])
            raise RuntimeError('PRIVATE_RESTORE_OR_SSH_FAILED')
        result = receipts[-1]
        result.update(source_cipher_hashes_verified=True, source_sql_sha256_verified=True,
                      source_table_schema_and_row_fingerprints_verified=True,
                      private_key_uploaded=False, plaintext_dump_saved_on_pc=False,
                      drop_table_statements_filtered=expected['drops_filtered'])
        return result
    except Exception as error:
        if source is not None:
            source.abort()
        try:
            process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=30)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch('20261117-[0-9]{2}', args.run_id):
        raise RuntimeError('SAFE_RUN_ID_REQUIRED')
    received = subprocess.run(SSH + ['cat ' + BACKUP + '/verification.json'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if received.returncode:
        raise RuntimeError('BACKUP_REPORT_READ_FAILED')
    public = json.loads(received.stdout)
    database = read_manifest(public)
    expected = fingerprint(public, database)
    print(json.dumps(dict(stage='fresh_ts_sql_and_manifest_verified', table_count=len(expected['tables']),
                          sql_bytes=expected['sql_bytes'],
                          total_rows=sum(row['rows'] for row in expected['tables'].values()),
                          private_key_uploaded=False)), flush=True)
    result = restore(public, expected, args.run_id)
    Path('.tmp/ts-backup-restore-' + args.run_id + '.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(stage='complete', **result)), flush=True)


if __name__ == '__main__':
    main()
