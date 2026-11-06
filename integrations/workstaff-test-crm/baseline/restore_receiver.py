#!/usr/bin/env python3
"""Receive plaintext only on SSH stdin into a new private rehearsal MySQL.

The system socket and running CRM are never accessed. Refuse a nonempty target;
there is no destructive reset, table deletion or fallback connection mode.
"""
from pathlib import Path
import json
import subprocess
import sys

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')


def main():
    identity = json.loads((WORK / 'rehearsal-mysql/identity.json').read_text())
    socket = Path(identity['socket']);data = Path(identity['datadir'])
    if socket.parent != WORK / 'rehearsal-mysql' or data != WORK / 'rehearsal-mysql/data':
        raise RuntimeError('Unexpected private database identity')
    if socket.parent.resolve() != socket.parent:
        raise RuntimeError('Unsafe private socket directory')
    command = ['mysql', '--no-defaults', '--protocol=SOCKET', '--socket=' + str(socket),
               '--user=root', '--batch', '--skip-column-names', '--default-character-set=utf8mb4',
               '--database=' + identity['database']]
    def query(sql):
        result = subprocess.run(command + ['-e', sql], capture_output=True, text=True)
        if result.returncode: raise RuntimeError('Private database query failed')
        return result.stdout.strip()
    if Path(query('SELECT @@datadir')).resolve() != data:
        raise RuntimeError('Not the private MySQL process')
    if query('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()') != '0':
        raise RuntimeError('Rehearsal target not empty; do not reset or delete it')
    result = subprocess.run(command, stdin=sys.stdin.buffer, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode: raise RuntimeError('Private restore failed; inspect privately without logging business SQL')
    tables = query('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()').splitlines()
    counts = {}
    for table in tables:
        if not table.replace('_', '').isalnum(): raise RuntimeError('Unexpected table identifier')
        counts[table] = int(query('SELECT COUNT(*) FROM `' + table + '`'))
    report = {'restore_completed': True, 'table_count': len(tables), 'row_counts': counts,
              'live_database_accessed': False, 'private_database': identity['database']}
    (WORK / 'rehearsal-mysql/restore-result.json').write_text(json.dumps(report))
    print(json.dumps(report))


if __name__ == '__main__': main()
