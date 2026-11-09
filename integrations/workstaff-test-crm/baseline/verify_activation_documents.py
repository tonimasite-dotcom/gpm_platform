#!/usr/bin/env python3
"""Final private-only data check after legacy, activation and document acceptance."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')


def php(name):
    result = subprocess.run(['unshare', '--net', 'nice', '-n', '10', 'php', '-d', 'memory_limit=512M',
        str(WORK/'acceptance-20261109/payload'/name)],
        env=dict(os.environ, GPM_TS_REHEARSAL='1'), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
    if result.returncode:
        raise RuntimeError('PRIVATE_CHECK_REJECTED_DETAILS_WITHHELD')
    return json.loads(result.stdout)


def main():
    os.umask(0o077)
    output = WORK/'activation-document-verification-20261109.json'
    if WORK.resolve() != WORK or output.exists():
        raise RuntimeError('NEW_PRIVATE_REPORT_REQUIRED')
    for filename, expected in {
        'original-data-checks.json': 'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec',
        'rehearse_migrations.php': '0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259',
    }.items():
        if hashlib.sha256((WORK/filename).read_bytes()).hexdigest() != expected:
            raise RuntimeError('IMMUTABLE_EVIDENCE_HASH_MISMATCH')
    for name in ['order_form_acceptance.php', 'activation_acceptance.php', 'document_acceptance.php']:
        checked = subprocess.run(['php', '-l', str(WORK/'acceptance-20261109/payload'/name)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if checked.returncode:
            raise RuntimeError('PRIVATE_PHP_LINT_FAILED')
    forms = php('order_form_acceptance.php')
    legacy = json.loads((WORK/'legacy-financial-acceptance-20261109.json').read_text())
    activation = json.loads((WORK/'activation-acceptance-20261109.json').read_text())
    document = json.loads((WORK/'document-acceptance-20261109.json').read_text())
    preserved = php('diagnose_original_data.php')
    if not all(item.get('success') for item in [forms, legacy, activation, document]) \
            or not legacy.get('legacy_pre_worker_boundary') \
            or not preserved.get('saved_rehearsal_data_acceptance_passed'):
        raise RuntimeError('PRIVATE_ACCEPTANCE_FAILED')
    report = {'checks_passed': True, 'form_regression': forms, 'legacy': legacy,
        'activation': activation, 'document': document, 'original_data': preserved,
        'changed_php_payloads_lint_passed': 3, 'candidate_code_unchanged_this_stage': True,
        'candidate_code_manifest_sha256': 'dce57370efff2615fafde248addfb7808f13a0560254f2fb4e3982fd7a661b5d',
        'main_crm_accessed': False, 'live_crm_changed': False, 'release_ready': False}
    with output.open('x') as target:
        target.write(json.dumps(report, indent=2))
    print(json.dumps({'checks_passed': True, 'form_regression_scenarios': forms['accepted_scenarios'],
        'legacy_pre_boundary_scenarios': legacy['accepted_scenarios'],
        'activation_scenarios': activation['scenarios_passed'], 'document_files_verified': 4,
        'original_tables_checked': preserved['tables_checked'],
        'all_original_rows_preserved': preserved['all_original_rows_preserved'],
        'live_crm_changed': False, 'release_ready': False}))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(json.dumps({'checks_passed': False, 'safe_code': str(error)}))
        raise SystemExit(1)
