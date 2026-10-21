import unittest

from scripts import reset_app_orders as reset
from app import app_orders_api as api
from tests import test_tester_feedback as feedback


class OrderResetTests(unittest.TestCase):
    setUp = feedback.TesterFeedbackTests.setUp
    actor = feedback.TesterFeedbackTests.actor
    active_order = feedback.TesterFeedbackTests.active_order

    def test_changed_snapshot_prevents_any_deletion(self):
        order = self.active_order()
        with api.db_connection() as connection:
            plan = reset.snapshot(connection)
        api.save_order({**order, 'description': 'changed after inspection'})
        with self.assertRaises(RuntimeError), api.db_connection() as connection:
            reset.clear_orders(connection, plan['plan_sha256'])
        self.assertIsNotNone(api.get_order(order['id']))

    def test_clears_only_orders_and_their_related_data(self):
        order = self.active_order()
        api.list_account_chat_threads(self.worker)
        with api.db_connection() as connection:
            connection.execute(f'''INSERT INTO {api.CHAT_THREADS_TABLE_NAME}
                (thread_id, order_id, thread_type) VALUES ('standalone', 'standalone', 'support')''')
            connection.execute(f'''INSERT INTO {api.ATTENDANCE_TABLE_NAME}
                (attendance_id, order_id, worker_account_id) VALUES (?, ?, ?)''',
                ('attendance', order['id'], self.worker['sub']))
        with api.db_connection() as connection:
            before_accounts = reset.rows(connection, f'SELECT * FROM {api.ACCOUNTS_TABLE_NAME} ORDER BY account_id')
            before_profiles = reset.rows(connection, f'SELECT * FROM {api.PROFILES_TABLE_NAME} ORDER BY account_id')
            plan = reset.snapshot(connection)
            self.assertGreater(plan['counts']['threads'], 0)
            self.assertEqual(plan['counts']['attendance'], 1)
            result = reset.clear_orders(connection, plan['plan_sha256'])
            self.assertEqual(result['remaining_orders'], 0)
            self.assertEqual(reset.rows(connection, f'SELECT * FROM {api.ACCOUNTS_TABLE_NAME} ORDER BY account_id'), before_accounts)
            self.assertEqual(reset.rows(connection, f'SELECT * FROM {api.PROFILES_TABLE_NAME} ORDER BY account_id'), before_profiles)
            self.assertEqual(reset.rows(connection, f'SELECT thread_id FROM {api.CHAT_THREADS_TABLE_NAME}'), [('standalone',)])
            self.assertEqual(reset.rows(connection, f'SELECT COUNT(*) FROM {api.ATTENDANCE_TABLE_NAME}')[0][0], 0)
        self.assertEqual(api.list_orders(), [])


class RequiredRateTests(unittest.TestCase):
    setUp = feedback.TesterFeedbackTests.setUp
    actor = feedback.TesterFeedbackTests.actor

    def test_creation_and_publication_require_explicit_rate(self):
        from tests.test_app_orders_api import sample_payload
        for mode in ('rate', 'shift'):
            for rate in (None, '', 0):
                payload = sample_payload()
                payload['order_data'].update(work_mode=mode, price_per_hour=rate, individual_price=10000)
                with self.subTest(mode=mode, rate=rate), self.assertRaises(ValueError):
                    api.normalize_external_order(payload)
        order = api.normalize_external_order(sample_payload())
        order['price_per_hour'] = None
        with self.assertRaises(api.HTTPException):
            api.validate_order_patch(order, {'status': 'PROCESSED'}, actor=None, integration=True)
        order['price_per_hour'] = 600
        with self.assertRaises(api.HTTPException):
            api.validate_order_patch(order, {'price_per_hour': None}, actor=None, integration=True)
