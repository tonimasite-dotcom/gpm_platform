#!/usr/bin/env python3
"""Resume an existing isolated recovery DB, test auth, then shut only it down."""
from pathlib import Path
import argparse
import base64
import contextlib
import importlib.util
import io
import json
import os
import secrets
import subprocess
import sys
import threading

PRIVATE = Path('/root/gpm-ts-update/20261110-demo-04')
RUNTIME = PRIVATE / 'runtime'
RECOVERY = Path('/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109')
MYSQL = RECOVERY / 'rehearsal-mysql'


def module(name):
    path = Path(__file__).parent / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, str(path))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    if args.attempt < 1 or args.attempt > 99:
        raise RuntimeError('SAFE_ATTEMPT_REQUIRED')
    os.umask(0o077)
    report_path = PRIVATE / ('login-acceptance-%02d.json' % args.attempt)
    shutdown_path = PRIVATE / ('login-shutdown-%02d.json' % args.attempt)
    if report_path.exists() or shutdown_path.exists() or (RUNTIME / '.env').exists():
        raise RuntimeError('NEW_AUTH_ACCEPTANCE_REPORT_REQUIRED')
    identity = json.loads((MYSQL / 'identity.json').read_text())
    if MYSQL.resolve() != MYSQL or identity['datadir'] != str(MYSQL / 'data') or identity['socket'] != str(MYSQL / 'mysql.sock'):
        raise RuntimeError('EXISTING_PRIVATE_RECOVERY_REQUIRED')
    for name in ['bootstrap/cache', 'storage/app', 'storage/logs', 'storage/framework/sessions',
                 'storage/framework/views', 'storage/framework/cache/data']:
        (RUNTIME / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    vendor = RUNTIME / 'vendor'
    expected_vendor = Path('/root/gpm-ts-update/20261106-baseline-01/candidate/vendor')
    if not vendor.exists():
        vendor.symlink_to(expected_vendor, target_is_directory=True)
    if vendor.resolve() != expected_vendor:
        raise RuntimeError('SAVED_VENDOR_REQUIRED')
    env_path = PRIVATE / 'private-auth-environment.json'
    if not env_path.exists():
        env = {'APP_BASE_PATH': str(RUNTIME), 'APP_ENV': 'testing', 'APP_URL': 'https://ts.workstaffcrm.ru',
               'APP_DEBUG': 'false', 'APP_KEY': 'base64:' + base64.b64encode(secrets.token_bytes(32)).decode(),
               'JWT_SECRET': secrets.token_hex(48), 'DB_CONNECTION': 'mysql', 'DB_HOST': 'localhost',
               'DB_SOCKET': identity['socket'], 'DB_DATABASE': identity['database'],
               'DB_USERNAME': identity['username'], 'DB_PASSWORD': identity['password'],
               'CACHE_DRIVER': 'array', 'SESSION_DRIVER': 'array', 'QUEUE_CONNECTION': 'sync',
               'MAIL_MAILER': 'smtp', 'MAIL_DRIVER': 'smtp', 'MAIL_HOST': '127.0.0.1',
               'MAIL_FROM_ADDRESS': 'fixture@example.invalid', 'BROADCAST_DRIVER': 'null',
               'LOGIN_EMAIL_CODE_ENABLED': 'true', 'GPM_APP_ORDER_SYNC_ENABLED': 'false',
               'GPM_APP_API_URL': 'https://invalid.invalid', 'GPM_APP_API_TOKEN': '',
               'GPM_TS_DEMO_REHEARSAL': '1', 'LOG_CHANNEL': 'single'}
        with env_path.open('x') as out:
            out.write(json.dumps(env))
    env = {key: value for key, value in os.environ.items() if key in ['PATH', 'HOME', 'LANG', 'TZ']}
    env.update(json.loads(env_path.read_text()))
    env['GPM_TS_AUTH_ATTEMPT'] = '%02d' % args.attempt
    resume = module('resume_private_mysql')
    resume.WORK = RECOVERY
    resume.MYSQL = MYSQL
    previous_argv = sys.argv
    sys.argv = ['resume_private_mysql.py', '--report-name', 'resume-demo-auth-04-%02d.json' % args.attempt]
    started = False
    mysql_process = None
    real_popen = subprocess.Popen
    def track_private_popen(*call_args, **kwargs):
        nonlocal mysql_process
        process = real_popen(*call_args, **kwargs)
        if call_args and isinstance(call_args[0], list) and ('--datadir=' + str(MYSQL / 'data')) in call_args[0]:
            mysql_process = process
        return process
    try:
        if (MYSQL / 'mysql.sock').exists() or (MYSQL / 'mysql.pid').exists():
            raise RuntimeError('PRIVATE_INSTANCE_ALREADY_RUNNING')
        started = True
        subprocess.Popen = track_private_popen
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                resume.main()
        finally:
            subprocess.Popen = real_popen
        result = subprocess.run(['unshare', '--net', '/opt/php74/bin/php',
                                 str(Path(__file__).parent / 'login_acceptance.php')],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if result.stderr:
            (PRIVATE / ('auth-private-stderr-%02d.log' % args.attempt)).write_bytes(result.stderr)
        try:
            report = json.loads(result.stdout)
        except Exception:
            (PRIVATE / ('auth-private-output-%02d.log' % args.attempt)).write_bytes(result.stdout)
            raise RuntimeError('PRIVATE_AUTH_OUTPUT_INVALID')
        with report_path.open('x') as out:
            out.write(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
        if result.returncode or not report.get('passed'):
            raise SystemExit(1)
    finally:
        sys.argv = previous_argv
        if started:
            # Reap our own child while the strict shutdown verifier waits for /proc.
            waiter = threading.Thread(target=mysql_process.wait, daemon=True) if mysql_process else None
            if waiter:
                waiter.start()
            stopped = module('stop_private_mysql').stop(MYSQL)
            if waiter:
                waiter.join(timeout=2)
            with shutdown_path.open('x') as out:
                out.write(json.dumps(stopped, indent=2) + '\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'PRIVATE_AUTH_RUNNER_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
