#!/usr/bin/env python3
"""Verify only the preserved private candidate; never access a live CRM."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK/'candidate'
OUTPUT = WORK/'order-form-verification-20261109.json'


def private_php(name):
    env = dict(os.environ, GPM_TS_REHEARSAL='1')
    result = subprocess.run(['unshare', '--net', 'nice', '-n', '10', 'php', '-d',
        'memory_limit=512M', str(WORK/'acceptance-20261109/payload'/name)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=180)
    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise RuntimeError('PRIVATE_CHECK_FAILED_DETAILS_WITHHELD')
    if result.returncode:
        raise RuntimeError('PRIVATE_CHECK_REJECTED_DETAILS_WITHHELD')
    return report


def main():
    os.umask(0o077)
    if WORK.resolve() != WORK or ROOT.resolve() != ROOT or OUTPUT.exists():
        raise RuntimeError('FRESH_PRIVATE_REPORT_REQUIRED')
    if hashlib.sha256((WORK/'original-data-checks.json').read_bytes()).hexdigest() != \
            'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec':
        raise RuntimeError('ORIGINAL_BASELINE_HASH_MISMATCH')
    if hashlib.sha256((WORK/'rehearse_migrations.php').read_bytes()).hexdigest() != \
            '0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259':
        raise RuntimeError('ORIGINAL_CHECKER_HASH_MISMATCH')
    forms = private_php('order_form_acceptance.php')
    runtime = private_php('functional_acceptance.php')
    preserved = private_php('diagnose_original_data.php')
    if not forms.get('order_form_acceptance_passed') or not runtime.get('success') \
            or not preserved.get('saved_rehearsal_data_acceptance_passed'):
        raise RuntimeError('PRIVATE_ACCEPTANCE_FAILED')
    files = [p for folder in ['app', 'config', 'routes', 'database/migrations', 'bootstrap']
        for p in (ROOT/folder).rglob('*.php')]
    payloads = list((WORK/'acceptance-20261109/payload').glob('*.php'))
    for path in files + payloads:
        checked = subprocess.run(['php', '-l', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if checked.returncode:
            raise RuntimeError('PRIVATE_PHP_LINT_FAILED')
    regressions = {}
    for name in ['sync_plan_test.php', 'sync_service_test.php', 'worker_rate_test.php']:
        result = subprocess.run(['unshare', '--net', 'php', str(WORK/'regression/tests'/name)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=90)
        if result.returncode:
            raise RuntimeError('PRIVATE_GPM_REGRESSION_FAILED')
        regressions[name] = result.stdout.strip()
    report = {'checks_passed': True, 'order_forms': forms, 'previous_functional': runtime,
        'original_data': preserved, 'php_lint': {'candidate_files': len(files),
            'acceptance_files': len(payloads), 'success': True}, 'gpm_regressions': regressions,
        'main_crm_accessed': False, 'live_crm_changed': False, 'release_ready': False}
    with OUTPUT.open('x') as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps({'checks_passed': True, 'order_form_scenarios': forms['accepted_scenarios'],
        'previous_functional_scenarios': runtime['scenarios_passed'], 'php_candidate_files': len(files),
        'gpm_regressions': regressions, 'original_tables_checked': preserved['tables_checked'],
        'all_original_rows_preserved': preserved['all_original_rows_preserved'],
        'main_crm_accessed': False, 'live_crm_changed': False, 'release_ready': False}))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(json.dumps({'checks_passed': False, 'safe_code': str(error)}))
        raise SystemExit(1)
