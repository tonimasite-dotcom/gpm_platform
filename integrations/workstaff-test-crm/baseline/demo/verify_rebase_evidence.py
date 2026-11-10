#!/usr/bin/env python3
"""Pin reused GPM results and lint current helpers; no jobs, DB or app bootstrap."""
from pathlib import Path
import hashlib
import json
import subprocess

OLD = Path('/root/gpm-ts-update/20261110-demo-04')
NEW = Path('/root/gpm-ts-update/20261110-demo-05')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = NEW / 'gpm-equivalence.json'
    if target.exists():
        raise RuntimeError('NEW_EQUIVALENCE_REPORT_REQUIRED')
    evidence = json.loads((NEW / 'auth-equivalence.json').read_text())
    original = OLD / 'gpm-regression.json'
    report = json.loads(original.read_text())
    if not report['passed']:
        raise RuntimeError('PRIOR_GPM_ACCEPTANCE_REQUIRED')
    rows = []
    for name in evidence['gpm_files_byte_identical']:
        same = sha(OLD / 'runtime' / name) == sha(NEW / 'runtime' / name)
        if not same:
            raise RuntimeError('GPM_LOGIC_CHANGED')
        rows.append({'file': name, 'sha256': sha(NEW / 'runtime' / name)})
    tools = Path(__file__).parent
    linted = 0
    for path in tools.rglob('*.php'):
        result = subprocess.run(['/opt/php74/bin/php', '-l', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('PHP74_HELPER_LINT_FAILED')
        linted += 1
    value = {'passed': True, 'kind': 'code_equivalence_not_new_gpm_execution',
             'source_report': str(original), 'source_report_sha256': sha(original),
             'tests_reused': report['tests'], 'byte_identical_files': rows,
             'php74_helpers_linted': linted, 'live_sync_executed': False,
             'database_accessed': False, 'live_files_changed': False}
    with target.open('x') as out:
        out.write(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
