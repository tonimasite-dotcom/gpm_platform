#!/usr/bin/env python3
"""New private package; retain every live debt guard and preserve old artifacts."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
from prepare_demo import inject

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
OLD = Path('/root/gpm-ts-update/20261110-demo-04')
NEW = Path('/root/gpm-ts-update/20261110-demo-05')
SAVED = Path('/root/gpm-ts-update/20261106-baseline-01/source-ts')
DEBT = Path('/root/gpm-ts-update/20261110-debt-off-01')
MARKER = b'GPM_TS_DEBT_AUTOMATION_DISABLED_20261110'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    os.umask(0o077)
    if NEW.exists() or NEW.is_symlink() or TS.resolve() != TS or OLD.resolve() != OLD:
        raise RuntimeError('NEW_CANONICAL_REBASE_REQUIRED')
    old = json.loads((OLD / 'manifest.json').read_text())
    debt = json.loads((DEBT / 'manifest.json').read_text())
    if not json.loads((DEBT / 'deployment.json').read_text())['passed']:
        raise RuntimeError('VERIFIED_DEBT_RELEASE_REQUIRED')
    changed = {row['file']: row for row in debt['files']}
    # No drift outside the three explicitly released files is accepted.
    for row in old['files']:
        file = TS / row['file']
        expected = changed[row['file']]['after_sha256'] if row['file'] in changed else row['before_sha256']
        if file.resolve() != file or sha(file) != expected:
            raise RuntimeError('UNREVIEWED_LIVE_DRIFT:' + row['file'])
        if sha(OLD / 'runtime' / row['file']) != row['after_sha256']:
            raise RuntimeError('OLD_TESTED_OVERLAY_CHANGED')
    for name, expected in debt['protected_files'].items():
        if sha(TS / name) != expected:
            raise RuntimeError('PROTECTED_LIVE_DRIFT')
    NEW.mkdir(mode=0o700)
    source = NEW / 'source-current'
    shutil.copytree(SAVED, source)
    for name in changed:
        (source / name).write_bytes((TS / name).read_bytes())
    runtime = NEW / 'runtime'
    shutil.copytree(source, runtime)
    for row in old['files']:
        target = runtime / row['file']
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(OLD / 'runtime' / row['file'], target)
    debt_retained = {}
    for name, debt_row in changed.items():
        data = (source / name).read_bytes()
        for method, body in old['guards'][name].items():
            data = inject(data, method, body)
        (runtime / name).write_bytes(data)
        # The only additions to the previously tested after-code are the exact
        # already-deployed debt guards; no auth or other method may drift.
        original = (SAVED / name).read_bytes()
        before = (source / name).read_bytes()
        edits = []
        for value in ['0', '']:
            edit = ("\n        // GPM_TS_DEBT_AUTOMATION_DISABLED_20261110: no calculation or debtor email.\n"
                    "        if (realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'\n"
                    "            || rtrim((string) config('app.url'), '/') === 'https://ts.workstaffcrm.ru') {\n"
                    "            return" + (' ' + value if value else '') + ";\n        }\n").encode()
            if edit in before:
                edits.append(edit)
        stripped_before = before
        for edit in edits:
            stripped_before = stripped_before.replace(edit, b'', 1)
        if len(edits) != len(debt_row['guarded_methods']) or stripped_before != original:
            raise RuntimeError('LIVE_DEBT_DIFF_NOT_EXACT_REVIEWED_INSERTS')
        stripped = data
        for edit in edits:
            if stripped.count(edit) != 1:
                raise RuntimeError('DEBT_INSERT_NOT_UNIQUE')
            stripped = stripped.replace(edit, b'', 1)
        if stripped != (OLD / 'runtime' / name).read_bytes():
            raise RuntimeError('REBASE_CHANGED_MORE_THAN_DEBT_GUARD')
        debt_retained[name] = data.count(MARKER)
    release = runtime / 'app/Services/Release'
    policy = Path(__file__).parent / 'payload/GpmTsDemoPolicy.php'
    (release / policy.name).write_bytes(policy.read_bytes())
    expected_policy = (OLD / 'runtime/app/Services/Release/GpmTsDemoPolicy.php').read_bytes().replace(
        b'20261110-demo-04', b'20261110-demo-05').replace(b'ts-demo-20261110-04', b'ts-demo-20261110-05')
    if policy.read_bytes() != expected_policy:
        raise RuntimeError('POLICY_CHANGED_BEYOND_PROFILE_AND_VERSION')
    (runtime / 'PRIVATE_DEMO_NO_DATABASE').write_text('Transport acceptance: no DB; previously verified auth logic is unchanged.\n')
    manifest = copy.deepcopy(old)
    manifest.update({'base': str(source), 'target': str(runtime),
                     'rebased_from_manifest_sha256': sha(OLD / 'manifest.json'),
                     'standalone_debt_guards_retained': debt_retained,
                     'nonselected_source_is_saved_reference': True})
    after_changed = []
    for row in manifest['files']:
        name = row['file']
        row['before_sha256'] = sha(TS / name)
        row['after_sha256'] = sha(runtime / name)
        if row['after_sha256'] != next(item for item in old['files'] if item['file'] == name)['after_sha256']:
            after_changed.append(name)
        subprocess.run(['/opt/php74/bin/php', '-l', str(runtime / name)], check=True, stdout=subprocess.DEVNULL)
    if len(after_changed) != 4 or sum(debt_retained.values()) != 4:
        raise RuntimeError('UNEXPECTED_REBASE_SCOPE')
    (NEW / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    unchanged_auth = ['app/Http/Controllers/Auth/LoginController.php',
                      'app/Services/Release/GpmTsDemoLoginInbox.php', 'app/Services/Release/GpmTsDemoTransport.php']
    unchanged_gpm = ['app/Services/Order/GpmAppOrderSync.php', 'app/Services/Order/GpmAppOrderPublisher.php',
                     'app/Services/Order/GpmOrderSyncPlan.php', 'app/Services/Order/GpmWorkerRateRules.php',
                     'app/Services/Order/GpmLogistOrderGuard.php', 'app/Http/Controllers/Order/GpmWorkerRateController.php']
    for name in unchanged_auth + unchanged_gpm:
        if sha(runtime / name) != sha(OLD / 'runtime' / name):
            raise RuntimeError('AUTH_OR_GPM_LOGIC_CHANGED')
    evidence = {'passed': True, 'kind': 'code_equivalence_not_a_new_auth_execution',
                'source_auth_report': str(OLD / 'login-acceptance-02.json'),
                'source_auth_report_sha256': sha(OLD / 'login-acceptance-02.json'),
                'auth_files_byte_identical': unchanged_auth,
                'gpm_files_byte_identical': unchanged_gpm,
                'webklex_diff_only_retained_debt_guard': True,
                'policy_diff_only_private_profile_and_version': True,
                'auth_scenarios_reused': 14, 'gpm_scenarios_reused': [11, 16, 35],
                'private_mysql_started': False, 'live_files_changed': False}
    if not json.loads((OLD / 'login-acceptance-02.json').read_text())['passed']:
        raise RuntimeError('PRIOR_AUTH_ACCEPTANCE_NOT_PASSED')
    (NEW / 'auth-equivalence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    report = {'passed': True, 'files': 27, 'before_sha_changes': sorted(changed),
              'after_sha_changes': after_changed, 'retained_debt_guards': 4,
              'new_manifest_sha256': sha(NEW / 'manifest.json'), 'live_files_changed': False,
              'old_artifacts_overwritten': False, 'schema_changes': False}
    (NEW / 'rebase.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
