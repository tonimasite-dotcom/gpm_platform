#!/usr/bin/env python3
"""Reviewable dry-run only. No live file replacement or automatic deployment."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PRIVATE = Path('/root/gpm-ts-update/20261110-demo-06')
BACKUP = Path('/root/gpm-ts-update/20261110-demo-06/code-backup')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if TS.resolve() != TS or PRIVATE.resolve() != PRIVATE:
        raise RuntimeError('EXACT_TS_PATH_REQUIRED')
    path = PRIVATE / 'manifest.json'
    manifest = json.loads(path.read_text())
    current = subprocess.run(['python3', str(Path(__file__).parent / 'read_release_preflight.py')],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if current.returncode:
        raise RuntimeError('LIVE_READ_ONLY_PREFLIGHT_REQUIRED')
    live = json.loads(current.stdout)
    if live['composer_classmap_authoritative'] or live['ts_long_running_or_scheduled_workers']:
        raise RuntimeError('TS_WORKERS_OR_AUTOLOAD_REQUIRE_REVIEW')
    if (not live['immutable_original_baseline_preserved'] or not live['immutable_original_checker_preserved']
        or live['existing_sync_cron_sha256'] != '113d98c6d51bc04f4d8f8dfc12814402bec01b061127445f394b4afbf60c2365'):
        raise RuntimeError('ORIGINAL_CHECKPOINT_OR_SYNC_CRON_CHANGED_REVIEW_REQUIRED')
    if not live['all_protected_files_match_saved_baseline'] or not live['all_live_targets_match_saved_baseline']:
        raise RuntimeError('PROTECTED_OR_TARGET_CODE_CHANGED')
    backup = json.loads((BACKUP / 'verification.json').read_text())
    restore = json.loads((PRIVATE / 'code-backup-restore.json').read_text())
    if sha(Path(backup['artifact'])) != backup['sha256'] or restore['encrypted_sha256'] != backup['sha256']:
        raise RuntimeError('BACKUP_HASH_MISMATCH')
    if not restore['passed'] or not restore['all_restored_sha256_match']:
        raise RuntimeError('BACKUP_RESTORE_NOT_VERIFIED')
    backup_age = time.time() - (BACKUP / 'verification.json').stat().st_mtime
    if backup_age < 0 or backup_age > 24 * 3600:
        raise RuntimeError('FRESH_CODE_BACKUP_REQUIRED')
    rows = []
    for row in manifest['files']:
        current = TS / row['file']
        staged = PRIVATE / 'runtime' / row['file']
        if current.is_symlink() or current.resolve() != current or staged.resolve() != staged:
            raise RuntimeError('TARGET_SYMLINK_REJECTED')
        observed = sha(current) if current.is_file() else None
        if observed != row['before_sha256'] or sha(staged) != row['after_sha256']:
            raise RuntimeError('CODE_CHANGED_REVIEW_REQUIRED')
        saved = next(item for item in backup['files'] if item['file'] == row['file'])
        if saved['existed'] != current.is_file() or (saved['existed'] and saved['sha256'] != observed):
            raise RuntimeError('BACKUP_DOES_NOT_COVER_TARGET')
        lint = subprocess.run(['/opt/php74/bin/php', '-l', str(staged)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if lint.returncode:
            raise RuntimeError('PHP_LINT_FAILED_DETAILS_WITHHELD')
        rows.append({'file': row['file'], 'new_file': observed is None,
                     'before_sha256': observed, 'after_sha256': row['after_sha256']})
    reports = {}
    for label, file in [('auth_preserved', 'auth-preserved.json'), ('gpm_code_equivalence', 'gpm-equivalence.json'), ('transport', 'transport-acceptance.json'),
                        ('installation', 'install-rehearsal.json')]:
        reports[label] = json.loads((PRIVATE / file).read_text()).get('passed', False)
    if not all(reports.values()):
        raise RuntimeError('PRIVATE_ACCEPTANCE_NOT_COMPLETE')
    preserved = json.loads((PRIVATE / 'auth-preserved.json').read_text())
    if sha(TS / preserved['controller']) != preserved['controller_sha256']:
        raise RuntimeError('LOGIN_CONTROLLER_CHANGED')
    if sha(TS / preserved['login_view']) != preserved['login_view_sha256']:
        raise RuntimeError('LOGIN_EMAIL_TEMPLATE_CHANGED')
    gpm = json.loads((PRIVATE / 'gpm-equivalence.json').read_text())
    if sha(Path(gpm['source_report'])) != gpm['source_report_sha256']:
        raise RuntimeError('PRIOR_GPM_EVIDENCE_CHANGED')
    report = {'dry_run_passed': True, 'manifest_sha256': sha(path), 'files': rows,
              'private_acceptance': reports,
              'login_controller_unchanged_and_email_delivery_tested': True,
              'fresh_targeted_encrypted_backup_restored': True,
              'database_backup_needed_for_this_code_only_package': False,
              'apply_implemented': True, 'live_files_changed': False,
              'release_ready': False,
              'remaining_before_live_apply': [
                  'Current owner instruction: keep existing email login; no auth changes',
                  'Live apply and HTTP verification through TS FPM socket during the agreed short TS maintenance window',
                  'Manual browser login using ordinary email codes and app-to-TS acceptance on designated test data'],
              'apply_order': ['Keep original data/schema/accounts/env/cron',
                              'Create two new release classes first; provider then guarded caller files',
                              'Preserve exact file owners/modes and use atomic per-file replacement',
                              'Invalidate only these TS opcache entries through its socket; no global reset',
                              'Check demo response marker plus auth denials; preserve GPM sync cron',
                              'Never restore an SMTP-capable baseline while claiming daily mail remains OFF']}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'dry_run_passed': False, 'safe_error': 'RELEASE_PLAN_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
