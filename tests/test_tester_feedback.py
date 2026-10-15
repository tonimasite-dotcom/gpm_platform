import base64
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app import app_orders_api as api
from tests.test_app_orders_api import sample_payload


TEST_POSTGRES_URL = os.getenv("GPM_TEST_POSTGRES_URL")


class TesterFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {
            "GPM_APP_SQLITE_DB_FILE": os.path.join(self.temp.name, "test.sqlite3"),
            "GPM_APP_JWT_SECRET": "x" * 32,
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        api.init_db()
        self.client = self.actor("client", "test-client")
        self.logist = self.actor("logist", "test-logist")
        self.worker = self.actor("worker", "test-worker")
        self.other = self.actor("worker", "other-worker")

    def actor(self, role, name):
        invitation = api.create_account_invitation(name, role, created_by="test")
        account = api.redeem_account_invitation(invitation["token"], "Synthetic password 123!")
        return {"sub": account["account_id"], "username": name, "role": role}

    def active_order(self, *, workers=None, owner=None):
        workers = workers or [self.worker]
        owner = owner or self.client
        payload = sample_payload(source="manual")
        payload["order_data"].update({"price_per_hour": 600, "min_time": 4, "hours": 6})
        payload["order_data"]["loaders"]["loader_count"] = len(workers)
        incoming = api.normalize_external_order(payload, created_by=owner["sub"],
            created_by_role=owner["role"], require_order_number=False)
        if owner["role"] == "logist":
            incoming["logist_account_id"] = owner["sub"]
        saved = api.persist_published_order(incoming, actor=owner)
        api.patch_order_atomically(saved["id"], {"status": "PROCESSED"}, actor=None, integration=True)
        return api.patch_order_atomically(saved["id"], {
            "status": "IN_PROCESS", "assigned_worker_ids": [worker["sub"] for worker in workers],
        }, actor=None, integration=True)

    def attendance_event(self, order, worker, moment):
        with patch.object(api, "utc_now", return_value=moment):
            challenge = api.create_attendance_challenge(order["id"], worker, public_api_url="https://api.example.test")
            token = challenge["confirmation_url"].rsplit("/", 1)[1]
            if order["created_by_role"] == "client":
                return api.confirm_attendance_by_client(self.client, token=token)
            confirmation = api.guest_confirm_attendance(token=token)
            return api.complete_guest_attendance_by_worker(worker, confirmation["completion_code"])

    def test_checkout_rounds_each_worker_up_and_waits_for_every_worker(self):
        order = self.active_order(workers=[self.worker, self.other])
        start = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
        self.attendance_event(order, self.worker, start)
        self.attendance_event(order, self.other, start)
        self.attendance_event(order, self.other, start + timedelta(hours=2, minutes=10))
        pending = api.get_order(order["id"])
        self.assertEqual(pending["status"], "IN_PROCESS")
        self.attendance_event(order, self.worker, start + timedelta(hours=4, minutes=20))
        finished = api.get_order(order["id"])
        self.assertEqual(finished["status"], "DONE_PENDING")
        self.assertEqual(finished["worker_hours"], {self.worker["sub"]: 5, self.other["sub"]: 3})
        self.assertEqual(api.account_finance(self.worker)["pending"], 3000)
        self.assertEqual(api.account_finance(self.other)["pending"], 2400)

    def test_guest_checkout_and_replay_cannot_complete_an_order_twice(self):
        order = self.active_order(owner=self.logist)
        start = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
        self.attendance_event(order, self.worker, start)
        self.attendance_event(order, self.worker, start + timedelta(hours=4, seconds=1))
        finished = api.get_order(order["id"])
        self.assertEqual(finished["status"], "DONE_PENDING")
        self.assertEqual(finished["worker_hours"][self.worker["sub"]], 5)
        with self.assertRaises(HTTPException):
            api.create_attendance_challenge(order["id"], self.worker, public_api_url="https://api.example.test")

    def test_worker_cannot_finish_or_edit_order_through_status_api(self):
        order = self.active_order()
        for changes in ({"status": "DONE_PENDING"}, {"price_per_hour": 900}, {"status": "JUNK"}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as caught:
                api.patch_order_atomically(order["id"], changes, actor=self.worker, integration=False)
            self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(api.get_order(order["id"])["status"], "IN_PROCESS")

    def test_logist_can_cancel_without_attendance_but_other_logist_cannot(self):
        order = self.active_order(owner=self.logist)
        other_logist = self.actor("logist", "other-logist")
        with self.assertRaises(HTTPException):
            api.patch_order_atomically(order["id"], {"status": "JUNK"}, actor=other_logist, integration=False)
        cancelled = api.patch_order_atomically(order["id"], {"status": "JUNK"}, actor=self.logist, integration=False)
        self.assertEqual(cancelled["status"], "JUNK")
        self.assertEqual(api.account_finance(self.worker)["total_accrued"], 0)

    def test_latest_crm_fields_preserve_assignments_hours_reviews_and_owner(self):
        original = api.normalize_external_order({**sample_payload(), "source_instance": api.CRM_SYNC_INSTANCE})
        existing = {**original, "status": "IN_PROCESS", "logist_account_id": self.logist["sub"],
            "assigned_worker_ids": [self.worker["sub"]], "worker_hours": {self.worker["sub"]: 5},
            "worker_reviews": {self.worker["sub"]: {"result": "success"}}}
        incoming = {**original, "address": "Updated address", "price_per_hour": 700,
            "logist_account_id": "another-account"}
        merged = api.merge_existing_workflow_state(incoming, existing)
        self.assertEqual(merged["address"], "Updated address")
        self.assertEqual(merged["price_per_hour"], 700)
        for field in ("status", "logist_account_id", "assigned_worker_ids", "worker_hours", "worker_reviews"):
            self.assertEqual(merged[field], existing[field])
        with self.assertRaises(HTTPException):
            api.merge_existing_workflow_state({**incoming, "workers_count": 1},
                {**existing, "assigned_worker_ids": [self.worker["sub"], self.other["sub"]]})

    def test_closed_order_rates_and_hours_are_not_rewritten_by_crm(self):
        original = api.normalize_external_order(sample_payload())
        existing = {**original, "status": "CONVERTED", "price_per_hour": 600, "hours": 4}
        merged = api.merge_existing_workflow_state({**original, "price_per_hour": 900, "hours": 8}, existing)
        self.assertEqual(merged["price_per_hour"], 600)
        self.assertEqual(merged["hours"], 4)

    def test_integration_and_owner_can_edit_active_order_but_not_reduce_assigned_slots(self):
        order = self.active_order(owner=self.logist, workers=[self.worker, self.other])
        updated = api.patch_order_atomically(order["id"], {"price_per_hour": 900, "description": "Updated"},
            actor=None, integration=True)
        self.assertEqual(updated["price_per_hour"], 900)
        updated = api.patch_order_atomically(order["id"], {"description": "Edited by owner"},
            actor=self.logist, integration=False)
        self.assertEqual(updated["description"], "Edited by owner")
        with self.assertRaises(HTTPException):
            api.patch_order_atomically(order["id"], {"workers_count": 1}, actor=self.logist, integration=False)

    def test_worker_summary_is_current_and_does_not_expose_passport_or_payout(self):
        api.update_account_profile(self.worker, {"nationality": True, "display_name": "Current worker", "card_last4": "1234"})
        order = self.active_order(owner=self.logist)
        order["applications"] = [{"id": "application", "worker_id": self.worker["sub"]}]
        projection = api.enrich_order_worker_profiles(api.orders_for_user([order], self.logist))
        worker = projection[0]["applications"][0]["worker"]
        self.assertTrue(worker["nationality"])
        self.assertEqual(worker["display_name"], "Current worker")
        self.assertEqual(worker["identity_status"], "not_submitted")
        self.assertNotIn("card_last4", worker)
        self.assertNotIn("passport", worker)
        api.staff_update_worker_profile(self.worker["sub"], {"nationality": False}, self.logist)
        worker = api.enrich_order_worker_profiles(api.orders_for_user([order], self.logist))[0]["applications"][0]["worker"]
        self.assertFalse(worker["nationality"])

    def test_only_logist_can_manage_employment_and_other_profile_fields_are_rejected(self):
        api.update_account_profile(self.worker, {"nationality": True})
        updated = api.staff_update_worker_profile(self.worker["sub"], {"employment_type": "state"}, self.logist)
        self.assertEqual(updated["employment_type"], "state")
        self.assertTrue(updated["nationality"])
        for actor in (self.worker, self.client):
            with self.assertRaises(HTTPException) as caught:
                api.staff_update_worker_profile(self.worker["sub"], {"employment_type": "contract"}, actor)
            self.assertEqual(caught.exception.status_code, 403)
        with self.assertRaises(HTTPException):
            api.update_account_profile(self.worker, {"employment_type": "contract"})
        with self.assertRaises(HTTPException):
            api.staff_update_worker_profile(self.worker["sub"], {"email": "test@example.test"}, self.logist)

    def test_worker_can_set_citizenship_once_and_logist_can_correct_it(self):
        self.assertFalse(api.get_account_profile(self.worker)["nationality_recorded"])
        api.update_account_profile(self.worker, {"display_name": "Synthetic worker"})
        self.assertFalse(api.get_account_profile(self.worker)["nationality_recorded"])
        self.assertIsNone(api.worker_summary(self.worker["sub"])["nationality"])
        for actor, initial in ((self.worker, True), (self.other, False)):
            profile = api.update_account_profile(actor, {"nationality": initial})
            self.assertTrue(profile["nationality_recorded"])
            self.assertEqual(profile["nationality"], initial)
            # Older clients resubmit an unchanged value with other profile fields.
            api.update_account_profile(actor, {"nationality": initial, "cities": ["Москва"]})
            with self.assertRaises(HTTPException) as caught:
                api.update_account_profile(actor, {"nationality": not initial})
            self.assertEqual(caught.exception.status_code, 403)
            corrected = api.staff_update_worker_profile(actor["sub"], {"nationality": not initial}, self.logist)
            self.assertEqual(corrected["nationality"], not initial)
            with self.assertRaises(HTTPException):
                api.update_account_profile(actor, {"nationality": initial})
        with self.assertRaises(HTTPException) as caught:
            api.staff_update_worker_profile(self.worker["sub"], {"nationality": False}, self.client)
        self.assertEqual(caught.exception.status_code, 403)

    def test_missing_citizenship_is_not_treated_as_foreign(self):
        profile = api.get_account_profile(self.worker)
        self.assertFalse(api.worker_matches_nationality_requirement({"national": "yes"}, profile))
        self.assertFalse(api.worker_matches_nationality_requirement({"national": "no"}, profile))
        self.assertTrue(api.worker_matches_nationality_requirement({"national": "every"}, profile))
        profile = api.update_account_profile(self.worker, {"nationality": False})
        self.assertTrue(api.worker_matches_nationality_requirement({"national": "no"}, profile))

    def assert_concurrent_citizenship_is_saved_once(self, worker):
        barrier = Barrier(2)

        def save(value):
            barrier.wait(timeout=10)
            try:
                return api.update_account_profile(worker, {"nationality": value})["nationality"]
            except HTTPException as error:
                return error.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(save, value) for value in (True, False)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sum(type(result) is bool for result in results), 1)
        self.assertEqual(results.count(403), 1)
        saved = next(result for result in results if type(result) is bool)
        self.assertEqual(api.get_account_profile(worker)["nationality"], saved)

    def test_concurrent_first_profile_updates_cannot_replace_citizenship(self):
        self.assert_concurrent_citizenship_is_saved_once(self.worker)

    @unittest.skipUnless(TEST_POSTGRES_URL, "GPM_TEST_POSTGRES_URL is only configured in backend CI")
    def test_postgres_profile_locking_crm_update_and_attendance_finance(self):
        self.assertIsNotNone(api.psycopg2)
        schema = "gpm_feedback_" + uuid4().hex
        connection = api.psycopg2.connect(TEST_POSTGRES_URL)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA "{schema}"')
            connection.commit()
        finally:
            connection.close()

        def cleanup_schema():
            connection = api.psycopg2.connect(TEST_POSTGRES_URL)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
                connection.commit()
            finally:
                connection.close()

        self.addCleanup(cleanup_schema)
        dsn = api.psycopg2.extensions.make_dsn(TEST_POSTGRES_URL, options=f"-csearch_path={schema}")
        with patch.dict(os.environ, {
            "GPM_APP_DATABASE_URL": dsn,
            "GPM_APP_PRIVATE_UPLOAD_DIR": os.path.join(self.temp.name, "postgres-uploads"),
            "GPM_APP_JWT_SECRET": "x" * 32,
        }, clear=True):
            api.init_db()
            self.client = self.actor("client", "postgres-feedback-client")
            self.logist = self.actor("logist", "postgres-feedback-logist")
            self.worker = self.actor("worker", "postgres-feedback-worker")
            self.other = self.actor("worker", "postgres-feedback-other")
            self.assert_concurrent_citizenship_is_saved_once(self.worker)
            api.staff_update_worker_profile(self.worker["sub"], {"nationality": True, "employment_type": "state"}, self.logist)
            self.assertEqual(api.get_account_profile(self.worker)["employment_type"], "state")
            with self.assertRaises(HTTPException):
                api.update_account_profile(self.worker, {"nationality": False})
            order = self.active_order(owner=self.logist, workers=[self.worker, self.other])
            order.update(source="external", source_system="workstaff", source_instance=api.CRM_SYNC_INSTANCE)
            api.save_order(order)
            start = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
            self.attendance_event(order, self.worker, start)
            self.attendance_event(order, self.other, start)
            refreshed = api.persist_published_order({**order, "address": "CRM updated address", "price_per_hour": 700}, actor=None)
            self.assertEqual(refreshed["assigned_worker_ids"], order["assigned_worker_ids"])
            self.assertEqual(refreshed["status"], "IN_PROCESS")
            self.attendance_event(order, self.worker, start + timedelta(hours=4, minutes=20))
            self.assertEqual(api.get_order(order["id"])["status"], "IN_PROCESS")
            self.attendance_event(order, self.other, start + timedelta(hours=2, minutes=10))
            self.assertEqual(api.get_order(order["id"])["status"], "DONE_PENDING")
            self.assertEqual(api.account_finance(self.worker)["pending"], 3500)
            self.assertEqual(api.account_finance(self.other)["pending"], 2800)
            self.assert_concurrent_review_is_counted_once(order)
            self.assertEqual(api.get_order(order["id"])["status"], "DONE_PENDING")
            api.review_order_worker_atomically(order["id"], self.other["sub"], "good", self.logist)
            self.assertEqual(api.get_order(order["id"])["status"], "CONVERTED")
            self.assertEqual(api.get_account_profile(self.other)["rating"], -1)
            self.assertEqual(api.account_finance(self.worker)["available"], 3500)

    def test_logist_citizenship_correction_invalidates_passport_but_employment_does_not(self):
        api.update_account_profile(self.worker, {"display_name": "Synthetic Worker", "nationality": True})
        submission = api.submit_worker_verification(self.worker, "identity", {
            "data": {
                "full_name": "Synthetic Worker", "passport_series": "0000", "passport_number": "000000",
                "issued_at": "01.01.2020", "department_code": "000-000", "issued_by": "Synthetic issuer",
            },
            "attachment": {
                "filename": "passport.jpg", "media_type": "image/jpeg",
                "base64": base64.b64encode(b"\xff\xd8\xffsynthetic-image").decode("ascii"),
            },
        })
        api.review_worker_verification(self.logist, submission["submission_id"], {"status": "verified"})
        updated = api.staff_update_worker_profile(self.worker["sub"], {"employment_type": "state"}, self.logist)
        self.assertEqual(updated["identity_status"], "verified")
        updated = api.staff_update_worker_profile(self.worker["sub"], {"nationality": False}, self.logist)
        self.assertEqual(updated["identity_status"], "rejected")
        self.assertFalse(updated["nationality"])

    def ready_for_review(self, workers=None):
        order = self.active_order(owner=self.logist, workers=workers)
        return api.patch_order_atomically(
            order["id"], {"status": "DONE_PENDING"}, actor=self.logist, integration=False,
        )

    def test_ratings_follow_all_four_approved_values_and_survive_profile_edits(self):
        api.update_account_profile(self.worker, {"nationality": True})
        expected_rating = 0
        for result, delta in (("success", 1), ("fail", -2), ("good", -1), ("excellent", 2)):
            order = self.ready_for_review()
            reviewed = api.review_order_worker_atomically(order["id"], self.worker["sub"], result, self.logist)
            expected_rating += delta
            self.assertEqual(reviewed["review"]["rating_delta"], delta)
            self.assertEqual(reviewed["order"]["status"], "CONVERTED")
            self.assertEqual(api.get_account_profile(self.worker)["rating"], expected_rating)
        api.update_account_profile(self.worker, {"cities": ["Москва"]})
        profile = api.get_account_profile(self.worker)
        self.assertEqual(profile["rating"], 0)
        self.assertEqual(profile["success_requests"], 2)
        self.assertEqual(profile["fail_requests"], 1)
        self.assertTrue(profile["nationality"])

    def test_each_assigned_worker_is_reviewed_before_the_order_is_closed(self):
        order = self.ready_for_review(workers=[self.worker, self.other])
        reviewed = api.review_order_worker_atomically(order["id"], self.worker["sub"], "success", self.logist)
        self.assertEqual(reviewed["order"]["status"], "DONE_PENDING")
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 1)
        self.assertEqual(api.get_account_profile(self.other)["rating"], 0)
        reviewed = api.review_order_worker_atomically(order["id"], self.other["sub"], "excellent", self.logist)
        self.assertEqual(reviewed["order"]["status"], "CONVERTED")
        self.assertEqual(api.get_account_profile(self.other)["rating"], 2)

    def test_repeated_review_is_idempotent_and_different_review_is_rejected(self):
        order = self.ready_for_review()
        api.review_order_worker_atomically(order["id"], self.worker["sub"], "excellent", self.logist)
        repeated = api.review_order_worker_atomically(order["id"], self.worker["sub"], "excellent", self.logist)
        self.assertTrue(repeated["already_recorded"])
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 2)
        self.assertEqual(api.get_account_profile(self.worker)["success_requests"], 1)
        with self.assertRaises(HTTPException) as caught:
            api.review_order_worker_atomically(order["id"], self.worker["sub"], "good", self.logist)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 2)

    def test_review_requires_owner_assigned_worker_and_pending_completion(self):
        order = self.active_order(owner=self.logist)
        with self.assertRaises(HTTPException) as caught:
            api.review_order_worker_atomically(order["id"], self.worker["sub"], "success", self.logist)
        self.assertEqual(caught.exception.status_code, 409)
        order = self.ready_for_review()
        for actor in (self.worker, self.client, self.actor("logist", "other-reviewer")):
            with self.assertRaises(HTTPException) as caught:
                api.review_order_worker_atomically(order["id"], self.worker["sub"], "success", actor)
            self.assertEqual(caught.exception.status_code, 403)
        with self.assertRaises(HTTPException) as caught:
            api.review_order_worker_atomically(order["id"], self.other["sub"], "success", self.logist)
        self.assertEqual(caught.exception.status_code, 403)
        with self.assertRaises(HTTPException) as caught:
            api.review_order_worker_atomically(order["id"], self.worker["sub"], "neutral", self.logist)
        self.assertEqual(caught.exception.status_code, 422)

    def test_review_and_rating_are_rolled_back_together_on_failure(self):
        order = self.ready_for_review()
        with patch.object(api, "record_audit_event_in_connection", side_effect=RuntimeError("synthetic write failure")):
            with self.assertRaises(RuntimeError):
                api.review_order_worker_atomically(order["id"], self.worker["sub"], "excellent", self.logist)
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 0)
        self.assertEqual(api.get_order(order["id"])["status"], "DONE_PENDING")
        self.assertFalse(api.get_order(order["id"]).get("worker_reviews"))

    def assert_concurrent_review_is_counted_once(self, order):
        barrier = Barrier(2)

        def review():
            barrier.wait(timeout=10)
            return api.review_order_worker_atomically(order["id"], self.worker["sub"], "excellent", self.logist)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(review) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sum(result["already_recorded"] for result in results), 1)
        self.assertEqual(api.get_account_profile(self.worker)["rating"], 2)
        self.assertEqual(api.get_account_profile(self.worker)["success_requests"], 1)

    def test_concurrent_reviews_do_not_duplicate_rating(self):
        self.assert_concurrent_review_is_counted_once(self.ready_for_review())
