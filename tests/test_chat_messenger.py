import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app import app_orders_api as api
from tests.test_app_orders_api import sample_payload


class MessengerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "GPM_APP_SQLITE_DB_FILE": os.path.join(temporary.name, "chat.sqlite3"),
            "GPM_APP_DATABASE_URL": "", "DATABASE_URL": "",
            "GPM_APP_WORKER_USERNAME": "synthetic-worker",
            "GPM_APP_WORKER_PASSWORD": "synthetic-password-123",
            "GPM_APP_LOGIST_USERNAME": "synthetic-logist",
            "GPM_APP_LOGIST_PASSWORD": "synthetic-password-456",
            "GPM_APP_JWT_SECRET": "s" * 32,
        }, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        api.init_db()
        self.worker = api.current_user("Bearer " + api.check_app_credentials(
            "synthetic-worker", "synthetic-password-123"
        )["access_token"])
        self.logist = api.current_user("Bearer " + api.check_app_credentials(
            "synthetic-logist", "synthetic-password-456"
        )["access_token"])
        payload = sample_payload()
        payload["order_data"]["order_number"] = "001/26"
        self.order = api.normalize_external_order(payload)
        self.order.update({
            "status": "IN_PROCESS",
            "logist_account_id": self.logist["sub"],
            "assigned_worker_ids": [self.worker["sub"], "another-worker"],
        })
        api.persist_published_order(self.order, actor=None)
        self.thread_id = api.list_account_chat_threads(self.worker)[0]["id"]

    def send(self, text="Тестовое сообщение", key=None, user=None):
        return api.send_account_chat_message(
            self.thread_id, text, user or self.worker, key or str(uuid4())
        )

    def test_retry_returns_exact_original_and_records_one_message_and_audit(self):
        key = str(uuid4())
        first = self.send(key=key)
        self.send(text="Другое сообщение")
        retry = self.send(key=key)
        self.assertEqual(first, retry)
        _, messages = api.get_account_chat_messages(self.thread_id, self.worker)
        self.assertEqual(sum(message["id"] == key for message in messages), 1)
        with api.db_connection() as connection:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {api.AUDIT_TABLE_NAME} WHERE event_type = ?",
                ("chat_message_sent",),
            ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_same_role_does_not_make_another_workers_message_own(self):
        own = self.send()
        other = self.send(user={"sub": "another-worker", "role": "worker"})
        _, messages = api.get_account_chat_messages(self.thread_id, self.worker)
        by_id = {message["id"]: message for message in messages}
        self.assertTrue(by_id[own["id"]]["is_own"])
        self.assertFalse(by_id[other["id"]]["is_own"])

    def test_concurrent_retries_store_only_one_message(self):
        key = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.send(key=key), range(2)))
        self.assertEqual(results[0], results[1])
        _, messages = api.get_account_chat_messages(self.thread_id, self.worker)
        self.assertEqual(sum(message["id"] == key for message in messages), 1)

    def test_conflicting_retry_and_other_account_are_rejected(self):
        key = str(uuid4())
        self.send(key=key)
        for text, user in [("Изменённый текст", self.worker),
                           ("Тестовое сообщение", self.logist)]:
            with self.assertRaises(HTTPException) as caught:
                self.send(text=text, key=key, user=user)
            self.assertEqual(caught.exception.status_code, 409)

    def test_unassigned_account_cannot_read_send_or_retry(self):
        key = str(uuid4())
        self.send(key=key)
        outsider = {"sub": "outsider", "role": "worker"}
        for operation in [
            lambda: api.get_account_chat_messages(self.thread_id, outsider),
            lambda: self.send(key=key, user=outsider),
        ]:
            with self.assertRaises(HTTPException) as caught:
                operation()
            self.assertEqual(caught.exception.status_code, 404)

    def test_archive_blocks_new_messages_but_allows_acknowledgment_retry(self):
        key = str(uuid4())
        original = self.send(key=key)
        with api.db_connection() as connection:
            connection.execute(
                f"UPDATE {api.CHAT_THREADS_TABLE_NAME} SET is_archived = 1 WHERE thread_id = ?",
                (self.thread_id,),
            )
        self.assertEqual(original, self.send(key=key))
        with self.assertRaises(HTTPException) as caught:
            self.send()
        self.assertEqual(caught.exception.status_code, 409)

    def test_read_cursor_clears_unread_and_new_message_restores_it(self):
        self.send()
        self.assertGreater(api.list_account_chat_threads(self.logist)[0]["unread_count"], 0)
        api.get_account_chat_messages(self.thread_id, self.logist)
        self.assertEqual(api.list_account_chat_threads(self.logist)[0]["unread_count"], 0)
        self.send(text="Следующее сообщение")
        self.assertEqual(api.list_account_chat_threads(self.logist)[0]["unread_count"], 1)

    def test_polling_one_chat_does_not_list_all_other_chats(self):
        with patch.object(api, "list_account_chat_threads", side_effect=AssertionError("full scan")):
            thread, _ = api.get_account_chat_messages(self.thread_id, self.worker)
        self.assertEqual(thread["title"], "Заявка № 001/26")

    def test_invalid_id_and_oversize_message_are_rejected(self):
        for text, key in [("Текст", "invalid"), ("x" * 2001, str(uuid4()))]:
            with self.assertRaises(HTTPException) as caught:
                self.send(text=text, key=key)
            self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
