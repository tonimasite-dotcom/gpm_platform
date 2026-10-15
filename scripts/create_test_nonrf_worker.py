#!/usr/bin/env python3
"""Create the owner's requested synthetic non-RF worker; seal credentials first."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path('/opt/gpm/gpm_platform')
USERNAME = 'gpm-worker-nonrf-151026-01'
DESTINATION = Path('/root/gpm-test-accounts') / USERNAME


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--age', type=Path, required=True)
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if Path.cwd().resolve() != ROOT or os.getenv('GPM_APP_ENV') != 'production':
        raise RuntimeError('Unexpected production scope')
    sys.path.insert(0, str(ROOT))
    from app import app_orders_api as api
    api.validate_runtime_configuration()
    if not api.is_postgres_enabled():
        raise RuntimeError('Production PostgreSQL is required')
    if DESTINATION.is_symlink() or DESTINATION.parent.is_symlink():
        raise RuntimeError('Unexpected output path')
    with api.db_connection() as connection:
        existing = api._fetch_account_for_login(connection, USERNAME)
    sealed = DESTINATION / 'credentials.json.age'
    marker = DESTINATION / 'created.json'
    if existing:
        if not sealed.is_file() or not marker.is_file() or str(existing[3]) != 'worker':
            raise RuntimeError('Existing account requires manual review; never resetting password')
        print(json.dumps({'username': USERNAME, 'created': False, 'already_exists': True}))
        return
    if sealed.exists() or marker.exists():
        raise RuntimeError('Prior incomplete creation requires review')
    print(json.dumps({'username': USERNAME, 'role': 'worker', 'nationality': False,
                      'cities': ['Москва', 'Санкт-Петербург'], 'apply': args.apply}))
    if not args.apply:
        return
    DESTINATION.mkdir(parents=True, mode=0o700, exist_ok=True)
    password = secrets.token_urlsafe(24)
    document = json.dumps({'app_url': 'https://app.gpmbot.ru', 'role': 'worker',
                           'username': USERNAME, 'password': password,
                           'display_name': 'Тестовый исполнитель — не РФ',
                           'nationality': False, 'cities': ['Москва', 'Санкт-Петербург']},
                          ensure_ascii=False).encode('utf-8')
    # The only recoverable password copy is encrypted BEFORE creating the account.
    subprocess.run([str(args.age), '--encrypt', '--recipient', args.recipient,
                    '--output', str(sealed)], input=document, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    os.chmod(sealed, 0o600)
    invitation = api.create_account_invitation(USERNAME, 'worker', created_by='project-owner-request-20261015')
    account = api.redeem_account_invitation(invitation['token'], password, expected_role='worker')
    user = {'sub': account['account_id'], 'username': USERNAME, 'role': 'worker'}
    api.update_account_profile(user, {'display_name': 'Тестовый исполнитель — не РФ',
                                    'nationality': False, 'cities': ['Москва', 'Санкт-Петербург']})
    profile = api.get_account_profile(user)
    authenticated = api.check_app_credentials(USERNAME, password)
    api.revoke_session({**user, 'sid': authenticated['session_id']})
    if authenticated['account_id'] != user['sub'] or profile['nationality'] is not False or not profile['nationality_recorded']:
        raise RuntimeError('Created account did not pass verification')
    result = {'username': USERNAME, 'account_id': user['sub'], 'created': True,
              'nationality': False, 'login_verified': True, 'orders_changed': 0, 'crm_touched': False}
    marker.write_text(json.dumps(result) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Synthetic worker creation stopped (' + type(error).__name__ + '); credentials not printed.')
        raise SystemExit(1)
