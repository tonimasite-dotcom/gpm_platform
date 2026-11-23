import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from app import registration_preview as reg
from app import registration_preview_crm as sync


class PreviewWorkerSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1795431600.0
        environment = patch.dict(os.environ, {
            "GPM_REGISTRATION_PREVIEW_DB": self.temp.name+"/preview.sqlite3",
            "GPM_REGISTRATION_PREVIEW_CRM_ENABLED": "true",
        })
        environment.start(); self.addCleanup(environment.stop)
        timer = patch.object(reg, "clock", side_effect=lambda: self.now)
        timer.start(); self.addCleanup(timer.stop)
        self.store = reg.PreviewStore()

    def complete(self, phone="+79990000001"):
        state = self.store.create()
        sid, token = state["registration_id"], state["session_token"]
        state = self.store.patch(sid, token, state["revision"], {"phone": phone, "phone_country": "RU"})
        state = self.store.challenge(sid, token, state["revision"])
        self.assertEqual(state["test_code"], "123456")
        state = self.store.verify(sid, token, state["revision"], "123456")
        state = self.store.patch(sid, token, state["revision"], {
            "district_ids": [502], "first_name": "Тест", "last_name": "Пример",
            "middle_name": "", "birth_date": "1990-01-01",
            "citizenship_ru": True, "has_straps": False, "has_tools": False,
        })
        return self.store.complete(sid, token, state["revision"], uuid4().hex)

    def listing(self, **extra):
        return {"operation": "list", "source_instance": sync.INSTANCE, "since": self.now-1,
                "limit": 100, **extra}

    def ack(self, document, **extra):
        return {"operation": "ack", "source_instance": sync.INSTANCE,
                "profile_id": document["profile_id"], "revision": document["revision"],
                "status": "linked", "crm_worker_id": "101", "error_code": None, **extra}

    def error(self, code, function, *args):
        with self.assertRaises(HTTPException) as result:
            function(*args)
        self.assertEqual(result.exception.status_code, code)

    def test_only_complete_test_profiles_are_exported_without_session_credentials(self):
        self.store.create()
        completed = self.complete()
        result = sync.export(self.listing())
        self.assertEqual(result["environment"], "registration-preview")
        self.assertEqual(len(result["profiles"]), 1)
        document = result["profiles"][0]
        self.assertEqual(document["profile_id"], completed["profile_id"])
        self.assertEqual(document["cities"], ["Санкт-Петербург"])
        self.assertEqual(document["verification_method"], "test_code")
        self.assertNotIn("session_token", json.dumps(result))
        self.assertNotIn("token_hash", json.dumps(result))
        self.assertFalse(completed["profile_active"])

    def test_common_code_works_for_different_test_participants(self):
        self.complete("+79990000001")
        self.complete("+79990000002")
        self.assertEqual(len(sync.export(self.listing())["profiles"]), 2)

    def test_disabled_and_other_crm_are_rejected(self):
        with patch.dict(os.environ, {"GPM_REGISTRATION_PREVIEW_CRM_ENABLED": "false"}):
            self.error(503, sync.export, self.listing())
        self.error(403, sync.export, self.listing(source_instance="https://main.invalid"))

    def test_cutoff_and_page_size_are_enforced(self):
        self.complete()
        self.assertEqual(sync.export(self.listing(since=self.now+1))["profiles"], [])
        for value in [True, float("nan"), -1, self.now+100]:
            self.error(422, sync.export, self.listing(since=value))
        self.error(422, sync.export, self.listing(limit=101))
        self.error(422, sync.export, self.listing(untrusted=True))

    def test_ack_is_idempotent_and_terminal_link_cannot_be_rebound(self):
        self.complete()
        document = sync.export(self.listing())["profiles"][0]
        payload = self.ack(document)
        sync.acknowledge(payload)
        self.assertTrue(sync.acknowledge(payload)["already_linked"])
        self.assertEqual(sync.export(self.listing())["profiles"], [])
        self.error(409, sync.acknowledge, self.ack(document, crm_worker_id="102"))
        self.error(409, sync.acknowledge, self.ack(document, status="deferred", crm_worker_id=None,
                                                error_code="temporary_unavailable"))
        receipts = list((Path(self.temp.name)/"crm-sync").glob("preview_*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].stat().st_mode & 0o777, 0o600)

    def test_conflicts_retry_later_without_blocking_other_profiles(self):
        self.complete()
        document = sync.export(self.listing())["profiles"][0]
        sync.acknowledge(self.ack(document, status="conflict", crm_worker_id=None,
                                  error_code="duplicate_crm_phone"))
        self.complete("+79990000002")
        pending = sync.export(self.listing())["profiles"]
        self.assertEqual(len(pending), 1)
        self.assertNotEqual(pending[0]["profile_id"], document["profile_id"])
        self.now += 301
        self.assertEqual(len(sync.export(self.listing())["profiles"]), 2)

    def test_wrong_revision_and_duplicate_crm_binding_are_rejected(self):
        self.complete()
        first = sync.export(self.listing())["profiles"][0]
        self.error(409, sync.acknowledge, self.ack(first, revision="0"*64))
        sync.acknowledge(self.ack(first))
        self.complete("+79990000002")
        second = sync.export(self.listing())["profiles"][0]
        self.error(409, sync.acknowledge, self.ack(second))

    def test_private_storage_escape_is_rejected(self):
        self.complete()
        document = sync.export(self.listing())["profiles"][0]
        self.error(422, sync.acknowledge, self.ack(document, profile_id="../../escape"))

    def test_no_production_tables_are_created(self):
        self.complete()
        sync.export(self.listing())
        with self.store.connection() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"preview_sessions", "preview_profiles", "preview_events"})
        self.assertFalse((Path(self.temp.name)/"main.sqlite3").exists())

    def test_route_requires_service_auth_before_reading_test_data(self):
        app = FastAPI()
        sync.register_routes(app)
        async def request(token):
            messages = []
            raw = json.dumps(self.listing()).encode()
            received = False
            async def receive():
                nonlocal received
                if received:
                    return {"type": "http.disconnect"}
                received = True
                return {"type": "http.request", "body": raw, "more_body": False}
            async def send(message):
                messages.append(message)
            headers = [(b"content-type", b"application/json")]
            if token:
                headers.append((b"x-gpm-app-token", token.encode()))
            path = "/app-api/integration/registration-preview/workers"
            await app({"type":"http","asgi":{"version":"3.0"},"http_version":"1.1",
                       "method":"POST","scheme":"https","path":path,"raw_path":path.encode(),
                       "query_string":b"","headers":headers,"server":("test",443),
                       "client":("127.0.0.1",1000),"root_path":""}, receive, send)
            return next(m["status"] for m in messages if m["type"]=="http.response.start")
        def check(token):
            if token != "synthetic-service-token":
                raise HTTPException(401, "unauthorized")
        with patch.object(sync.api(), "check_token", side_effect=check):
            self.assertEqual(asyncio.run(request(None)), 401)
            self.assertEqual(asyncio.run(request("synthetic-service-token")), 200)
