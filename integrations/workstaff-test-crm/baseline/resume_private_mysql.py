#!/usr/bin/env python3
"""Resume ONLY the existing, network-isolated rehearsal; never initialize it."""
import json
import argparse
import os
import re
from pathlib import Path
import subprocess
import time

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
MYSQL = WORK / 'rehearsal-mysql'


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-name', default='resume-20261109.json')
    options = parser.parse_args()
    if not re.fullmatch(r'resume-[a-z0-9-]+\.json', options.report_name):
        raise RuntimeError('SAFE_RESUME_REPORT_NAME_REQUIRED')
    report_path = MYSQL / options.report_name
    if report_path.exists():
        raise RuntimeError('NEW_RESUME_REPORT_REQUIRED')
    data = MYSQL / 'data'
    socket = MYSQL / 'mysql.sock'
    for path in (WORK, MYSQL, data, data / 'ibdata1', MYSQL / 'identity.json'):
        if not path.exists() or path.resolve() != path:
            raise RuntimeError('SAVED_PRIVATE_DATABASE_REQUIRED')
    identity = json.loads((MYSQL / 'identity.json').read_text())
    if identity['datadir'] != str(data) or identity['socket'] != str(socket):
        raise RuntimeError('PRIVATE_IDENTITY_MISMATCH')
    if socket.exists() or socket.is_symlink() or (MYSQL / 'mysql.pid').exists():
        raise RuntimeError('PRIVATE_INSTANCE_MUST_BE_STOPPED')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
            if ('--datadir=' + str(data)).encode() in args:
                raise RuntimeError('PRIVATE_PROCESS_ALREADY_RUNNING')
        except OSError:
            pass
    command = ['unshare', '--net', 'nice', '-n', '10', '/usr/sbin/mysqld',
        '--no-defaults', '--user=root', '--datadir=' + str(data),
        '--log-error=' + str(MYSQL / 'mysql-error.log'),
        '--socket=' + str(socket), '--pid-file=' + str(MYSQL / 'mysql.pid'),
        '--skip-networking', '--skip-log-bin', '--performance-schema=OFF',
        '--innodb-buffer-pool-size=67108864', '--innodb-log-file-size=16777216',
        '--max-connections=12', '--innodb-flush-log-at-trx-commit=2',
        '--character-set-server=utf8mb4', '--collation-server=utf8mb4_unicode_ci']
    with (MYSQL / 'resume-20261109-daemon.log').open('ab') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
            stdout=output, stderr=output, start_new_session=True)
    client = ['mysql', '--no-defaults', '--protocol=SOCKET', '--socket=' + str(socket),
        '--user=root', '--batch', '--skip-column-names']
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError('PRIVATE_START_FAILED_DIAGNOSTICS_WITHHELD')
        if socket.exists():
            result = subprocess.run(client + ['-e',
                'SELECT @@datadir,@@skip_networking,VERSION()'], capture_output=True, text=True)
            if result.returncode == 0:
                values = result.stdout.strip().split('\t')
                if len(values) != 3 or Path(values[0]).resolve() != data or values[1] != '1' or not values[2].startswith('5.7.'):
                    raise RuntimeError('PRIVATE_RUNNING_IDENTITY_MISMATCH')
                pid = int((MYSQL / 'mysql.pid').read_text())
                namespace = os.readlink('/proc/' + str(pid) + '/ns/net')
                if pid != process.pid or namespace == os.readlink('/proc/1/ns/net'):
                    raise RuntimeError('PRIVATE_NETWORK_ISOLATION_MISSING')
                report = {'existing_private_mysql_resumed': True, 'initialized': False,
                    'dump_restored': False, 'network_disabled': True, 'pid': pid,
                    'network_namespace': namespace, 'live_mysql_accessed': False}
                with report_path.open('x') as stream:
                    stream.write(json.dumps(report, indent=2))
                print(json.dumps(report))
                return
        time.sleep(0.25)
    raise RuntimeError('PRIVATE_START_TIMEOUT')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = str(error) if type(error) is RuntimeError else 'PRIVATE_RESUME_FAILED'
        print(json.dumps({'success': False, 'error_code': code}))
        raise SystemExit(1)
