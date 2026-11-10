#!/usr/bin/env python3
"""Run existing failure-injection tests against actual files in the new overlay."""
from pathlib import Path
import json
import os
import re
import subprocess

RUNTIME = Path('/root/gpm-ts-update/20261110-demo-04/runtime')
DEST = RUNTIME.parent / 'regression-fixtures'


def main():
    os.umask(0o077)
    if DEST.exists() or RUNTIME.resolve() != RUNTIME or (RUNTIME / '.env').exists():
        raise RuntimeError('NEW_ISOLATED_FIXTURE_TARGET_REQUIRED')
    DEST.mkdir(mode=0o700)
    results = []
    source = Path(__file__).parent / 'fixtures'
    for name in ['sync_plan_test.php', 'sync_service_test.php', 'worker_rate_test.php']:
        text = (source / name).read_text()
        text, count = re.subn(r"__DIR__ \. '/../(?:worker-rate/)?app/", "'" + str(RUNTIME / 'app') + '/', text)
        if count not in [1, 2]:
            raise RuntimeError('FIXTURE_IMPORTS_NOT_REBOUND')
        path = DEST / name
        path.write_text(text)
        result = subprocess.run(['unshare', '--net', '/opt/php74/bin/php', str(path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            (DEST / (name + '.private-error')).write_bytes(result.stdout + result.stderr)
            raise RuntimeError('REGRESSION_FAILED:' + name)
        output = result.stdout.decode().strip()
        if not re.fullmatch(r'GPM (?:sync planner|sync service|worker rate): [0-9]+ scenarios passed', output):
            raise RuntimeError('UNEXPECTED_REGRESSION_OUTPUT')
        results.append({'test': name, 'result': output, 'actual_overlay_sources': True})
    report = {'passed': True, 'tests': results, 'external_network': False,
              'live_files_changed': False, 'live_sync_executed': False, 'database_accessed': False}
    (RUNTIME.parent / 'gpm-regression.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
