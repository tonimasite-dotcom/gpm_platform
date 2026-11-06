#!/usr/bin/env python3
"""Create a private, network-isolated MySQL instance for TS restore rehearsal.

Never connect to the system MySQL socket. No existing database or account is
changed. Preserve rehearsal files and stop only this instance after verification.
"""
from pathlib import Path
import json
import os
import secrets
import subprocess
import time

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
MYSQL = WORK / 'rehearsal-mysql'
DATABASE = 'gpm_ts_rehearsal_20261106'
ACCOUNT = 'gpm_ts_rehearsal'


def main():
    os.umask(0o077)
    if WORK.resolve() != WORK or MYSQL.exists():
        raise RuntimeError('Unsafe or existing rehearsal root')
    MYSQL.mkdir(mode=0o700)
    data = MYSQL / 'data';data.mkdir(mode=0o700)
    socket = MYSQL / 'mysql.sock'
    log = MYSQL / 'mysql-error.log'
    common = ['/usr/sbin/mysqld', '--no-defaults', '--user=root', '--datadir=' + str(data),
              '--log-error=' + str(log)]
    init = subprocess.run(['unshare', '--net'] + common + ['--initialize-insecure'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if init.returncode: raise RuntimeError('Private MySQL initialization failed')
    with (MYSQL / 'daemon.log').open('ab') as out:
        process = subprocess.Popen(['unshare', '--net', 'nice', '-n', '10'] + common + [
            '--socket=' + str(socket), '--pid-file=' + str(MYSQL / 'mysql.pid'),
            '--skip-networking', '--skip-log-bin', '--performance-schema=OFF',
            '--innodb-buffer-pool-size=67108864', '--innodb-log-file-size=16777216',
            '--max-connections=12', '--innodb-flush-log-at-trx-commit=2',
            '--character-set-server=utf8mb4', '--collation-server=utf8mb4_unicode_ci'],
            stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
    command = ['mysql', '--no-defaults', '--protocol=SOCKET', '--socket=' + str(socket),
               '--user=root', '--batch', '--skip-column-names']
    ready = False
    for _ in range(60):
        if process.poll() is not None: raise RuntimeError('Private MySQL exited during startup')
        if socket.exists():
            check = subprocess.run(command + ['-e', 'SELECT @@datadir'], capture_output=True, text=True)
            if check.returncode == 0 and Path(check.stdout.strip()).resolve() == data:
                ready = True;break
        time.sleep(0.25)
    if not ready: raise RuntimeError('Private MySQL startup timed out')
    password = secrets.token_hex(24)
    sql = ("CREATE DATABASE `" + DATABASE + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
           "CREATE USER '" + ACCOUNT + "'@'localhost' IDENTIFIED BY '" + password + "';"
           "GRANT ALL PRIVILEGES ON `" + DATABASE + "`.* TO '" + ACCOUNT + "'@'localhost';")
    result = subprocess.run(command, input=sql.encode(), capture_output=True)
    if result.returncode: raise RuntimeError('Private rehearsal schema/account creation failed')
    identity = {'datadir': str(data), 'socket': str(socket), 'database': DATABASE,
                'username': ACCOUNT, 'password': password, 'pid': process.pid,
                'network_namespace': os.readlink('/proc/' + str(process.pid) + '/ns/net'),
                'host_network_namespace': os.readlink('/proc/1/ns/net')}
    if identity['network_namespace'] == identity['host_network_namespace']:
        raise RuntimeError('Private MySQL network isolation missing')
    (MYSQL / 'identity.json').write_text(json.dumps(identity))
    print(json.dumps({'private_mysql_ready': True, 'network_disabled': True,
                      'live_mysql_accessed': False, 'workspace': str(MYSQL)}))


if __name__ == '__main__': main()
