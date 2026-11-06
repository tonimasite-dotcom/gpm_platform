#!/usr/bin/env python3
"""Lint and exercise a private candidate; no live app bootstrap or database."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import time

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK / 'candidate'
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')


def copy_dependencies(source, destination):
    if destination.exists():
        return
    for p in source.rglob('*'):
        if p.is_symlink() and (os.path.isabs(os.readlink(str(p))) or source not in p.resolve().parents):
            raise RuntimeError('External dependency symlink; review required')
    shutil.copytree(source, destination, symlinks=True)


def run():
    if WORK.resolve() != WORK or ROOT.resolve() != ROOT:
        raise RuntimeError('Unsafe candidate location')
    start = time.monotonic()
    copy_dependencies(MAIN / 'vendor', ROOT / 'vendor')
    copy_dependencies(TS / 'node_modules', ROOT / 'node_modules')
    failures = []
    php = [p for folder in ['app', 'config', 'routes', 'database/migrations', 'bootstrap']
           for p in (ROOT / folder).rglob('*.php')]
    for p in php:
        result = subprocess.run(['php', '-l', str(p)], capture_output=True)
        if result.returncode:
            failures.append(str(p.relative_to(ROOT)))
    tests = {}
    for name in ['sync_plan_test.php', 'sync_service_test.php', 'worker_rate_test.php']:
        result = subprocess.run(['unshare', '--net', 'php', str(WORK / 'regression/tests' / name)],
                                capture_output=True, text=True)
        tests[name] = {'success': result.returncode == 0,
                       'summary': result.stdout.strip() if result.returncode == 0 else 'failed; inspect private log'}
        if result.returncode:
            (WORK / (name + '.log')).write_text(result.stdout + result.stderr)
    required = {
        'routes/api.php': ['manager_orders/publish_gpm_app/{order}', 'logist_orders/{order}/gpm_worker_rate'],
        'app/Providers/AppServiceProvider.php': ['GpmLogistOrderGuard::forbiddenFields'],
        'resources/js/pages/app/orders/logist_orders/LogistOrderForm.vue': ['<gpm-worker-rate-editor', 'GpmWorkerRateEditor,'],
        'resources/js/pages/app/orders/logist_orders/index.vue': ['showGpmAppModal', 'sendToGpmApp'],
        'app/Http/Controllers/Auth/LoginController.php': ['login_email_code_enabled'],
    }
    for rel, markers in required.items():
        text = (ROOT / rel).read_text()
        if not all(marker in text for marker in markers):
            failures.append(rel + ': required ts hook absent')
    order_list = (ROOT / 'resources/js/pages/app/orders/logist_orders/index.vue').read_text()
    if order_list.count('<v-dialog v-model="showGpmAppModal"') != 1:
        failures.append('GPM publication dialog duplicated or absent')
    if failures or not all(r['success'] for r in tests.values()):
        raise RuntimeError(json.dumps({'php_or_hook_failures': failures, 'tests': tests}))
    # No .env and no live credentials are passed to the build. Existing ts
    # MIX_BASE_URL is this public URL; other backend environment remains absent.
    env = {**os.environ, 'NODE_ENV': 'production', 'MIX_BASE_URL': 'https://ts.workstaffcrm.ru',
           'NODE_OPTIONS': '--max-old-space-size=2048'}
    build_log = WORK / 'frontend-build.log'
    with build_log.open('wb') as stream:
        build = subprocess.run(['unshare', '--net', 'nice', '-n', '10', 'node',
                                'node_modules/webpack/bin/webpack.js', '--no-progress', '--hide-modules',
                                '--config=node_modules/laravel-mix/setup/webpack.config.js'],
                               cwd=str(ROOT), env=env, stdout=stream, stderr=subprocess.STDOUT)
    report = {'mode': 'private_candidate_only', 'php_files_linted': len(php), 'php_lint_success': True,
              'gpm_regression_tests': tests, 'frontend_build_success': build.returncode == 0,
              'elapsed_seconds': round(time.monotonic() - start, 2),
              'live_files_changed': False, 'database_accessed': False, 'network_disabled_for_tests_and_build': True}
    if build.returncode == 0:
        report['frontend_manifest_entries'] = len(json.loads((ROOT / 'public/mix-manifest.json').read_text()))
    (WORK / 'candidate-checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    if build.returncode:
        raise SystemExit(1)


if __name__ == '__main__': run()
