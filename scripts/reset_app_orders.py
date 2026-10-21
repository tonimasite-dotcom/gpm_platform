"""Inspect or clear the owner's requested app orders; retain accounts and audit.

The apply operation requires a freshly verified backup in the workflow and an
exact hash of the inspected rows. No business data is emitted to public logs.
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app_orders_api as api


def rows(connection, query, parameters=()):
    if api._is_sqlite_connection(connection):
        return connection.execute(query.replace('%s', '?'), parameters).fetchall()
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchall()


def execute(connection, query, parameters=()):
    if api._is_sqlite_connection(connection):
        return connection.execute(query.replace('%s', '?'), parameters).rowcount
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return cursor.rowcount


def snapshot(connection):
    orders = rows(connection, f'SELECT * FROM {api.TABLE_NAME} ORDER BY order_id')
    related = {
        'orders': orders,
        'attendance': rows(connection, f'SELECT * FROM {api.ATTENDANCE_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME}) ORDER BY attendance_id'),
        'challenges': rows(connection, f'SELECT * FROM {api.ATTENDANCE_CHALLENGES_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME}) ORDER BY challenge_id'),
        'threads': rows(connection, f'SELECT * FROM {api.CHAT_THREADS_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME}) ORDER BY thread_id'),
        'messages': rows(connection, f'SELECT * FROM {api.CHAT_MESSAGES_TABLE_NAME} WHERE thread_id IN (SELECT thread_id FROM {api.CHAT_THREADS_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME})) ORDER BY message_id'),
        'reads': rows(connection, f'SELECT * FROM {api.CHAT_READS_TABLE_NAME} WHERE thread_id IN (SELECT thread_id FROM {api.CHAT_THREADS_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME})) ORDER BY thread_id, account_id'),
    }
    digest = hashlib.sha256(json.dumps(related, sort_keys=True, default=str).encode()).hexdigest()
    statuses = Counter()
    missing_rates = applications = reviews = 0
    for row in orders:
        order = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        statuses[str(order.get('status') or '')] += 1
        applications += len(order.get('applications') or [])
        reviews += len(order.get('worker_reviews') or {})
        if not any(isinstance(order.get(field), int) and not isinstance(order.get(field), bool) and order[field] > 0
                   for field in ('price_per_hour', 'price_regular', 'price_state')):
            missing_rates += 1
    return {
        'plan_sha256': digest,
        'counts': {name: len(value) for name, value in related.items()},
        'statuses': dict(statuses), 'applications': applications,
        'worker_reviews': reviews, 'orders_without_rate': missing_rates,
    }


def worker_diagnostics(connection, fingerprint=''):
    counts = Counter()
    target = None
    for username, data in rows(connection, f'''SELECT a.username, p.data
        FROM {api.ACCOUNTS_TABLE_NAME} a
        LEFT JOIN {api.PROFILES_TABLE_NAME} p ON p.account_id = a.account_id
        WHERE a.role = 'worker' '''):
        profile = data if isinstance(data, dict) else json.loads(data or '{}')
        nationality = profile.get('nationality')
        kind = 'russian' if nationality is True else 'non_russian' if nationality is False else 'missing_or_invalid'
        counts[kind] += 1
        if fingerprint and hashlib.sha256(username.casefold().encode()).hexdigest() == fingerprint:
            target = {
                'nationality': nationality if isinstance(nationality, bool) else None,
                'nationality_value_type': type(nationality).__name__,
                'nationality_recorded': 'nationality' in profile,
                'moscow_in_profile': 'москва' in api.worker_profile_cities(profile),
                'matches_rf_requirement': api.worker_matches_nationality_requirement({'national': 'yes'}, profile),
            }
    return {'counts': dict(counts), 'target': target}


def clear_orders(connection, expected_plan):
    if not api._is_sqlite_connection(connection):
        execute(connection, "SET LOCAL lock_timeout = '5s'")
        execute(connection, "SET LOCAL statement_timeout = '60s'")
        execute(connection, 'LOCK TABLE ' + ', '.join([
            api.TABLE_NAME, api.ATTENDANCE_TABLE_NAME,
            api.ATTENDANCE_CHALLENGES_TABLE_NAME, api.CHAT_THREADS_TABLE_NAME,
            api.CHAT_MESSAGES_TABLE_NAME, api.CHAT_READS_TABLE_NAME,
        ]) + ' IN ACCESS EXCLUSIVE MODE')
    else:
        execute(connection, 'BEGIN IMMEDIATE')
    before = snapshot(connection)
    if not expected_plan or before['plan_sha256'] != expected_plan:
        raise RuntimeError('Order snapshot changed; inspect the current plan before clearing')
    for table in (api.CHAT_READS_TABLE_NAME, api.CHAT_MESSAGES_TABLE_NAME):
        execute(connection, f'DELETE FROM {table} WHERE thread_id IN (SELECT thread_id FROM {api.CHAT_THREADS_TABLE_NAME} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME}))')
    for table in (api.CHAT_THREADS_TABLE_NAME, api.ATTENDANCE_CHALLENGES_TABLE_NAME, api.ATTENDANCE_TABLE_NAME):
        execute(connection, f'DELETE FROM {table} WHERE order_id IN (SELECT order_id FROM {api.TABLE_NAME})')
    execute(connection, f'DELETE FROM {api.TABLE_NAME}')
    if api._is_sqlite_connection(connection):
        execute(connection, f'DELETE FROM {api.LEGACY_TABLE_NAME}')
    api.record_audit_event_in_connection(connection,
        event_type='all_app_orders_cleared', outcome='success',
        target_type='maintenance', target_id='owner-request-2026-10-21',
        details=before)
    return {'deleted': before, 'remaining_orders': snapshot(connection)['counts']['orders']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    args = json.loads(base64.b64decode(parser.parse_args().request, validate=True))
    if os.environ.get('GPM_APP_ENV') != 'production' or not api.is_postgres_enabled():
        raise RuntimeError('This operation requires the production PostgreSQL configuration')
    if args.get('operation') not in {'inspect', 'clear'}:
        raise ValueError('Unsupported operation')
    with api.db_connection() as connection:
        if args['operation'] == 'clear':
            result = clear_orders(connection, args.get('expected_plan', ''))
            connection.commit()
        else:
            result = snapshot(connection)
        result['worker_diagnostics'] = worker_diagnostics(connection, args.get('worker_fingerprint', ''))
        print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
