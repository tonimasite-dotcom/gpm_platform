#!/usr/bin/env python3
"""Stop only the two verified private rehearsal/recovery MySQL instances."""
import hashlib
import argparse
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
    if not socket.exists() and not pidfile.exists():
        for candidate in Path('/proc').iterdir():
            if not candidate.name.isdigit():
                continue
            try:
                if ('--datadir=' + str(data)).encode() in (candidate / 'cmdline').read_bytes().split(b'\0'):
                    raise RuntimeError('PRIVATE_PROCESS_WITHOUT_EXPECTED_SOCKET')
            except OSError:
                pass
        return {'directory': str(directory), 'shutdown_verified': True,
            'already_stopped': True, 'data_files_preserved': True}
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-report', action='store_true')
    parser.add_argument('--order-form-report', action='store_true')
    options = parser.parse_args()
    if options.runtime_report and options.order_form_report:
        parser.error('Choose one report stage')
    filename = ('order-form-final-status-20261109.json' if options.order_form_report else
        'runtime-final-status-20261109.json' if options.runtime_report else 'resume-final-status-20261109.json')
    if (WORK / filename).exists():
        raise RuntimeError('REPORT_ALREADY_EXISTS_CHOOSE_NEW_STAGE')
    report = {'instances': [stop(WORK / 'sql-recovery-20261109/rehearsal-mysql'),
        stop(WORK / 'rehearsal-mysql')], 'live_mysql_accessed': False,
        'original_baseline_sha256': hashlib.sha256((WORK / 'original-data-checks.json').read_bytes()).hexdigest(),
        'original_checker_sha256': hashlib.sha256((WORK / 'rehearse_migrations.php').read_bytes()).hexdigest()}
    with (WORK / filename).open('x') as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps(report))
