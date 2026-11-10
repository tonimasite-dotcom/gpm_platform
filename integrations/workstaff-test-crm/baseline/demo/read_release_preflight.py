#!/usr/bin/env python3
"""TS-only current-state metadata. Does not bootstrap Laravel or connect to DB."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PRIVATE = Path('/root/gpm-ts-update/20261110-demo-04')
SAVED = Path('/root/gpm-ts-update/20261106-baseline-01/source-ts')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if TS.resolve() != TS or (TS / '.env').resolve() != TS / '.env':
        raise RuntimeError('EXACT_TS_PATH_REQUIRED')
    manifest = json.loads((PRIVATE / 'manifest.json').read_text())
    rows = []
    for row in manifest['files']:
        path = TS / row['file']
        if path.is_symlink() or path.resolve() != path:
            raise RuntimeError('LIVE_TARGET_SYMLINK')
        current = digest(path) if path.is_file() else None
        rows.append({'file': row['file'], 'sha256': current, 'matches_saved_baseline': current == row['before_sha256']})
    protected = ['app/Services/Order/GpmAppOrderSync.php', 'app/Services/Order/GpmAppOrderPublisher.php',
                 'app/Services/Order/GpmWorkerRateRules.php', 'app/Services/Order/GpmLogistOrderGuard.php',
                 'app/Http/Controllers/Order/GpmWorkerRateController.php', 'app/Http/Controllers/Auth/LoginController.php',
                 'app/Console/Kernel.php', 'routes/api.php', 'config/auth.php']
    protected_rows = [{'file': name, 'matches_saved_baseline': digest(TS / name) == digest(SAVED / name)} for name in protected]
    allowed = ['APP_ENV', 'APP_URL', 'MAIL_MAILER', 'QUEUE_CONNECTION', 'CACHE_DRIVER', 'SESSION_DRIVER',
               'LOGIN_EMAIL_CODE_ENABLED', 'GPM_APP_ORDER_SYNC_ENABLED', 'BROADCAST_DRIVER']
    code = "$loader=require '" + str(TS) + "/vendor/autoload.php'; $v=Dotenv\\Dotenv::parse(file_get_contents('" + str(TS) + "/.env')); echo json_encode(['environment'=>array_intersect_key($v,array_flip(json_decode('" + json.dumps(allowed) + "',true))),'classmap_authoritative'=>$loader->isClassMapAuthoritative()]);"
    process = subprocess.run(['/opt/php74/bin/php', '-r', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode:
        raise RuntimeError('ENV_METADATA_PARSE_FAILED')
    autoload = json.loads(process.stdout)
    flags = autoload['environment']
    if flags.get('APP_URL', '').rstrip('/') != 'https://ts.workstaffcrm.ru':
        raise RuntimeError('TS_URL_CHANGED')
    managed = []
    roots = ['/root/gpm-ts-update/20261106-baseline-01/rehearsal-mysql',
             '/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109/rehearsal-mysql']
    switch = Path('/root/gpm-ts-update/20261109-switch-01')
    roots += [str(p) for p in sorted(switch.glob('mysql-*')) if (p / 'data').is_dir()]
    processes = []
    ts_workers = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if any(root + '/' in command for root in roots) and ('mysqld' in command or 'mariadbd' in command):
                processes.append(int(proc.name))
            cwd = (proc / 'cwd').resolve()
            if str(TS) in command or cwd == TS:
                kinds = [kind for kind in ['queue:work', 'queue:listen', 'horizon', 'schedule:work', 'schedule:run',
                         'debit:check_debit', 'debit:notify', 'parse:email_leads'] if kind in command]
                if kinds:
                    ts_workers.append({'pid': int(proc.name), 'kinds': kinds})
        except (FileNotFoundError, PermissionError):
            pass
    for root in roots:
        p = Path(root)
        managed.append({'path': str(p), 'datadir_present': (p / 'data/ibdata1').is_file(),
                        'mysql_socket_present': (p / 'mysql.sock').exists()})
    units = []
    for folder in ['/etc/systemd/system', '/lib/systemd/system', '/usr/lib/systemd/system']:
        base = Path(folder)
        if not base.is_dir():
            continue
        for p in base.glob('*'):
            if p.suffix not in ['.service', '.timer'] or not p.is_file():
                continue
            text = p.read_text(errors='replace')
            if str(TS) in text:
                units.append({'file': str(p), 'sha256': digest(p),
                              'queue_or_scheduler_mentioned': bool(re.search(r'queue:|horizon|schedule:', text))})
    cron = Path('/etc/cron.d/gpm-test-crm-sync')
    fpm = []
    base = Path('/opt/php74/etc')
    for p in base.rglob('*.conf'):
        text = p.read_text(errors='replace')
        if 'ts.workstaffcrm.ru' not in text:
            continue
        values = []
        for line in text.splitlines():
            if re.match(r'^\s*(?:listen\s*=|php_(?:admin_)?(?:value|flag)\[opcache\.(?:enable|validate_timestamps|revalidate_freq)\])', line):
                values.append(line.strip())
        fpm.append({'file': str(p), 'selected_directives': values})
    report = {'files': rows, 'protected_files': protected_rows,
              'immutable_original_baseline_preserved': digest(Path('/root/gpm-ts-update/20261106-baseline-01/original-data-checks.json')) == 'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec',
              'immutable_original_checker_preserved': digest(Path('/root/gpm-ts-update/20261106-baseline-01/rehearse_migrations.php')) == '0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259',
              'all_live_targets_match_saved_baseline': all(r['matches_saved_baseline'] for r in rows),
              'all_protected_files_match_saved_baseline': all(r['matches_saved_baseline'] for r in protected_rows),
              'ts_environment_flags': flags, 'private_databases': managed, 'private_mysql_process_count': len(processes),
              'ts_long_running_or_scheduled_workers': ts_workers,
              'composer_classmap_authoritative': autoload['classmap_authoritative'],
              'ts_systemd_units': units, 'ts_fpm_pool_metadata': fpm,
              'fpm_socket_present': Path('/var/run/ts.workstaffcrm.ru.sock').exists(),
              'cgi_fcgi_available': bool(shutil.which('cgi-fcgi')),
              'existing_sync_cron_sha256': digest(cron) if cron.is_file() else None,
              'free_bytes': shutil.disk_usage(PRIVATE).free,
              'effective_fpm_opcache_verified': False, 'fresh_release_backup_verified': False,
              'main_crm_accessed': False, 'database_connected': False, 'laravel_bootstrapped': False,
              'live_files_changed': False, 'release_ready': False}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'READ_ONLY_PREFLIGHT_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
