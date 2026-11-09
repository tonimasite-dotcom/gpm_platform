#!/usr/bin/env python3
"""Run private document generation with isolated cwd, files and office profile."""
from pathlib import Path
import json
import os
import secrets
import subprocess

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')


def main():
    os.umask(0o077)
    if WORK.resolve() != WORK:
        raise RuntimeError('PRIVATE_WORK_ROOT_REQUIRED')
    fixture = WORK/('document-fixtures-20261109-' + secrets.token_hex(6))
    fixture.mkdir(mode=0o700)
    for folder in ['public', 'config', 'cache', 'tmp']:
        (fixture/folder).mkdir(mode=0o700)
    env = dict(os.environ, GPM_TS_REHEARSAL='1', GPM_TS_DOCUMENT_FIXTURE=str(fixture),
        XDG_CONFIG_HOME=str(fixture/'config'), XDG_CACHE_HOME=str(fixture/'cache'), TMPDIR=str(fixture/'tmp'))
    try:
        result = subprocess.run(['unshare', '--net', 'nice', '-n', '10', 'php', '-d', 'memory_limit=512M',
            str(WORK/'acceptance-20261109/payload/document_acceptance.php')], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError('PRIVATE_DOCUMENT_TEST_TIMEOUT')
    (fixture/'stdout-private.log').write_text(result.stdout)
    (fixture/'stderr-private.log').write_text(result.stderr)
    try:
        report = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('PRIVATE_DOCUMENT_DIAGNOSTICS_WITHHELD')
    print(json.dumps(report))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(json.dumps({'success': False, 'safe_code': str(error)}))
        raise SystemExit(1)
