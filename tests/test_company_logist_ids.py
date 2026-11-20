import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.responses import Response

from app import app_orders_api as api
from app import crm_logist_ids as ids
from tests.test_app_orders_api import sample_payload
from tests.test_tester_feedback import TesterFeedbackTests


class CompanyLogistIdTests(unittest.TestCase):
    setUp = TesterFeedbackTests.setUp
    actor = TesterFeedbackTests.actor

    def grant(self, actor):
        with api.db_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return ids.grant(connection, actor["sub"], assigned_by="synthetic-admin")

    def test_external_logist_has_no_crm_id_and_cannot_self_enroll(self):
        profile = api.get_account_profile(self.logist)
        self.assertIsNone(profile["crm_logist_id"])
        self.assertFalse(profile["is_gpm_company_logist"])
        for field in ("crm_logist_id", "is_gpm_company_logist"):
            with self.assertRaises(HTTPException) as caught:
                api.update_account_profile(self.logist, {field: 1})
            self.assertEqual(caught.exception.status_code, 422)

    def test_only_company_logists_consume_ids_and_existing_numbers_do_not_change(self):
        with api.db_connection() as connection:
            previous = api.get_actor_code(connection, self.logist["sub"])
        external = self.actor("logist", "external-logist")
        self.assertEqual(self.grant(self.logist)["crm_logist_id"], 1)
        company2 = self.actor("logist", "company-second")
        self.assertEqual(self.grant(company2)["crm_logist_id"], 2)
        self.assertFalse(self.grant(self.logist)["changed"])
        with api.db_connection() as connection:
            self.assertEqual(api.get_actor_code(connection, self.logist["sub"]), previous)
        self.assertIsNone(api.get_account_profile(external)["crm_logist_id"])
        self.assertEqual(api.get_account_profile(self.logist)["crm_logist_id"], 1)

    def test_company_invitation_assigns_on_account_creation_only(self):
        invite = api.create_account_invitation("company-invited", "logist", created_by="admin", gpm_company_logist=True)
        account = api.redeem_account_invitation(invite["token"], "Synthetic password 123!")
        profile = api.get_account_profile({"sub": account["account_id"], "role": "logist"})
        self.assertEqual(profile["crm_logist_id"], 1)
        self.assertTrue(profile["is_gpm_company_logist"])
        self.assertIsNone(api.get_account_profile(self.logist)["crm_logist_id"])
        with self.assertRaises(ValueError):
            api.create_account_invitation("invalid-company-worker", "worker", created_by="admin", gpm_company_logist=True)

    def test_worker_and_inactive_logist_cannot_be_granted(self):
        with self.assertRaises(ValueError):
            self.grant(self.worker)
        with api.db_connection() as connection:
            connection.execute(f"UPDATE {api.ACCOUNTS_TABLE_NAME} SET is_active=0 WHERE account_id=?", (self.logist["sub"],))
        with self.assertRaises(ValueError):
            self.grant(self.logist)

    def test_revoked_id_is_not_reused_and_inactive_accounts_are_not_recipients(self):
        self.grant(self.logist)
        with api.db_connection() as connection:
            ids.revoke(connection, self.logist["sub"])
        with self.assertRaises(ValueError):
            api.resolve_company_logist_recipient("#1")
        second = self.actor("logist", "new-company-logist")
        self.assertEqual(self.grant(second)["crm_logist_id"], 2)
        self.assertEqual(self.grant(self.logist)["crm_logist_id"], 1)
        with api.db_connection() as connection:
            connection.execute(f"UPDATE {api.ACCOUNTS_TABLE_NAME} SET is_active=0 WHERE account_id=?", (self.logist["sub"],))
        with self.assertRaises(ValueError):
            api.resolve_company_logist_recipient(1)

    def test_simultaneous_enrollment_has_unique_ids(self):
        second = self.actor("logist", "parallel-company")
        barrier = Barrier(2)
        def enroll(actor):
            barrier.wait()
            return self.grant(actor)["crm_logist_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(enroll, [self.logist, second]))
        self.assertEqual(sorted(result), [1, 2])

    def test_invalid_ids_never_fall_back_to_phone(self):
        for value in (None, True, False, 0, "#0", "-1", "#1.0", "1e1", 1.0, "#1000000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ids.parse_id(value)
        self.assertEqual(ids.parse_id(" #1 "), 1)

    def test_lookup_requires_integration_token_and_returns_only_routing_metadata(self):
        self.grant(self.logist)
        with patch.dict(api.os.environ, {"GPM_APP_API_TOKEN": "SyntheticIntegrationToken"}):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(api.get_company_logist_recipient("1", Response(), "wrong"))
            self.assertEqual(caught.exception.status_code, 401)
            result = asyncio.run(api.get_company_logist_recipient("1", Response(), "SyntheticIntegrationToken"))
            self.assertEqual(result, {"crm_logist_id": 1, "account_id": self.logist["sub"]})
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(api.get_company_logist_recipient("999", Response(), "SyntheticIntegrationToken"))
            self.assertEqual(caught.exception.status_code, 404)

    def publish(self, payload):
        request = SimpleNamespace(json=AsyncMock(return_value=payload))
        return asyncio.run(api.publish_order_payload(request, integration=True))

    def payload(self, code="#1"):
        payload = sample_payload()
        payload.update(source_system="workstaff", source_instance=api.CRM_SYNC_INSTANCE, logist_crm_id=code)
        return payload

    def test_id_publication_binds_account_without_changing_phone_or_order_number(self):
        self.grant(self.logist)
        saved = self.publish(self.payload())["order"]
        self.assertEqual(saved["logist_account_id"], self.logist["sub"])
        self.assertEqual(saved["external_order_id"], "ORDER-1")
        self.assertEqual(saved["logist_phone"], "")
        self.assertEqual(api.get_account_profile(self.logist)["phone"], "")
        repeat = self.publish(self.payload())["order"]
        self.assertEqual(repeat["logist_account_id"], self.logist["sub"])
        self.assertEqual(len(api.list_orders()), 1)

    def test_id_rejects_ambiguous_phone_wrong_source_unknown_id_and_retargeting(self):
        self.grant(self.logist)
        for changes in ({"logist_phone": "+70000000000"}, {"source_instance": "https://other.example"}, {"logist_crm_id": "#999"}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException):
                self.publish({**self.payload(), **changes})
        saved = self.publish(self.payload())["order"]
        other = self.actor("logist", "other-company")
        self.grant(other)
        with self.assertRaises(HTTPException) as caught:
            self.publish(self.payload("#2"))
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(api.get_order(saved["id"])["logist_account_id"], self.logist["sub"])

    def test_existing_phone_integration_remains_compatible(self):
        api.update_account_profile(self.logist, {"phone": "+70000000000"})
        payload = self.payload()
        payload.pop("logist_crm_id")
        payload["logist_phone"] = "+70000000000"
        saved = self.publish(payload)["order"]
        self.assertEqual(saved["logist_account_id"], self.logist["sub"])
        self.assertIsNone(api.get_account_profile(self.logist)["crm_logist_id"])
