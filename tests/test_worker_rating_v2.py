import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, Response
from app import app_orders_api as api
from app import worker_ratings as ratings
from tests import test_tester_feedback as fixture


class RatingV2Tests(unittest.TestCase):
    setUp = fixture.TesterFeedbackTests.setUp
    actor = fixture.TesterFeedbackTests.actor
    active_order = fixture.TesterFeedbackTests.active_order
    ready_for_review = fixture.TesterFeedbackTests.ready_for_review

    def submit(self, order, result="excellent", worker=None):
        return api.review_order_worker_atomically(
            order["id"], (worker or self.worker)["sub"], result, self.logist,
            reason="Проверенная тестовая причина",
        )

    def correction(self, order, result, revision=1, request_id="correction-one", actor=None):
        return ratings.correct_review(
            order["id"], self.worker["sub"], result, actor or self.logist,
            reason="Исправлена ошибка оценки", expected_revision=revision, request_id=request_id,
        )

    def appeal(self, order, revision=1, request_id="appeal-one", actor=None):
        return ratings.appeal_review(
            order["id"], actor or self.worker, reason="Прошу проверить факты выполнения",
            expected_revision=revision, request_id=request_id,
        )

    def assert_status(self, code, operation):
        with self.assertRaises(HTTPException) as caught:
            operation()
        self.assertEqual(caught.exception.status_code, code)

    def test_rating_never_completes_work_or_changes_finance_and_can_follow_client_acceptance(self):
        order = self.active_order(owner=self.client)
        order["logist_account_id"] = self.logist["sub"]
        api.save_order(order)
        api.patch_order_atomically(order["id"], {"status": "DONE_PENDING"}, actor=self.logist, integration=False)
        before = api.account_finance(self.worker)
        self.submit(order)
        self.assertEqual(api.get_order(order["id"])["status"], "DONE_PENDING")
        self.assertEqual(api.account_finance(self.worker), before)
        api.patch_order_atomically(order["id"], {"status": "CONVERTED"}, actor=self.client, integration=False)
        accepted = api.account_finance(self.worker)
        self.correction(order, "success")
        self.assertEqual(api.account_finance(self.worker), accepted)
        second = self.active_order(owner=self.client)
        second["logist_account_id"] = self.logist["sub"]
        api.save_order(second)
        api.patch_order_atomically(second["id"], {"status": "DONE_PENDING"}, actor=self.logist, integration=False)
        api.patch_order_atomically(second["id"], {"status": "CONVERTED"}, actor=self.client, integration=False)
        before = api.account_finance(self.worker)
        self.submit(second)
        self.assertEqual(api.get_order(second["id"])["status"], "CONVERTED")
        self.assertEqual(api.account_finance(self.worker), before)

    def test_correction_and_void_apply_only_difference_keep_history_and_replay_once(self):
        order = self.ready_for_review()
        self.submit(order)
        self.correction(order, "fail")
        profile = api.get_account_profile(self.worker)
        self.assertEqual((profile["rating"], profile["success_requests"], profile["fail_requests"]), (-2, 0, 1))
        repeated = self.correction(order, "fail")
        self.assertTrue(repeated["already_recorded"])
        self.assertEqual(api.get_account_profile(self.worker)["rating"], -2)
        self.assert_status(409, lambda: self.correction(order, "success", request_id="another", revision=1))
        self.correction(order, "void", revision=2, request_id="void-one")
        profile = api.get_account_profile(self.worker)
        self.assertEqual((profile["rating"], profile["success_requests"], profile["fail_requests"]), (0, 0, 0))
        review = api.get_order(order["id"])["worker_reviews"][self.worker["sub"]]
        self.assertEqual([row["result"] for row in review["revisions"]], ["excellent", "fail", "void"])
        self.assertEqual(review["revision"], 3)
        self.assert_status(409, lambda: self.correction(order, "success", request_id="correction-one", revision=3))

    def test_reason_permissions_and_versions_are_checked(self):
        order = self.ready_for_review()
        self.assert_status(422, lambda: api.review_order_worker_atomically(order["id"], self.worker["sub"], "fail", self.logist))
        self.submit(order)
        stranger = self.actor("logist", "stranger-logist")
        for actor in [self.worker, self.client, stranger]:
            self.assert_status(403, lambda actor=actor: self.correction(order, "fail", actor=actor))
        self.assert_status(422, lambda: ratings.correct_review(
            order["id"], self.worker["sub"], "fail", self.logist,
            reason="", expected_revision=1, request_id="bad"))
        self.assert_status(422, lambda: ratings.correct_review(
            order["id"], self.worker["sub"], "fail", self.logist,
            reason="Причина указана", expected_revision=True, request_id="bad"))

    def test_worker_appeal_does_not_change_points_or_money_and_can_be_answered(self):
        order = self.ready_for_review()
        self.submit(order, "fail")
        before = (api.get_account_profile(self.worker), api.account_finance(self.worker))
        self.appeal(order)
        self.assertTrue(self.appeal(order)["already_recorded"])
        self.assertEqual((api.get_account_profile(self.worker), api.account_finance(self.worker)), before)
        self.assert_status(403, lambda: self.appeal(order, actor=self.other))
        self.assert_status(403, lambda: self.appeal(order, actor=self.client))
        self.assert_status(409, lambda: self.appeal(order, request_id="another"))
        result = ratings.resolve_appeal(
            order["id"], self.worker["sub"], self.logist, reason="Факты проверены, оценка подтверждена",
            expected_revision=1, request_id="resolution-one")
        self.assertEqual(result["review"]["appeals"][-1]["status"], "resolved")
        self.assertEqual(result["review"]["appeals"][-1]["decision"], "upheld")
        self.assertEqual((api.get_account_profile(self.worker), api.account_finance(self.worker)), before)
        repeated = ratings.resolve_appeal(
            order["id"], self.worker["sub"], self.logist, reason="Факты проверены, оценка подтверждена",
            expected_revision=1, request_id="resolution-one")
        self.assertTrue(repeated["already_recorded"])
        self.assert_status(409, lambda: self.appeal(order, request_id="third"))

    def test_correction_resolves_appeal_and_new_version_may_be_appealed(self):
        order = self.ready_for_review()
        self.submit(order, "fail")
        self.appeal(order)
        self.correction(order, "success")
        review = api.get_order(order["id"])["worker_reviews"][self.worker["sub"]]
        self.assertEqual(review["appeals"][0]["decision"], "changed")
        self.appeal(order, revision=2, request_id="new-version")
        self.assertEqual(len(api.get_order(order["id"])["worker_reviews"][self.worker["sub"]]["appeals"]), 2)

    def test_history_is_scoped_private_paginated_and_does_not_recalculate_legacy_balance(self):
        order = self.ready_for_review()
        self.submit(order)
        self.appeal(order)
        other_logist = self.actor("logist", "second-logist")
        second = self.ready_for_review()
        second["logist_account_id"] = other_logist["sub"]
        api.save_order(second)
        api.review_order_worker_atomically(second["id"], self.worker["sub"], "success", other_logist)
        before = api.get_account_profile(self.worker)
        response = ratings.history(self.worker["sub"], self.worker, limit=1)
        self.assertEqual(response["summary"]["review_count"], 2)
        self.assertEqual(response["summary"]["positive_percent"], 100)
        self.assertTrue(response["has_more"])
        self.assertEqual(len(response["history"]), 1)
        second_page = ratings.history(self.worker["sub"], self.worker, offset=1, limit=1)
        self.assertFalse(second_page["has_more"])
        serialized = json.dumps([response, second_page])
        for private in ["reviewed_by", "resolved_by", "request_id"]:
            self.assertNotIn(private, serialized)
        staff = ratings.history(self.worker["sub"], self.logist)
        self.assertEqual(staff["summary"]["review_count"], 2)
        self.assertEqual([item["order_id"] for item in staff["history"]], [order["id"]])
        self.assert_status(403, lambda: ratings.history(self.worker["sub"], self.other))
        self.assert_status(403, lambda: ratings.history(self.worker["sub"], self.client))
        self.assertEqual(api.get_account_profile(self.worker), before)
        # No records are invented or rewritten for a pre-existing balance.
        with api.db_connection() as connection:
            api._write_profile_in_connection(connection, self.other["sub"], {"rating": 17, "success_requests": 9})
            if not api._is_sqlite_connection(connection):
                connection.commit()
        legacy = api.get_account_profile(self.other)
        view = ratings.history(self.other["sub"], self.other)
        self.assertTrue(view["summary"]["has_legacy_balance"])
        self.assertEqual(view["summary"]["rating"], 17)
        self.assertEqual(view["summary"]["review_count"], 0)
        self.assertEqual(api.get_account_profile(self.other), legacy)

    def test_client_sees_only_general_rating_not_internal_reviews(self):
        self.submit(self.ready_for_review())
        order = self.active_order(owner=self.client)
        order["applications"] = [{"id": "client-visible-application", "worker_id": self.worker["sub"], "status": "PENDING"}]
        api.save_order(order)
        with patch.object(api, "authenticated_user", AsyncMock(return_value=self.client)):
            response = asyncio.run(api.get_my_orders(None))
        own_order = next(item for item in response["orders"] if item["id"] == order["id"])
        self.assertNotIn("worker_reviews", own_order)
        worker = own_order["applications"][0]["worker"]
        self.assertEqual(worker["rating"], 2)
        self.assertEqual(worker["rating_summary"]["review_count"], 1)
        self.assertEqual(worker["rating_summary"]["positive_percent"], 100)
        self.assertNotIn("reason", json.dumps(worker))
        self.assertNotIn("appeals", json.dumps(worker))

    def test_client_gets_assigned_general_rating_even_without_application_record(self):
        self.submit(self.ready_for_review())
        order = self.active_order(owner=self.client)
        self.assertFalse(order.get("applications"))
        with patch.object(api, "authenticated_user", AsyncMock(return_value=self.client)):
            response = asyncio.run(api.get_my_orders(None))
        own = next(item for item in response["orders"] if item["id"] == order["id"])
        public = own["assigned_workers"][0]
        self.assertEqual(set(public), {"id", "display_name", "full_name", "rating", "rating_summary"})
        self.assertEqual(public["rating"], 2)
        self.assertEqual(public["rating_summary"]["review_count"], 1)
        self.assertNotIn("worker_reviews", own)
        self.assertNotIn("reason", json.dumps(public))

    def test_cancelled_work_gets_no_new_rating_and_existing_review_can_be_voided_explicitly(self):
        order = self.ready_for_review(workers=[self.worker, self.other])
        self.submit(order)
        api.patch_order_atomically(order["id"], {"status": "JUNK"}, actor=self.logist, integration=False)
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 2)
        self.assert_status(409, lambda: self.submit(order, worker=self.other))
        self.correction(order, "void")
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 0)
        self.assertEqual(api.get_order(order["id"])["status"], "JUNK")

    def test_failed_audit_rolls_back_correction_and_appeal(self):
        order = self.ready_for_review()
        self.submit(order)
        original = api.get_order(order["id"])
        profile = api.get_account_profile(self.worker)
        with patch.object(api, "record_audit_event_in_connection", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.correction(order, "fail")
            with self.assertRaises(RuntimeError):
                self.appeal(order)
        self.assertEqual(api.get_order(order["id"]), original)
        self.assertEqual(api.get_account_profile(self.worker), profile)

    def test_parallel_correction_is_counted_once_and_stale_version_is_rejected(self):
        order = self.ready_for_review()
        self.submit(order)
        barrier = Barrier(2)
        def execute():
            barrier.wait(timeout=10)
            return self.correction(order, "fail")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=20) for f in [pool.submit(execute), pool.submit(execute)]]
        self.assertEqual(sum(result["already_recorded"] for result in results), 1)
        self.assertEqual(api.get_account_profile(self.worker)["rating"], -2)
        self.assertEqual(len(api.get_order(order["id"])["worker_reviews"][self.worker["sub"]]["revisions"]), 2)

    def test_parallel_reviews_for_different_orders_preserve_both_balances(self):
        first, second = self.ready_for_review(), self.ready_for_review()
        barrier = Barrier(2)
        def execute(order):
            barrier.wait(timeout=10)
            return self.submit(order)
        with ThreadPoolExecutor(max_workers=2) as pool:
            [f.result(timeout=20) for f in [pool.submit(execute, first), pool.submit(execute, second)]]
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 4)

    def test_history_order_filter_keeps_global_summary_and_returns_only_selected_order(self):
        first, second = self.ready_for_review(), self.ready_for_review()
        self.submit(first)
        self.submit(second, "success")
        view = ratings.history(self.worker["sub"], self.logist, order_id=second["id"])
        self.assertEqual(view["summary"]["review_count"], 2)
        self.assertEqual([item["order_id"] for item in view["history"]], [second["id"]])
        self.assertFalse(view["has_more"])

    def test_new_http_routes_enforce_roles_and_filter_worker_appeal_response(self):
        def endpoint(path):
            return next(route.endpoint for route in api.app.routes if getattr(route, "path", "") == path)
        order = self.ready_for_review()
        self.submit(order)
        for actor in [self.client, self.worker]:
            with patch.object(api, "authenticated_user", AsyncMock(return_value=actor)):
                if actor == self.client:
                    self.assert_status(403, lambda: asyncio.run(endpoint("/app-api/me/rating")(
                        response=Response(), authorization=None, offset=0, limit=20, order_id=None)))
                self.assert_status(403, lambda: asyncio.run(endpoint("/app-api/logist/workers/{worker_id}/rating")(
                    worker_id=self.worker["sub"], response=Response(), authorization=None,
                    offset=0, limit=20, order_id=None)))
        payload = {"reason": "Прошу проверить данные", "expected_revision": 1, "request_id": "http-appeal"}
        request = type("Request", (), {"headers": {}, "body": AsyncMock(return_value=json.dumps(payload).encode())})()
        with patch.object(api, "authenticated_user", AsyncMock(return_value=self.worker)):
            response = asyncio.run(endpoint("/app-api/me/order-rating-appeals/{order_id:path}")(
                order_id=order["id"], request=request, authorization=None))
        self.assertTrue(response["success"])
        self.assertNotIn("reviewed_by", json.dumps(response))
        self.assertNotIn("request_id", json.dumps(response))
        self.assertEqual(response["review"]["appeals"][0]["status"], "open")


    @unittest.skipUnless(fixture.TEST_POSTGRES_URL, "isolated PostgreSQL is configured by CI")
    def test_postgres_rating_history_corrections_privacy_finance_and_concurrency(self):
        schema = "rating_v2_" + uuid4().hex
        with api.psycopg2.connect(fixture.TEST_POSTGRES_URL) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute('CREATE SCHEMA "' + schema + '"')
        dsn = api.psycopg2.extensions.make_dsn(fixture.TEST_POSTGRES_URL, options="-csearch_path=" + schema)
        try:
            with patch.dict(os.environ, {"GPM_APP_DATABASE_URL": dsn, "GPM_APP_JWT_SECRET": "x" * 32}, clear=True):
                api.init_db()
                for method in [
                    self.test_rating_never_completes_work_or_changes_finance_and_can_follow_client_acceptance,
                    self.test_correction_and_void_apply_only_difference_keep_history_and_replay_once,
                    self.test_worker_appeal_does_not_change_points_or_money_and_can_be_answered,
                    self.test_history_is_scoped_private_paginated_and_does_not_recalculate_legacy_balance,
                    self.test_client_sees_only_general_rating_not_internal_reviews,
                    self.test_failed_audit_rolls_back_correction_and_appeal,
                    self.test_parallel_correction_is_counted_once_and_stale_version_is_rejected,
                    self.test_parallel_reviews_for_different_orders_preserve_both_balances,
                ]:
                    suffix = uuid4().hex[:8]
                    self.client = self.actor("client", "rating-client-" + suffix)
                    self.logist = self.actor("logist", "rating-logist-" + suffix)
                    self.worker = self.actor("worker", "rating-worker-" + suffix)
                    self.other = self.actor("worker", "rating-other-" + suffix)
                    method()
        finally:
            with api.psycopg2.connect(fixture.TEST_POSTGRES_URL) as connection:
                connection.autocommit = True
                with connection.cursor() as cursor:
                    cursor.execute('DROP SCHEMA "' + schema + '" CASCADE')
