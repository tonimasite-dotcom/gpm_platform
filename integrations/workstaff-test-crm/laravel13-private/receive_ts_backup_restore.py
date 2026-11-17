"""Restore TS SQL into a NEW isolated MySQL datadir, verify, always shut down.

No application is booted; no live socket, app credential, migration or scheduler
is used. The caller must already be inside a new network namespace.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from sql_snapshot import Snapshot

BASE = Path('/root/gpm-ts-runtime-20261113-01')
DATABASE = 'gpm_ts_restore_20261117'
RESERVE = 3 * 1024**3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    options = parser.parse_args()
    if not re.fullmatch('20261117-[0-9]{2}', options.run_id):
        raise RuntimeError('EXACT_RESTORE_RUN_ID_REQUIRED')
    if os.readlink('/proc/self/ns/net') == os.readlink('/proc/1/ns/net'):
        raise RuntimeError('NEW_NETWORK_NAMESPACE_REQUIRED')
    if BASE.resolve() != BASE or shutil.disk_usage(BASE).free < RESERVE + 2 * 1024**3:
        raise RuntimeError('EXACT_BASE_AND_DISK_RESERVE_REQUIRED')
    root = BASE / ('ts-backup-restore-' + options.run_id)
    if root.exists() or root.resolve() != root:
        raise RuntimeError('NEW_PRIVATE_RESTORE_ROOT_REQUIRED')
    os.umask(0o077)
    root.mkdir(mode=0o700)
    data = root / 'data'
    data.mkdir(mode=0o700)
    (root / 'PRIVATE_TS_BACKUP_RESTORE').write_text('SQL restore only; no application startup\n')
    stream = sys.stdin.buffer
    expected = json.loads(stream.readline(2 * 1024**2))
    if expected.get('kind') != 'verified_ts_sql_restore' or len(expected['tables']) != 72:
        raise RuntimeError('VERIFIED_72_TABLE_HEADER_REQUIRED')
    if not 0 < expected['filtered_sql_bytes'] < 4 * 1024**3:
        raise RuntimeError('BOUNDED_SQL_INPUT_REQUIRED')
    socket = root / 'mysql.sock'
    common = ['/usr/sbin/mysqld', '--no-defaults', '--user=root', '--datadir=' + str(data),
              '--log-error=' + str(root / 'mysql-error.log'), '--innodb-buffer-pool-size=67108864',
              '--innodb-log-file-size=16777216', '--event-scheduler=OFF',
              '--innodb-flush-log-at-trx-commit=2']
    client = ['mysql', '--no-defaults', '--protocol=SOCKET', '--socket=' + str(socket),
              '--user=root', '--batch', '--skip-column-names']

    def query(sql):
        result = subprocess.run(client, input=sql.encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            raise RuntimeError('PRIVATE_QUERY_FAILED')
        return result.stdout

    process = None
    importer = None
    result = dict(status='FAILED', run_id=options.run_id, live_ts_changed=False,
                  main_crm_changed=False, existing_synthetic_database_changed=False,
                  migrations_run=False, application_started=False, network_isolated=True,
                  plaintext_dump_created=False, restore_root=str(root))
    try:
        init = subprocess.run(common + ['--initialize-insecure'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, timeout=120)
        if init.returncode:
            raise RuntimeError('PRIVATE_INITIALIZE_FAILED')
        process = subprocess.Popen(common + ['--socket=' + str(socket),
            '--pid-file=' + str(root / 'mysql.pid'), '--skip-networking', '--skip-log-bin',
            '--performance-schema=OFF', '--max-connections=10',
            '--character-set-server=utf8mb4', '--collation-server=utf8mb4_unicode_ci'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('PRIVATE_MYSQL_EXITED')
            if socket.exists():
                probe = subprocess.run(client + ['--execute=SELECT 1'], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                if probe.returncode == 0:
                    break
            time.sleep(0.25)
        else:
            raise RuntimeError('PRIVATE_MYSQL_START_TIMEOUT')
        identity = query('SELECT @@datadir,@@skip_networking,@@event_scheduler').decode().strip().split('\t')
        if Path(identity[0]).resolve() != data or identity[1:] != ['1', 'OFF']:
            raise RuntimeError('PRIVATE_DATADIR_OR_NETWORK_IDENTITY_FAILED')
        user = 'gpm_restore_check'
        password = secrets.token_hex(24)
        query('CREATE DATABASE `' + DATABASE + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
              "CREATE USER '" + user + "'@'localhost' IDENTIFIED BY '" + password + "';"
              "GRANT ALL PRIVILEGES ON `" + DATABASE + "`.* TO '" + user + "'@'localhost';")
        config = root / 'private-client.cnf'
        config.write_text('[client]\nprotocol=SOCKET\nsocket=' + str(socket) + '\nuser=' + user
                          + '\npassword=' + password + '\ndefault-character-set=utf8mb4\n')
        if query('SHOW TABLES FROM `' + DATABASE + '`').strip():
            raise RuntimeError('EMPTY_TARGET_DATABASE_REQUIRED')
        print(json.dumps(dict(stage='private_empty_database_ready', network_isolated=True,
                              event_scheduler_off=True, live_database_accessed=False)), flush=True)
        remaining = expected['filtered_sql_bytes']
        received_hash = hashlib.sha256()
        with (root / 'import-error.log').open('xb') as error:
            importer = subprocess.Popen(['mysql', '--defaults-file=' + str(config),
                '--binary-mode=1', '--database=' + DATABASE], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=error)
            while remaining:
                if shutil.disk_usage(BASE).free < RESERVE:
                    raise RuntimeError('THREE_GIB_RESERVE_REQUIRED')
                block = stream.read(min(remaining, 1024 * 1024))
                if not block:
                    raise RuntimeError('SQL_INPUT_TRUNCATED')
                received_hash.update(block)
                importer.stdin.write(block)
                remaining -= len(block)
            importer.stdin.close()
            if importer.wait(timeout=180):
                raise RuntimeError('PRIVATE_SQL_IMPORT_FAILED')
        footer = json.loads(stream.readline(4096))
        if footer != dict(source_integrity_verified=True, filtered_sql_sha256=received_hash.hexdigest()):
            raise RuntimeError('SOURCE_INTEGRITY_COMMIT_REQUIRED')
        names = query('SHOW TABLES FROM `' + DATABASE + '`').decode().splitlines()
        if set(names) != set(expected['tables']):
            raise RuntimeError('RESTORED_TABLE_INVENTORY_MISMATCH')
        for name in names:
            if not re.fullmatch('[A-Za-z0-9_]+', name):
                raise RuntimeError('UNEXPECTED_TABLE_NAME')
            count = int(query('SELECT COUNT(*) FROM `' + DATABASE + '`.`' + name + '`').strip())
            if count != expected['tables'][name]['rows']:
                raise RuntimeError('RESTORED_ROW_COUNT_MISMATCH')
        print(json.dumps(dict(stage='restored_row_counts_match', tables=len(names))), flush=True)
        dump = subprocess.Popen(['mysqldump', '--defaults-file=' + str(config),
            '--single-transaction', '--skip-lock-tables', '--quick', '--no-tablespaces',
            '--set-gtid-purged=OFF', '--hex-blob', '--skip-extended-insert',
            '--default-character-set=utf8mb4', DATABASE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        snapshot = Snapshot()
        for line in dump.stdout:
            snapshot.line(line)
        dump.stderr.read()
        if dump.wait(timeout=90):
            raise RuntimeError('RESTORED_READBACK_DUMP_FAILED')
        actual = snapshot.finish()
        if actual['tables'] != expected['tables']:
            differences = {name: [key for key in expected['tables'][name]
                          if expected['tables'][name][key] != actual['tables'].get(name, {}).get(key)]
                           for name in expected['tables']
                           if expected['tables'][name] != actual['tables'].get(name)}
            (root / 'private-differences.json').write_text(json.dumps(differences, indent=2) + '\n')
            raise RuntimeError('RESTORED_CONTENT_SCHEMA_OR_AUTO_INCREMENT_MISMATCH')
        (root / 'private-table-fingerprints.json').write_text(json.dumps(actual['tables'], indent=2) + '\n')
        result.update(status='PASS', sql_restore_executed=True, table_count=len(names),
                      all_row_counts_match=True, all_row_content_hashes_match=True,
                      all_table_schema_hashes_match=True, all_auto_increment_values_match=True,
                      source_integrity_commit_verified=True,
                      private_datadir_verified=True, event_scheduler_off=True,
                      total_rows=sum(row['rows'] for row in expected['tables'].values()),
                      free_bytes_after_restore=shutil.disk_usage(BASE).free)
    except Exception as error:
        result['error'] = str(error) if type(error) is RuntimeError else type(error).__name__
    finally:
        if importer is not None and importer.poll() is None:
            importer.terminate()
            importer.wait(timeout=30)
        if process is not None and process.poll() is None:
            try:
                stop = subprocess.run(['mysqladmin', '--no-defaults', '--protocol=SOCKET',
                    '--socket=' + str(socket), '--user=root', 'shutdown'], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30)
                if stop.returncode:
                    raise RuntimeError('PRIVATE_SHUTDOWN_FAILED')
                process.wait(timeout=60)
            except Exception:
                command = Path('/proc/' + str(process.pid) + '/cmdline').read_bytes()
                if ('--datadir=' + str(data)).encode() not in command:
                    raise RuntimeError('PRIVATE_SHUTDOWN_PROCESS_IDENTITY_FAILED')
                process.terminate()
                process.wait(timeout=60)
        result['private_mysql_shutdown_verified'] = (process is None or process.poll() is not None) and not socket.exists()
        if not result['private_mysql_shutdown_verified']:
            result['status'] = 'FAILED'
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
