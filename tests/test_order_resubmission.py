import asyncio
import copy
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException

from app import app_orders_api as api, crm_logist_ids as ids, order_resubmission as resubmit
from tests import test_tester_feedback as feedback


class OrderResubmissionTests(unittest.TestCase):
    setUp = feedback.TesterFeedbackTests.setUp
    actor = feedback.TesterFeedbackTests.actor
    active_order = feedback.TesterFeedbackTests.active_order

    def ready(self):
        with api.db_connection() as connection:
            ids.grant(connection, self.logist["sub"], assigned_by="synthetic-admin")
        order = self.active_order(owner=self.logist)
        order.update(status="PROCESSED", source="external", source_system="workstaff",
                     source_instance=api.CRM_SYNC_INSTANCE)
        api.save_order(order)
        return order

    def envelope(self):
        return {"source_instance": api.CRM_SYNC_INSTANCE,
                "logist_crm_id": 1, "request_id": uuid4().hex}

    def test_each_explicit_send_requests_moderation_without_losing_order_data(self):
        order = self.ready()
        before = copy.deepcopy(order)
        result = resubmit.request_moderation(order["id"], self.envelope())
        self.assertEqual(result["status"], "NEW")
        self.assertFalse(result["already_applied"])
        saved = api.get_order(order["id"])
        self.assertEqual(saved, {**before, "status": "NEW"})
        api.patch_order_atomically(order["id"], {"status": "PROCESSED"},
                                  actor=self.logist, integration=False)
        result = resubmit.request_moderation(order["id"], self.envelope())
        self.assertEqual(result["status"], "NEW")
        self.assertEqual(api.get_order(order["id"])["assigned_worker_ids"],
                         before["assigned_worker_ids"])

    def test_late_retry_does_not_reverse_a_newer_approval(self):
        order = self.ready()
        payload = self.envelope()
        resubmit.request_moderation(order["id"], payload)
        api.patch_order_atomically(order["id"], {"status": "PROCESSED"},
                                  actor=self.logist, integration=False)
        result = resubmit.request_moderation(order["id"], payload)
        self.assertTrue(result["already_applied"])
        self.assertEqual(result["status"], "PROCESSED")
        with api.db_connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM "+api.AUDIT_TABLE_NAME+
                " WHERE event_type=?", (resubmit.EVENT,)).fetchone()[0]
        self.assertEqual(count, 1)

    def test_started_finished_and_financial_records_are_never_reset(self):
        order = self.ready()
        for patch_value in [{"status": status} for status in
                            ["IN_PROCESS", "DONE_PENDING", "CONVERTED", "JUNK"]] + [
                                {"worker_hours": {self.worker["sub"]: 4}},
                                {"paid_at": "synthetic-paid-marker"},
                            ]:
            with self.subTest(patch=patch_value):
                before = {**order, **patch_value}
                api.save_order(before)
                finance_before = api.account_finance(self.worker)
                with self.assertRaises(HTTPException) as caught:
                    resubmit.request_moderation(order["id"], self.envelope())
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(api.get_order(order["id"]), before)
                self.assertEqual(api.account_finance(self.worker), finance_before)

    def test_owner_source_and_payload_cannot_be_overridden(self):
        order = self.ready()
        other = self.actor("logist", "other-logist")
        with api.db_connection() as connection:
            ids.grant(connection, other["sub"], assigned_by="synthetic-admin")
        for changes, status in [
            ({"logist_crm_id": 2}, 409),
            ({"source_instance": "https://other.invalid"}, 403),
            ({"request_id": "bad"}, 422),
            ({"fields": {"status": "NEW"}}, 422),
        ]:
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as caught:
                resubmit.request_moderation(order["id"], {**self.envelope(), **changes})
            self.assertEqual(caught.exception.status_code, status)
        self.assertEqual(api.get_order(order["id"]), order)

    def test_audit_failure_rolls_back_moderation(self):
        order = self.ready()
        with patch.object(api, "record_audit_event_in_connection",
                          side_effect=RuntimeError("Synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                resubmit.request_moderation(order["id"], self.envelope())
        self.assertEqual(api.get_order(order["id"]), order)

    def test_concurrent_retry_records_one_operation(self):
        order = self.ready()
        payload = self.envelope()
        barrier = Barrier(2)
        def attempt():
            barrier.wait()
            return resubmit.request_moderation(order["id"], payload)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(r["already_applied"] for r in results), [False, True])
        self.assertEqual(api.get_order(order["id"])["status"], "NEW")

    def test_http_route_requires_service_auth_not_an_app_session(self):
        from starlette.requests import Request
        from starlette.responses import Response
        self.assertTrue(any(getattr(route, "path", "") ==
            "/app-api/integration/order-resubmission/{order_id:path}"
            for route in api.app.routes))
        endpoint = next(route.endpoint for route in api.app.routes
                        if getattr(route, "path", "") ==
                        "/app-api/integration/order-resubmission/{order_id:path}")
        request = Request({"type": "http", "method": "POST", "path": "/synthetic",
                           "headers": []})
        with patch.dict(api.os.environ, {"GPM_APP_API_TOKEN": "SyntheticIntegrationToken"}):
            for token in ("wrong", None):
                with self.subTest(token=token), self.assertRaises(HTTPException) as caught:
                    asyncio.run(endpoint("TEST", request, Response(), token))
                self.assertEqual(caught.exception.status_code, 401)


    @unittest.skipUnless(feedback.TEST_POSTGRES_URL, "Synthetic PostgreSQL is not configured")
    def test_postgres_serializes_manual_retries_and_preserves_approval(self):
        with patch.dict(os.environ, {"GPM_APP_DATABASE_URL": feedback.TEST_POSTGRES_URL}):
            api.init_db()
            suffix = uuid4().hex
            staff = self.actor("logist", "remoderation-staff-" + suffix)
            worker = self.actor("worker", "remoderation-worker-" + suffix)
            with api.db_connection() as connection:
                code = ids.grant(connection, staff["sub"], assigned_by="synthetic-admin")["crm_logist_id"]
                connection.commit()
            order = self.active_order(owner=staff, workers=[worker])
            order.update(status="PROCESSED", source="external", source_system="workstaff",
                         source_instance=api.CRM_SYNC_INSTANCE)
            api.save_order(order)
            payload = {"source_instance": api.CRM_SYNC_INSTANCE,
                       "logist_crm_id": code, "request_id": uuid4().hex}
            barrier = Barrier(2)
            def attempt():
                barrier.wait()
                return resubmit.request_moderation(order["id"], payload)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: attempt(), range(2)))
            self.assertEqual(sorted(r["already_applied"] for r in results), [False, True])
            api.patch_order_atomically(order["id"], {"status": "PROCESSED"},
                                      actor=staff, integration=False)
            again = resubmit.request_moderation(order["id"], payload)
            self.assertTrue(again["already_applied"])
            self.assertEqual(again["status"], "PROCESSED")
