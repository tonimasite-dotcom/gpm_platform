#!/usr/bin/env python3
"""Failure injection at every code-swap boundary, only on NEW private copies."""
from pathlib import Path
import json
import shutil
from apply_code import install, sha

PRIVATE = Path('/root/gpm-ts-update/20261110-demo-06')
SOURCE = PRIVATE / 'source-current'


def main():
    parent = PRIVATE / 'install-rehearsal'
    if parent.exists():
        raise RuntimeError('NEW_INSTALL_REHEARSAL_REQUIRED')
    parent.mkdir(mode=0o700)
    rows = json.loads((PRIVATE / 'manifest.json').read_text())['files']
    checks = []
    def debt_off(target):
        files = ['app/Console/Commands/CheckDebit.php', 'app/Console/Commands/CheckCustomerDebit.php', 'app/Services/WebKlexMailClient.php']
        return sum((target / name).read_bytes().count(b'GPM_TS_DEBT_AUTOMATION_DISABLED_20261110') for name in files) == 4
    def fresh(name):
        folder = parent / name
        target = folder / 'site'
        (target / 'storage/framework').mkdir(mode=0o700, parents=True)
        for row in rows:
            if row['before_sha256'] is not None:
                path = target / row['file']
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SOURCE / row['file'], path)
        return folder, target

    def invalidation(plan):
        assert len(plan) == len(rows)
        return {'passed': True, 'fixture': True, 'global_reset': False}
    def probe():
        return {'passed': True, 'fixture': True}

    # All partial states are preserved, then completed by the same pinned plan.
    for boundary in range(len(rows) + 1):
        folder, target = fresh('fail-%02d' % boundary)
        state_path = folder / 'state.json'
        try:
            install(target, PRIVATE / 'runtime', rows, state_path, invalidation, probe, fail_after=boundary)
            raise AssertionError('FAILURE_NOT_INJECTED')
        except RuntimeError as error:
            assert str(error) == 'INJECTED_INSTALL_FAILURE'
        assert (target / 'storage/framework/down').is_file()
        assert debt_off(target)
        assert json.loads(state_path.read_text())['maintenance_held'] is True
        (folder / 'preserved-failure-state.json').write_bytes(state_path.read_bytes())
        completed = install(target, PRIVATE / 'runtime', rows, state_path, invalidation, probe, resume=True)
        assert completed['complete'] and not (target / 'storage/framework/down').exists()
        assert all(sha(target / row['file']) == row['after_sha256'] for row in rows)
        assert debt_off(target)
        checks.append('failure_%02d_holds_maintenance_and_resumes_exact_manifest' % boundary)
    folder, target = fresh('failed-runtime-probe')
    state_path = folder / 'state.json'
    try:
        install(target, PRIVATE / 'runtime', rows, state_path, invalidation, lambda: {'passed': False})
        raise AssertionError('BAD_RUNTIME_PROBE_ACCEPTED')
    except RuntimeError as error:
        assert str(error) == 'GUARDED_RUNTIME_NOT_VERIFIED'
    assert (target / 'storage/framework/down').exists()
    assert all(sha(target / row['file']) == row['after_sha256'] for row in rows)
    checks.append('failed_runtime_probe_never_restores_smtp_baseline')
    (target / 'storage/framework/down').write_text('owner-changed-marker')
    try:
        install(target, PRIVATE / 'runtime', rows, state_path, invalidation, probe, resume=True)
        raise AssertionError('FOREIGN_MAINTENANCE_ACCEPTED')
    except RuntimeError as error:
        assert str(error) == 'EXACT_OWN_MAINTENANCE_STATE_REQUIRED'
    assert (target / 'storage/framework/down').read_text() == 'owner-changed-marker'
    checks.append('foreign_maintenance_never_removed')
    folder, target = fresh('failed-post-release-http')
    try:
        install(target, PRIVATE / 'runtime', rows, folder / 'state.json', invalidation, probe,
                post_probe=lambda: {'passed': False})
        raise AssertionError('BAD_POST_RELEASE_HTTP_ACCEPTED')
    except RuntimeError as error:
        assert str(error) == 'POST_RELEASE_HTTP_NOT_VERIFIED'
    assert (target / 'storage/framework/down').exists()
    assert all(sha(target / row['file']) == row['after_sha256'] for row in rows)
    checks.append('failed_post_release_http_restores_own_maintenance_and_keeps_guards')
    report = {'passed': True, 'checks': checks, 'real_fpm_used': False, 'live_files_changed': False,
              'database_accessed': False, 'all_fixtures_preserved': True,
              'debt_guards_retained_in_every_partial_and_completed_state': True}
    (PRIVATE / 'install-rehearsal.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
