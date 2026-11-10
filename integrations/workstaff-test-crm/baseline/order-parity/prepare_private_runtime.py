"""Prepare isolated configuration and reviewed migration recipes; no execution."""
from pathlib import Path
import base64
import hashlib
import json
import os
import secrets
import subprocess

ROOT = Path('/root/gpm-ts-update/order-parity-20261110-02')
OLD = Path('/root/gpm-ts-update/20261106-baseline-01')
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TOOLS = Path(__file__).parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebase(text):
    return text.replace(str(OLD), str(ROOT)).replace('gpm_ts_rehearsal_20261106', 'gpm_order_parity_20261110').replace("'gpm_ts_rehearsal'", "'gpm_order_parity'")


def main():
    os.umask(0o077)
    candidate = ROOT / 'candidate'
    if candidate.resolve() != candidate or (candidate / '.env').exists():
        raise RuntimeError('NEW_PRIVATE_CONFIGURATION_REQUIRED')
    deps = json.loads(Path('/root/gpm-ts-update/order-parity-audit-20261110-01/dependencies.json').read_text())
    selected = []
    for row in deps['pending_migrations']:
        name = row['migration'] + '.php'
        source = MAIN / 'database/migrations' / name
        if sha(source) != row['sha256'] or source.read_bytes() != (OLD / 'source-main/database/migrations' / name).read_bytes():
            raise RuntimeError('NEW_UPSTREAM_MIGRATION_REQUIRES_REVIEW')
        if 'transfer_banking_card_to_card_number' in name or 'release_deleted_user_emails' in name:
            continue
        adapted = OLD / 'candidate/database/migrations' / name
        if not adapted.is_file():
            raise RuntimeError('REVIEWED_MIGRATION_RECIPE_REQUIRED')
        target = candidate / 'database/migrations' / name
        if target.exists():
            raise RuntimeError('UNEXPECTED_PREEXISTING_MIGRATION')
        target.write_text(rebase(adapted.read_text()))
        selected.append(name)
    for name in ['2026_10_28_110001_add_deleted_email_schema_for_gpm_ts.php',
                 '2026_11_06_180000_add_reference_permissions_for_gpm_ts.php']:
        source = OLD / 'candidate/database/migrations' / name
        if not source.is_file():
            raise RuntimeError('SCHEMA_ONLY_OR_PERMISSION_RECIPE_REQUIRED')
        (candidate / 'database/migrations' / name).write_text(rebase(source.read_text()))
        selected.append(name)
    release = candidate / 'app/Services/Release'
    for name in ['GpmTsRehearsal.php', 'GpmTsRuntimeContext.php']:
        (release / name).write_text(rebase((TOOLS / name).read_text()))
    policy = release / 'GpmTsDemoPolicy.php'
    text = policy.read_text()
    text = text.replace('/root/gpm-ts-update/20261110-demo-06/runtime', str(candidate))
    text = text.replace('/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109/rehearsal-mysql/mysql.sock', str(ROOT / 'rehearsal-mysql/mysql.sock'))
    text = text.replace('gpm_ts_backup_20261109', 'gpm_order_parity_20261110').replace('gpm_ts_backup_recovery', 'gpm_order_parity')
    text = text.replace('ts-demo-20261110-06', 'ts-order-parity-20261110-02')
    policy.write_text(text)
    (candidate / 'PRIVATE_DEMO_NO_DATABASE').write_text('Only the verified private SQL instance; isolated transport tests.\n')
    identity = json.loads((ROOT / 'rehearsal-mysql/identity.json').read_text())
    if identity['database'] != 'gpm_order_parity_20261110' or identity['socket'] != str(ROOT / 'rehearsal-mysql/mysql.sock'):
        raise RuntimeError('PRIVATE_DATABASE_IDENTITY_MISMATCH')
    config = {'APP_NAME': 'TS Private Order Parity', 'APP_ENV': 'production', 'APP_DEBUG': 'false',
              'APP_URL': 'https://ts.workstaffcrm.ru', 'APP_KEY': 'base64:' + base64.b64encode(secrets.token_bytes(32)).decode(),
              'DB_CONNECTION': 'mysql', 'DB_SOCKET': identity['socket'], 'DB_HOST': 'localhost',
              'DB_DATABASE': identity['database'], 'DB_USERNAME': identity['username'], 'DB_PASSWORD': identity['password'],
              'CACHE_DRIVER': 'array', 'SESSION_DRIVER': 'array', 'QUEUE_CONNECTION': 'sync',
              'BROADCAST_DRIVER': 'null', 'MAIL_MAILER': 'log', 'MAIL_DRIVER': 'log', 'LOG_CHANNEL': 'single',
              'JWT_SECRET': secrets.token_hex(32), 'GPM_APP_ORDER_SYNC_ENABLED': 'true',
              'GPM_APP_API_URL': 'https://invalid.invalid', 'GPM_APP_API_TOKEN': '', 'LOGIN_EMAIL_CODE_ENABLED': 'true'}
    (candidate / '.env').write_text('\n'.join(k + '=' + json.dumps(v) for k, v in config.items()) + '\n')
    for folder in ['storage/app', 'storage/logs', 'storage/framework/cache/data', 'storage/framework/sessions',
                   'storage/framework/views', 'bootstrap/cache']:
        (candidate / folder).mkdir(parents=True, exist_ok=True)
    (candidate / 'storage/framework/down').write_text(json.dumps({'time': 0, 'status': 503, 'retry': 60}))
    runner = rebase((TOOLS / 'rehearse_migrations.php').read_text())
    (ROOT / 'rehearse_migrations.php').write_text(runner)
    checked = []
    for path in [candidate / 'database/migrations' / n for n in selected] + list(release.glob('*.php')) + [ROOT / 'rehearse_migrations.php']:
        result = subprocess.run(['/opt/php74/bin/php', '-l', str(path)], capture_output=True)
        if result.returncode:
            raise RuntimeError('PRIVATE_RUNTIME_LINT_FAILED')
        checked.append(path.name)
    report = {'prepared': True, 'deployable': False, 'migration_recipes': selected,
              'banking_card_data_transfer_excluded': True, 'deleted_email_release_excluded': True,
              'existing_role_assignments_not_changed': True, 'private_environment_only': True,
              'php74_linted': len(checked), 'live_files_changed': False, 'migrations_executed': False,
              'note': 'Fresh SQL copy must be used; prior baseline results do not prove this rehearsal.'}
    (ROOT / 'private-runtime-preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'prepared': True, 'deployable': False, 'migration_recipes': len(selected),
                      'php74_linted': len(checked), 'live_files_changed': False, 'migrations_executed': False}))


if __name__ == '__main__':
    main()
