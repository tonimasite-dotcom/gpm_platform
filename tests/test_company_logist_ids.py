import asyncio
import os
import io
import json
from pathlib import Path
from contextlib import redirect_stdout
from uuid import uuid4
import unittest
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.responses import Response

from app import app_orders_api as api
from app import crm_logist_ids as ids
from app import company_logist_cli
from tests.test_app_orders_api import sample_payload
from tests import test_tester_feedback as feedback


class CompanyLogistIdTests(unittest.TestCase):
    setUp = feedback.TesterFeedbackTests.setUp
    actor = feedback.TesterFeedbackTests.actor

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

    def test_untrusted_registration_metadata_cannot_enable_company_membership(self):
        invite = api.create_account_invitation("external-with-forged-metadata", "logist", created_by="admin")
        account = api.redeem_account_invitation(invite["token"], "Synthetic password 123!",
            audit_details={"gpm_company_logist": True, "crm_logist_id": 1})
        profile = api.get_account_profile({"sub": account["account_id"], "role": "logist"})
        self.assertIsNone(profile["crm_logist_id"])
        self.assertFalse(profile["is_gpm_company_logist"])

    def cli(self, *arguments):
        output = io.StringIO()
        with patch.object(api, "validate_runtime_configuration"), patch("sys.argv", ["company_logist_cli", *arguments]), redirect_stdout(output):
            company_logist_cli.main()
        return output.getvalue()

    def test_trusted_cli_dry_run_does_not_enroll_and_grant_revoke_preserve_identity(self):
        self.cli("grant", "--account-id", self.logist["sub"], "--by", "synthetic-admin")
        self.assertIsNone(api.get_account_profile(self.logist)["crm_logist_id"])
        before = api.get_account_profile(self.logist)
        self.assertIn("#1", self.cli("grant", "--account-id", self.logist["sub"], "--by", "synthetic-admin", "--apply"))
        profile = api.get_account_profile(self.logist)
        self.assertEqual(profile["phone"], before["phone"])
        self.assertEqual(profile["username"], before["username"])
        self.assertEqual(profile["role"], "logist")
        self.cli("revoke", "--account-id", self.logist["sub"], "--by", "synthetic-admin", "--apply")
        self.assertIsNone(api.get_account_profile(self.logist)["crm_logist_id"])

    def test_trusted_cli_can_revoke_inactive_logist_without_reusing_id(self):
        self.cli("grant", "--account-id", self.logist["sub"], "--by", "synthetic-admin", "--apply")
        with api.db_connection() as connection:
            connection.execute(f"UPDATE {api.ACCOUNTS_TABLE_NAME} SET is_active=0 WHERE account_id=?", (self.logist["sub"],))
            account_before = connection.execute(
                f"SELECT * FROM {api.ACCOUNTS_TABLE_NAME} WHERE account_id=?", (self.logist["sub"],)).fetchone()
            membership_before = connection.execute(
                f"SELECT crm_id,assigned_by,assigned_at FROM {ids.MEMBERS} WHERE account_id=?", (self.logist["sub"],)).fetchone()
            actor_before = api.get_actor_code(connection, self.logist["sub"])
        with self.assertRaises(ValueError):
            self.cli("grant", "--account-id", self.logist["sub"], "--by", "synthetic-admin", "--apply")
        self.cli("revoke", "--account-id", self.logist["sub"], "--by", "synthetic-admin")
        with api.db_connection() as connection:
            self.assertTrue(connection.execute(
                f"SELECT enabled FROM {ids.MEMBERS} WHERE account_id=?", (self.logist["sub"],)).fetchone()[0])
        self.assertIn("#1", self.cli("revoke", "--account-id", self.logist["sub"], "--by", "synthetic-admin", "--apply"))
        with api.db_connection() as connection:
            self.assertFalse(connection.execute(
                f"SELECT enabled FROM {ids.MEMBERS} WHERE account_id=?", (self.logist["sub"],)).fetchone()[0])
            self.assertEqual(connection.execute(
                f"SELECT crm_id,assigned_by,assigned_at FROM {ids.MEMBERS} WHERE account_id=?", (self.logist["sub"],)).fetchone(), membership_before)
            self.assertEqual(connection.execute(
                f"SELECT * FROM {api.ACCOUNTS_TABLE_NAME} WHERE account_id=?", (self.logist["sub"],)).fetchone(), account_before)
            self.assertEqual(api.get_actor_code(connection, self.logist["sub"]), actor_before)
            connection.execute(f"UPDATE {api.ACCOUNTS_TABLE_NAME} SET is_active=1 WHERE account_id=?", (self.logist["sub"],))
        with self.assertRaises(ValueError):
            api.resolve_company_logist_recipient("#1")
        second = self.actor("logist", "company-after-inactive-revocation")
        self.assertEqual(self.grant(second)["crm_logist_id"], 2)
        self.assertEqual(self.grant(self.logist)["crm_logist_id"], 1)

    def test_company_invitation_cli_writes_valid_private_json_and_never_prints_token(self):
        path = Path(self.temp.name) / "private-company-invitation.json"
        output = self.cli("invite", "--username", "cli-invited-company", "--by", "synthetic-admin", "--output", str(path))
        invitation = json.loads(path.read_text())["invitation"]
        self.assertNotIn(invitation["token"], output)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        account = api.redeem_account_invitation(invitation["token"], "Synthetic password 123!")
        profile = api.get_account_profile({"sub": account["account_id"], "role": "logist"})
        self.assertEqual(profile["crm_logist_id"], 1)

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


@unittest.skipUnless(os.getenv("GPM_TEST_POSTGRES_URL"), "PostgreSQL CI only")
class CompanyIdPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ["GPM_TEST_POSTGRES_URL"]
        self.schema = "crmids_" + uuid4().hex
        connection = api.psycopg2.connect(self.dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA " + self.schema)
                cursor.execute("SET search_path TO " + self.schema)
                cursor.execute(f"CREATE TABLE {api.TABLE_NAME}(order_id TEXT PRIMARY KEY,data JSONB NOT NULL,updated_at TIMESTAMPTZ DEFAULT NOW())")
            with patch.object(api, "is_postgres_enabled", return_value=True):
                api.create_auth_schema(connection)
                with connection.cursor() as cursor:
                    for account in ("company-one", "company-two", "external"):
                        cursor.execute(f"""INSERT INTO {api.ACCOUNTS_TABLE_NAME}(
                            account_id,username,username_normalized,password_hash,role,created_at,updated_at)
                            VALUES (%s,%s,%s,'synthetic-unused-hash','logist',NOW(),NOW())""",
                            (account, account, account))
                        api.ensure_actor_code(connection, account, "logist")
            ids.ensure_schema(connection)
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(self.drop_schema)

    def connection(self):
        return api.psycopg2.connect(self.dsn, options="-c search_path=" + self.schema)

    def drop_schema(self):
        connection = api.psycopg2.connect(self.dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA " + self.schema + " CASCADE")
            connection.commit()
        finally:
            connection.close()

    def test_concurrent_postgres_grants_allocate_distinct_company_ids(self):
        barrier = Barrier(2)
        def grant(account):
            connection = self.connection()
            try:
                barrier.wait()
                result = ids.grant(connection, account, assigned_by="synthetic-admin")
                connection.commit()
                return result["crm_logist_id"]
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(grant, ["company-one", "company-two"]))
        self.assertEqual(sorted(result), [1, 2])
        connection = self.connection()
        try:
            self.assertIsNone(ids.for_account(connection, "external"))
        finally:
            connection.close()

    def test_rollback_does_not_consume_an_id_or_leave_partial_membership(self):
        connection = self.connection()
        try:
            self.assertEqual(ids.grant(connection, "company-one", assigned_by="test")["crm_logist_id"], 1)
            connection.rollback()
            self.assertIsNone(ids.for_account(connection, "company-one"))
            self.assertEqual(ids.grant(connection, "company-two", assigned_by="test")["crm_logist_id"], 1)
            connection.commit()
        finally:
            connection.close()

    def test_additive_schema_preserves_accounts_profiles_actor_numbers_and_orders(self):
        connection = self.connection()
        tables = [api.ACCOUNTS_TABLE_NAME, api.PROFILES_TABLE_NAME, api.ACTOR_CODES_TABLE_NAME,
                  api.ACTOR_CODE_SEQUENCE_TABLE_NAME, api.TABLE_NAME]
        def snapshot():
            result = {}
            with connection.cursor() as cursor:
                for table in tables:
                    cursor.execute("SELECT * FROM " + table + " ORDER BY 1")
                    result[table] = cursor.fetchall()
            return result
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE " + ids.INVITES)
                cursor.execute("DROP TABLE " + ids.MEMBERS)
                cursor.execute(f"INSERT INTO {api.TABLE_NAME}(order_id,data) VALUES ('SYNTHETIC/26','{{\"number\":\"SYNTHETIC/26\"}}'::jsonb)")
                cursor.execute(f"INSERT INTO {api.PROFILES_TABLE_NAME}(account_id,data) VALUES ('company-one','{{\"phone\":\"+70000000000\"}}'::jsonb)")
            connection.commit()
            before = snapshot()
            ids.ensure_schema(connection)
            self.assertEqual(ids.grant(connection, "company-one", assigned_by="synthetic-admin")["crm_logist_id"], 1)
            self.assertEqual(snapshot(), before)
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name IN (%s,%s)",
                               (self.schema, ids.MEMBERS, ids.INVITES))
                self.assertEqual(cursor.fetchone()[0], 0)
            self.assertEqual(snapshot(), before)
            ids.ensure_schema(connection)
            self.assertEqual(ids.grant(connection, "company-one", assigned_by="synthetic-admin")["crm_logist_id"], 1)
            connection.commit()
            ids.ensure_schema(connection)
            self.assertEqual(ids.for_account(connection, "company-one"), 1)
            self.assertEqual(snapshot(), before)
            connection.commit()
        finally:
            connection.close()

    def test_company_invitation_redeems_atomically_on_real_postgres(self):
        @contextmanager
        def database():
            connection = self.connection()
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()
        with patch.object(api, "db_connection", side_effect=database), patch.object(api, "is_postgres_enabled", return_value=True):
            invitation = api.create_account_invitation("invited-company-pg", "logist",
                created_by="synthetic-admin", gpm_company_logist=True)
            account = api.redeem_account_invitation(invitation["token"], "Synthetic password 123!")
            profile = api.get_account_profile({"sub": account["account_id"], "role": "logist"})
            self.assertEqual(profile["crm_logist_id"], 1)
            external = api.create_account_invitation("invited-external-pg", "logist", created_by="synthetic-admin")
            outsider = api.redeem_account_invitation(external["token"], "Synthetic password 123!")
            self.assertIsNone(api.get_account_profile({"sub": outsider["account_id"], "role": "logist"})["crm_logist_id"])
