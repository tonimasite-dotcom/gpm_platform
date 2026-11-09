#!/usr/bin/env python3
"""Stop only the two verified private rehearsal/recovery MySQL instances."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')


def stop(directory):
    data = directory / 'data'
    socket = directory / 'mysql.sock'
    pidfile = directory / 'mysql.pid'
    if directory.resolve() != directory or data.resolve() != data or not (data / 'ibdata1').is_file():
        raise RuntimeError('SAVED_PRIVATE_DATADIR_REQUIRED')
    if not socket.exists() or not pidfile.is_file():
        raise RuntimeError('RUNNING_PRIVATE_IDENTITY_REQUIRED')
    pid = int(pidfile.read_text())
    process = Path('/proc') / str(pid)
    args = (process / 'cmdline').read_bytes().split(b'\0')
    if ('--datadir=' + str(data)).encode() not in args \
            or ('--socket=' + str(socket)).encode() not in args \
            or os.readlink(str(process / 'ns/net')) == os.readlink('/proc/1/ns/net'):
        raise RuntimeError('PRIVATE_PROCESS_IDENTITY_REQUIRED')
    base = ['--no-defaults', '--protocol=SOCKET', '--socket=' + str(socket), '--user=root']
    checked = subprocess.run(['mysql'] + base + ['--batch', '--skip-column-names', '-e',
        'SELECT @@datadir,@@skip_networking'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if checked.returncode or checked.stdout.strip().split('\t') != [str(data) + '/', '1']:
        raise RuntimeError('PRIVATE_MYSQL_IDENTITY_REQUIRED')
    result = subprocess.run(['mysqladmin'] + base + ['shutdown'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('PRIVATE_SHUTDOWN_FAILED')
    for _ in range(120):
        if not socket.exists() and not process.exists():
            return {'directory': str(directory), 'shutdown_verified': True,
                'data_files_preserved': (data / 'ibdata1').is_file()}
        time.sleep(0.25)
    raise RuntimeError('PRIVATE_SHUTDOWN_VERIFICATION_TIMEOUT')


if __name__ == '__main__':
    report = {'instances': [stop(WORK / 'sql-recovery-20261109/rehearsal-mysql'),
        stop(WORK / 'rehearsal-mysql')], 'live_mysql_accessed': False,
        'original_baseline_sha256': hashlib.sha256((WORK / 'original-data-checks.json').read_bytes()).hexdigest(),
        'original_checker_sha256': hashlib.sha256((WORK / 'rehearse_migrations.php').read_bytes()).hexdigest()}
    with (WORK / 'resume-final-status-20261109.json').open('x') as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps(report))
