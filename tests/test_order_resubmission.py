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
                     source_instance=api.CRM_SYNC_INSTANCE, city="Москва")
        api.save_order(order)
        return order

    def envelope(self, order):
        snapshot = api.crm_sync_snapshot(order)
        fields = dict(snapshot["fields"])
        fields["price_per_hour"] = 750
        return {"source_instance": api.CRM_SYNC_INSTANCE, "logist_crm_id": 1,
                "request_id": uuid4().hex, "revision": snapshot["revision"], "fields": fields}

    def create(self, order):
        result = resubmit.request_moderation(order["id"], self.envelope(order))
        return result, api.get_order(result["moderation_copy_id"])

    def test_published_stays_visible_and_draft_has_notice_without_duplicate_finance(self):
        order = self.ready()
        finance = api.account_finance(self.worker)
        result, draft = self.create(order)
        self.assertEqual(result["status"], "NEW")
        self.assertEqual(draft["status"], "NEW")
        self.assertTrue(draft["has_published_copy"])
        self.assertEqual(draft["published_copy_id"], order["id"])
        self.assertEqual(draft["title"], order["title"])
        self.assertEqual(draft["price_per_hour"], 750)
        self.assertEqual(draft["assigned_worker_ids"], [])
        stored = api.get_order(order["id"])
        for key, value in order.items():
            self.assertEqual(stored[key], value, key)
        visible = api.orders_for_user(api.list_orders(), self.worker, profile={"cities":["Москва"]})
        self.assertEqual([item["id"] for item in visible], [order["id"]])
        self.assertEqual(api.account_finance(self.worker), finance)
        self.assertEqual(len(api.list_account_chat_threads(self.logist)), 1)

    def test_approve_swaps_content_only_and_preserves_original_identity_and_people(self):
        order = self.ready()
        _, draft = self.create(order)
        api.patch_order_atomically(draft["id"], {"price_per_hour": 820},
                                  actor=self.logist, integration=False)
        saved = api.patch_order_atomically(draft["id"], {"status":"PROCESSED"},
                                          actor=self.logist, integration=False)
        self.assertEqual(saved["id"], order["id"])
        self.assertEqual(saved["status"], "PROCESSED")
        self.assertEqual(saved["price_per_hour"], 820)
        self.assertEqual(saved["assigned_worker_ids"], order["assigned_worker_ids"])
        self.assertEqual(saved["applications"], order["applications"])
        self.assertEqual(api.get_order(draft["id"])["moderation_state"], "approved")
        self.assertEqual(len(api.list_orders()), 1)
        self.assertFalse(api.crm_sync_snapshot(saved)["publication_review_hold"])
        second, new_draft = self.create(saved)
        self.assertNotEqual(new_draft["id"], draft["id"])

    def test_rejection_preserves_published_and_cannot_be_bypassed_by_cron(self):
        order = self.ready()
        _, draft = self.create(order)
        api.patch_order_atomically(draft["id"], {"status":"JUNK"},
                                  actor=self.logist, integration=False)
        saved = api.get_order(order["id"])
        self.assertEqual(saved["status"], "PROCESSED")
        self.assertEqual(saved["price_per_hour"], order["price_per_hour"])
        self.assertEqual(len(api.list_orders()), 1)
        snapshot = api.crm_sync_snapshot(saved)
        with self.assertRaises(HTTPException) as caught:
            api.sync_crm_order_atomically(order["id"], {
                "source_instance":api.CRM_SYNC_INSTANCE,"revision":snapshot["revision"],
                "fields":{"price_per_hour":900},
            })
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(api.get_order(order["id"])["price_per_hour"], order["price_per_hour"])

    def test_new_manual_request_supersedes_pending_without_stacking_live_copies(self):
        order = self.ready()
        _, first = self.create(order)
        _, second = self.create(api.get_order(order["id"]))
        self.assertNotEqual(first["id"],second["id"])
        self.assertEqual(api.get_order(first["id"])["moderation_state"],"superseded")
        self.assertEqual(len(api.list_orders()),2)
        with self.assertRaises(HTTPException):
            api.patch_order_atomically(first["id"],{"status":"PROCESSED"},
                                      actor=self.logist,integration=False)

    def test_network_retry_after_review_does_not_reopen_or_create_copy(self):
        order = self.ready()
        payload = self.envelope(order)
        result = resubmit.request_moderation(order["id"],payload)
        api.patch_order_atomically(result["moderation_copy_id"],{"status":"PROCESSED"},
                                  actor=self.logist,integration=False)
        retry = resubmit.request_moderation(order["id"],payload)
        self.assertTrue(retry["already_applied"])
        self.assertEqual(len(api.list_orders()),1)
        self.assertEqual(api.get_order(order["id"])["price_per_hour"],750)

    def test_initial_unpublished_order_remains_one_moderation_record(self):
        order = self.ready()
        order["status"]="NEW"
        api.save_order(order)
        result = resubmit.request_moderation(order["id"],self.envelope(order))
        self.assertIsNone(result["moderation_copy_id"])
        self.assertEqual(api.get_order(order["id"])["status"],"NEW")
        self.assertEqual(len(api.list_orders()),1)

    def test_started_closed_and_paid_orders_are_not_changed(self):
        order = self.ready()
        for delta in [{"status":s} for s in ["IN_PROCESS","DONE_PENDING","CONVERTED","JUNK"]] + [
            {"worker_hours":{self.worker["sub"]:4}},{"paid_at":"synthetic-paid"}
        ]:
            before={**order,**delta};api.save_order(before)
            with self.assertRaises(HTTPException) as caught:
                resubmit.request_moderation(order["id"],self.envelope(before))
            self.assertEqual(caught.exception.status_code,409)
            self.assertEqual(api.get_order(order["id"]),before)

    def test_work_started_or_published_content_changed_blocks_pending_approval(self):
        for delta in [{"status":"IN_PROCESS"},{"price_per_hour":910}]:
            order=self.ready();_,draft=self.create(order)
            changed={**api.get_order(order["id"]),**delta};api.save_order(changed)
            with self.assertRaises(HTTPException) as caught:
                api.patch_order_atomically(draft["id"],{"status":"PROCESSED"},
                                          actor=self.logist,integration=False)
            self.assertEqual(caught.exception.status_code,409)
            self.assertEqual(api.get_order(order["id"]),changed)

    def test_owner_source_revision_and_arbitrary_fields_cannot_be_overridden(self):
        order=self.ready();other=self.actor("logist","other-logist")
        with api.db_connection() as connection:ids.grant(connection,other["sub"],assigned_by="synthetic-admin")
        for delta,status in [
            ({"logist_crm_id":2},409),({"source_instance":"https://other.invalid"},403),
            ({"request_id":"bad"},422),({"revision":"f"*64},409),
            ({"fields":{"status":"NEW"}},422),
        ]:
            with self.subTest(delta=delta),self.assertRaises(HTTPException) as caught:
                resubmit.request_moderation(order["id"],{**self.envelope(order),**delta})
            self.assertEqual(caught.exception.status_code,status)
        _,draft=self.create(order)
        for actor,integration in [(other,False),(self.worker,False),(None,True)]:
            with self.assertRaises(HTTPException):
                api.patch_order_atomically(draft["id"],{"status":"PROCESSED"},
                                          actor=actor,integration=integration)

    def test_audit_failure_rolls_back_parent_and_new_copy(self):
        order=self.ready()
        with patch.object(api,"record_audit_event_in_connection",side_effect=RuntimeError("Synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                resubmit.request_moderation(order["id"],self.envelope(order))
        self.assertEqual(api.get_order(order["id"]),order)
        self.assertEqual(len(api.list_orders()),1)

    def test_concurrent_network_retry_creates_one_pending_version(self):
        order=self.ready();payload=self.envelope(order);barrier=Barrier(2)
        def attempt():
            barrier.wait()
            return resubmit.request_moderation(order["id"],payload)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
        self.assertEqual(sorted(r["already_applied"] for r in results),[False,True])
        self.assertEqual(results[0]["moderation_copy_id"],results[1]["moderation_copy_id"])
        self.assertEqual(len(api.list_orders()),2)

    def test_http_route_requires_integration_auth(self):
        from starlette.requests import Request
        from starlette.responses import Response
        endpoint=next(r.endpoint for r in api.app.routes if getattr(r,"path","")==
                      "/app-api/integration/order-resubmission/{order_id:path}")
        request=Request({"type":"http","method":"POST","path":"/synthetic","headers":[]})
        with patch.dict(api.os.environ,{"GPM_APP_API_TOKEN":"SyntheticIntegrationToken"}):
            for token in ["wrong",None]:
                with self.assertRaises(HTTPException) as caught:
                    asyncio.run(endpoint("TEST",request,Response(),token))
                self.assertEqual(caught.exception.status_code,401)

    @unittest.skipUnless(feedback.TEST_POSTGRES_URL,"Synthetic PostgreSQL is not configured")
    def test_postgres_retry_and_atomic_replacement(self):
        with patch.dict(os.environ,{"GPM_APP_DATABASE_URL":feedback.TEST_POSTGRES_URL}):
            api.init_db();suffix=uuid4().hex
            staff=self.actor("logist","version-staff-"+suffix)
            worker=self.actor("worker","version-worker-"+suffix)
            with api.db_connection() as connection:
                code=ids.grant(connection,staff["sub"],assigned_by="synthetic-admin")["crm_logist_id"]
                connection.commit()
            order=self.active_order(owner=staff,workers=[worker])
            order.update(status="PROCESSED",source="external",source_system="workstaff",
                         source_instance=api.CRM_SYNC_INSTANCE)
            api.save_order(order)
            payload={**self.envelope(order),"logist_crm_id":code};barrier=Barrier(2)
            def attempt():
                barrier.wait()
                return resubmit.request_moderation(order["id"],payload)
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
            self.assertEqual(sorted(r["already_applied"] for r in results),[False,True])
            draft=api.get_order(results[0]["moderation_copy_id"])
            api.patch_order_atomically(draft["id"],{"status":"PROCESSED"},actor=staff,integration=False)
            saved=api.get_order(order["id"])
            self.assertEqual(saved["price_per_hour"],750)
            self.assertEqual(saved["assigned_worker_ids"],order["assigned_worker_ids"])
            self.assertTrue(resubmit.request_moderation(order["id"],payload)["already_applied"])
