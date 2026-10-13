import asyncio
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from fastapi import HTTPException
from starlette.responses import Response

from app import app_orders_api as api
from tests import test_tester_feedback as feedback


class CrmOrderSyncTests(unittest.TestCase):
    setUp = feedback.TesterFeedbackTests.setUp
    actor = feedback.TesterFeedbackTests.actor
    active_order = feedback.TesterFeedbackTests.active_order

    def linked_order(self):
        order = self.active_order(owner=self.logist)
        order.update(source="external", source_system="workstaff", source_instance=api.CRM_SYNC_INSTANCE)
        api.save_order(order)
        return order

    def envelope(self, order, fields):
        return {
            "source_instance": api.CRM_SYNC_INSTANCE,
            "revision": api.crm_sync_snapshot(order)["revision"],
            "fields": fields,
        }

    def test_snapshot_only_exposes_sync_content_and_requires_test_binding(self):
        order = self.linked_order()
        snapshot = api.read_crm_sync_snapshot(order["id"])
        self.assertEqual(snapshot["protocol"], "gpm-crm-sync-v1")
        self.assertEqual(set(snapshot["fields"]), api.CRM_SYNC_FIELDS)
        self.assertNotIn("applications", snapshot)
        self.assertNotIn("logist_phone", snapshot)
        for changes in ({"source_instance": ""}, {"source_instance": "https://workstaffcrm.ru"}, {"source": "manual"}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException):
                api.crm_sync_snapshot({**order, **changes})

    def test_sync_updates_rates_and_address_preserving_workflow(self):
        order = self.linked_order()
        saved = api.sync_crm_order_atomically(order["id"], self.envelope(order, {
            "price_per_hour": 710, "address": "Москва, Тестовая, 3",
            "address_street": "Тестовая", "address_number": "3",
            "address_lat": 55.7, "address_lon": 37.6,
        }))
        self.assertEqual(saved["fields"]["price_per_hour"], 710)
        self.assertEqual(saved["fields"]["address_street"], "Тестовая")
        stored = api.get_order(order["id"])
        self.assertEqual(stored["assigned_worker_ids"], order["assigned_worker_ids"])
        self.assertEqual(stored["status"], "IN_PROCESS")

    def test_stale_revision_does_not_overwrite_new_app_edit(self):
        order = self.linked_order()
        envelope = self.envelope(order, {"price_per_hour": 700})
        api.patch_order_atomically(order["id"], {"price_per_hour": 800}, actor=self.logist, integration=False)
        with self.assertRaises(HTTPException) as caught:
            api.sync_crm_order_atomically(order["id"], envelope)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(api.get_order(order["id"])["price_per_hour"], 800)

    def test_attendance_changes_do_not_invalidate_content_revision(self):
        order = self.linked_order()
        envelope = self.envelope(order, {"min_time": 5})
        changed = {**order, "worker_hours": {self.worker["sub"]: 6}}
        api.save_order(changed)
        api.sync_crm_order_atomically(order["id"], envelope)
        self.assertEqual(api.get_order(order["id"])["worker_hours"], changed["worker_hours"])

    def test_closed_order_cannot_be_changed_even_with_current_revision(self):
        order = self.linked_order()
        order["status"] = "CONVERTED"
        api.save_order(order)
        for fields in ({"price_per_hour": 900}, {"address_lat": 0}):
            with self.subTest(fields=fields), self.assertRaises(HTTPException) as caught:
                api.sync_crm_order_atomically(order["id"], self.envelope(order, fields))
            self.assertEqual(caught.exception.status_code, 409)

    def test_sync_cannot_assign_workers_change_status_or_write_from_main_crm(self):
        order = self.linked_order()
        for fields in ({"status": "JUNK"}, {"assigned_worker_ids": []}, {"logist_account_id": "someone"}):
            with self.subTest(fields=fields), self.assertRaises(HTTPException) as caught:
                api.sync_crm_order_atomically(order["id"], self.envelope(order, fields))
            self.assertEqual(caught.exception.status_code, 422)
        envelope = self.envelope(order, {"city": "Москва"})
        envelope["source_instance"] = "https://workstaffcrm.ru"
        with self.assertRaises(HTTPException) as caught:
            api.sync_crm_order_atomically(order["id"], envelope)
        self.assertEqual(caught.exception.status_code, 403)

    def test_invalid_coordinates_and_audit_error_roll_back(self):
        order = self.linked_order()
        for value in (float("nan"), float("inf"), 91, None):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                api.sync_crm_order_atomically(order["id"], self.envelope(order, {"address_lat": value}))
        with patch.object(api, "record_audit_event_in_connection", side_effect=RuntimeError("Synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                api.sync_crm_order_atomically(order["id"], self.envelope(order, {"price_per_hour": 900}))
        self.assertEqual(api.get_order(order["id"])["price_per_hour"], 600)

    def test_simultaneous_sync_accepts_only_one_writer(self):
        order = self.linked_order()
        envelope = self.envelope(order, {"price_per_hour": 850})
        barrier = Barrier(2)
        def attempt():
            barrier.wait()
            try:
                api.sync_crm_order_atomically(order["id"], envelope)
                return 200
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(statuses), [200, 409])

    def test_sync_http_route_requires_integration_token(self):
        order = self.linked_order()
        with patch.dict(api.os.environ, {"GPM_APP_API_TOKEN": "SyntheticIntegrationToken"}):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(api.get_crm_sync_order(order["id"], Response(), "wrong"))
            self.assertEqual(caught.exception.status_code, 401)
            snapshot = asyncio.run(api.get_crm_sync_order(order["id"], Response(), "SyntheticIntegrationToken"))
            self.assertEqual(snapshot["order_id"], order["id"])

    def test_republication_cannot_take_over_another_crm_instance(self):
        order = self.linked_order()
        with self.assertRaises(HTTPException) as caught:
            api.merge_existing_workflow_state({**order, "source_instance": "https://other.example"}, order)
        self.assertEqual(caught.exception.status_code, 409)

    def test_first_test_crm_link_preserves_legacy_app_edits_and_owner(self):
        order = self.linked_order()
        order.pop("source_instance")
        order.update(price_per_hour=850, national="no", nationality="non_ru")
        api.save_order(order)
        incoming = {**order, "source_instance": api.CRM_SYNC_INSTANCE, "price_per_hour": 500,
                    "national": "yes", "nationality": "ru"}
        saved = api.persist_published_order(incoming, actor=None, preserve_existing_content=True)
        self.assertEqual(saved["price_per_hour"], 850)
        self.assertEqual(saved["national"], "no")
        self.assertEqual(saved["nationality"], "non_ru")
        self.assertEqual(saved["source_instance"], api.CRM_SYNC_INSTANCE)
        self.assertEqual(saved["logist_account_id"], self.logist["sub"])

    def test_first_link_cannot_claim_another_owner_or_manual_order(self):
        order = self.linked_order()
        for changes in ({"logist_account_id": "other-logist"}, {"source": "manual"}):
            stored = {**order, **changes, "source_instance": ""}
            api.save_order(stored)
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as caught:
                api.persist_published_order(order, actor=None, preserve_existing_content=True)
            self.assertEqual(caught.exception.status_code, 409)

    def test_publication_route_passes_link_option_only_for_integration(self):
        order = self.linked_order()
        order.pop("source_instance")
        order["price_per_hour"] = 850
        api.save_order(order)
        payload = feedback.sample_payload()
        payload.update(source_instance=api.CRM_SYNC_INSTANCE, preserve_existing_content=True)
        payload["order_data"].update(order_number=order["id"], price_per_hour=500)
        class JsonRequest:
            async def json(self):
                return payload
        with patch.object(api, "resolve_active_logist_account_id", return_value=self.logist["sub"]):
            response = asyncio.run(api.publish_order_payload(JsonRequest(), integration=True))
        self.assertEqual(response["order"]["price_per_hour"], 850)

    def test_real_asgi_sync_routes_accept_slash_order_numbers(self):
        order = self.linked_order()
        order.update(id="033/25", external_order_id="033/25")
        api.save_order(order)

        async def request(method, payload=None, token="SyntheticIntegrationToken"):
            messages = []
            body = json.dumps(payload).encode("utf-8") if payload is not None else b""
            scope = {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "scheme": "https", "method": method, "root_path": "",
                "path": "/app-api/integration/order-sync/033/25",
                "raw_path": b"/app-api/integration/order-sync/033%2F25",
                "query_string": b"", "server": ("testserver", 443), "client": ("127.0.0.1", 1234),
                "headers": [(b"x-gpm-app-token", token.encode()), (b"content-type", b"application/json")],
            }
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            async def send(message):
                messages.append(message)
            await api.app(scope, receive, send)
            status = next(message["status"] for message in messages if message["type"] == "http.response.start")
            content = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
            return status, json.loads(content)

        with patch.dict(api.os.environ, {"GPM_APP_API_TOKEN": "SyntheticIntegrationToken"}):
            status, snapshot = asyncio.run(request("GET"))
            self.assertEqual(status, 200)
            self.assertEqual(snapshot["order_id"], "033/25")
            status, updated = asyncio.run(request("PATCH", {
                "source_instance": api.CRM_SYNC_INSTANCE, "revision": snapshot["revision"],
                "fields": {"price_per_hour": 735},
            }))
            self.assertEqual(status, 200)
            self.assertEqual(updated["fields"]["price_per_hour"], 735)
            status, _ = asyncio.run(request("GET", token="wrong"))
            self.assertEqual(status, 401)
