#!/usr/bin/env python3
"""Release the explicitly requested three-file debt shutdown, not the auth package."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
WORK = Path('/root/gpm-ts-update/20261110-debt-off-01')
TOOLS = Path(__file__).parent
sys.path.insert(0, '/root/gpm-ts-update/demo-tools-20261110')
from apply_code import install
# The unchanged FastCGI helper is copied beside these scope-specific PHP probes.
import importlib.util
spec = importlib.util.spec_from_file_location('debt_fpm', str(TOOLS / 'fpm_probe.py'))
fpm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fpm)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    manifest = json.loads((WORK / 'manifest.json').read_text())
    backup = Path(manifest['backup_artifact'])
    if (TS.resolve() != TS or sha(backup) != manifest['backup_sha256']
        or not 0 <= time.time() - (backup.parent / 'verification.json').stat().st_mtime < 86400):
        raise RuntimeError('EXACT_TS_AND_FRESH_BACKUP_REQUIRED')
    for row in manifest['files']:
        if sha(TS / row['file']) != row['before_sha256'] or sha(WORK / 'runtime' / row['file']) != row['after_sha256']:
            raise RuntimeError('SOURCE_DRIFT_REVIEW_REQUIRED')
    for name, expected in manifest['protected_files'].items():
        if sha(TS / name) != expected:
            raise RuntimeError('PROTECTED_FILE_DRIFT_REVIEW_REQUIRED')
    if sha(Path('/etc/cron.d/gpm-test-crm-sync')) != manifest['sync_cron_sha256']:
        raise RuntimeError('SYNC_CRON_CHANGED')
    # No old in-flight debt/scheduler/queue process may keep old PHP code alive.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if str(TS) in command or (proc / 'cwd').resolve() == TS:
                if any(name in command for name in ['debit:', 'command:checkCustomerDebit', 'queue:work', 'queue:listen', 'schedule:run', 'schedule:work']):
                    raise RuntimeError('OLD_TS_AUTOMATION_PROCESS_ACTIVE')
        except (FileNotFoundError, PermissionError):
            pass
    return manifest


def rehearsal():
    parent = WORK / 'rehearsal'
    if parent.exists():
        raise RuntimeError('NEW_REHEARSAL_REQUIRED')
    parent.mkdir(mode=0o700)
    manifest = preflight(); rows = manifest['files']; checks = []
    for boundary in range(4):
        root = parent / ('failure-%d' % boundary)
        (root / 'storage/framework').mkdir(parents=True)
        for row in rows:
            target = root / row['file']; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TS / row['file'], target)
        state = root.parent / ('state-%d.json' % boundary)
        callback = lambda *args: {'passed': True, 'fixture': True}
        try:
            install(root, WORK / 'runtime', rows, state, callback, callback, fail_after=boundary)
            raise AssertionError('FAILURE_NOT_INJECTED')
        except RuntimeError as error:
            if str(error) != 'INJECTED_INSTALL_FAILURE':
                raise
        if not (root / 'storage/framework/down').exists():
            raise RuntimeError('FAILED_INSTALL_NOT_HELD')
        (parent / ('failure-state-%d.json' % boundary)).write_bytes(state.read_bytes())
        done = install(root, WORK / 'runtime', rows, state, callback, callback, resume=True)
        if not done['complete'] or (root / 'storage/framework/down').exists():
            raise RuntimeError('PRIVATE_RESUME_FAILED')
        checks.append('failure_%d_held_and_resumed' % boundary)
    report = {'passed': True, 'checks': checks, 'live_files_changed': False}
    (WORK / 'rehearsal.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rehearse', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--manifest-sha')
    args = parser.parse_args()
    if args.rehearse:
        print(json.dumps(rehearsal())); return
    manifest = preflight()
    fingerprint = sha(WORK / 'manifest.json')
    if not args.apply:
        print(json.dumps({'dry_run_passed': True, 'files': 3, 'manifest_sha256': fingerprint,
                          'backup_sha256': manifest['backup_sha256'], 'live_files_changed': False})); return
    if args.manifest_sha != fingerprint or not json.loads((WORK / 'rehearsal.json').read_text())['passed']:
        raise RuntimeError('TESTED_EXACT_MANIFEST_REQUIRED')
    def invalidate(rows):
        return fpm.run_probe('fpm_invalidate.php', rows)
    def probe():
        return fpm.run_probe('fpm_runtime_probe.php')
    def http():
        responses = {}
        for uri, expected in [('/api/user', 401), ('/', 200)]:
            response = fpm.request(TS / 'public/index.php', '', {'SCRIPT_NAME': '/index.php', 'REQUEST_URI': uri,
                'HTTP_ACCEPT': 'application/json' if uri.startswith('/api/') else 'text/html',
                'HTTPS': 'on', 'SERVER_PORT': '443'}, metadata_only=True)
            responses[uri] = response
            if response['status'] != expected:
                return {'passed': False, 'responses': responses}
        return {'passed': True, 'responses': responses}
    started = time.monotonic()
    state = install(TS, WORK / 'runtime', manifest['files'], WORK / 'live-install-state.json',
                    invalidate, probe, post_probe=http)
    for name, expected in manifest['protected_files'].items():
        if sha(TS / name) != expected:
            raise RuntimeError('PROTECTED_FILE_CHANGED')
    if sha(Path('/etc/cron.d/gpm-test-crm-sync')) != manifest['sync_cron_sha256']:
        raise RuntimeError('SYNC_CRON_CHANGED')
    receipt = {'passed': state['complete'], 'manifest_sha256': fingerprint,
               'elapsed_seconds': round(time.monotonic() - started, 3), 'files_changed': 3,
               'guarded_methods': 4, 'fpm_handlers': state['runtime_probe'], 'http': state['http_acceptance'],
               'protected_files_unchanged': True, 'sync_cron_unchanged': True,
               'maintenance_held': state['maintenance_held'], 'authorization_changed': False,
               'database_jobs_or_migrations_executed': False, 'main_crm_accessed': False,
               'shared_services_reloaded': False}
    (WORK / 'deployment.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'TS_DEBT_RELEASE_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
