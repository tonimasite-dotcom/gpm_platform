import base64
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import account_invite_cli
from app import app_orders_api as api


def sample_payload(*, source: str = "external") -> dict:
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    return {
        "source": source,
        "client_email": "client@example.test",
        "client_phone": "+70000000000",
        "order_data": {
            "order_number": "ORDER-1",
            "completion_date": {"date": scheduled_at},
            "loaders": {"loader_count": 2},
            "info": {
                "address": "Тестовый адрес",
                "address_street": "Тестовая улица",
                "address_number": "1",
                "additional": "",
            },
            "hours": 4,
            "note": "Тестовая заявка",
        },
    }


class ActiveApiTests(unittest.TestCase):
    def test_order_routes_accept_crm_numbers_with_slashes(self) -> None:
        cases = (
            ("/app-api/me/orders/{order_id:path}", "/app-api/me/orders/033/25"),
            ("/app-api/orders/{order_id:path}", "/app-api/orders/033/25"),
            (
                "/app-api/me/orders/{order_id:path}/applications",
                "/app-api/me/orders/033/25/applications",
            ),
            (
                "/app-api/me/orders/{order_id:path}/applications/{application_id}",
                "/app-api/me/orders/033/25/applications/application-1",
            ),
        )

        routes = {route.path: route for route in api.app.routes}
        for route_path, request_path in cases:
            with self.subTest(route=route_path):
                match = routes[route_path].path_regex.fullmatch(request_path)
                self.assertIsNotNone(match)
                self.assertEqual(match.groupdict()["order_id"], "033/25")

    @unittest.skipUnless(
        os.getenv("GPM_TEST_POSTGRES_URL"),
        "GPM_TEST_POSTGRES_URL is only configured in backend CI",
    )
    def test_postgres_account_schema_login_and_revocation(self) -> None:
        dsn = os.environ["GPM_TEST_POSTGRES_URL"]
        if api.psycopg2 is None:
            self.fail("psycopg2 is required for the PostgreSQL integration test")
        connection = api.psycopg2.connect(dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {api.CHAT_READS_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.CHAT_MESSAGES_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.CHAT_THREADS_TABLE_NAME}")
                cursor.execute(
                    f"DROP TABLE IF EXISTS {api.WORKER_VERIFICATIONS_TABLE_NAME}"
                )
                cursor.execute(f"DROP TABLE IF EXISTS {api.PROFILES_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.SESSIONS_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.INVITATIONS_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.AUDIT_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.ACCOUNTS_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.MIGRATIONS_TABLE_NAME}")
                cursor.execute(f"DROP TABLE IF EXISTS {api.TABLE_NAME}")
            connection.commit()
        finally:
            connection.close()

        environment = {
            "GPM_APP_DATABASE_URL": dsn,
            "GPM_APP_CLIENT_USERNAME": "postgres-client",
            "GPM_APP_CLIENT_PASSWORD": "a-strong-test-password",
            "GPM_APP_JWT_SECRET": "x" * 32,
        }
        with patch.dict(os.environ, environment, clear=True):
            api.init_db()
            invitation = api.create_account_invitation(
                "postgres-worker",
                "worker",
                created_by="ci",
            )
            invited_account = api.redeem_account_invitation(
                invitation["token"],
                "Strong synthetic password 42!",
                expected_role="worker",
            )
            invited_worker = api.current_user(
                "Bearer "
                + api.check_app_credentials(
                    "postgres-worker", "Strong synthetic password 42!"
                )["access_token"]
            )
            verification = api.submit_worker_verification(
                invited_worker,
                "npd",
                {"data": {"inn": "000000000000"}},
            )
            account = api.check_app_credentials(
                "postgres-client",
                "a-strong-test-password",
            )
            user = api.current_user(f"Bearer {account['access_token']}")
            api.revoke_session(user)
            with self.assertRaises(HTTPException) as caught:
                api.current_user(f"Bearer {account['access_token']}")

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(invited_account["role"], "worker")
        self.assertEqual(verification["status"], "pending")

    def test_api_lock_contains_all_direct_pins(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]

        def pinned_requirements(filename: str) -> set[str]:
            return {
                line.strip().lower()
                for line in (repository_root / filename)
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }

        direct = pinned_requirements("requirements-api.txt")
        locked = pinned_requirements("requirements-api.lock")
        self.assertLessEqual(direct, locked)

    def test_local_cors_origins_are_exact(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GPM_APP_ALLOWED_ORIGINS": (
                    "http://127.0.0.1:8090,http://localhost:8090"
                )
            },
            clear=False,
        ):
            origins = api.parse_allowed_origins()

        self.assertEqual(
            origins,
            ["http://127.0.0.1:8090", "http://localhost:8090"],
        )
        self.assertNotIn("http://localhost:8091", origins)

    def test_manual_order_keeps_source_and_drops_raw_payload(self) -> None:
        order = api.normalize_external_order(
            sample_payload(source="manual"),
            created_by="client-1",
            created_by_role="client",
        )

        self.assertEqual(order["source"], "manual")
        self.assertEqual(order["source_system"], "gpm-app")
        self.assertEqual(order["created_by"], "client-1")
        self.assertNotIn("source_payload", order)
        self.assertNotEqual(order["created_at"], order["scheduled_at"])

    def test_reimport_preserves_workflow_state(self) -> None:
        incoming = api.normalize_external_order(sample_payload())
        existing = {
            **incoming,
            "status": "IN_PROCESS",
            "assigned_worker_ids": ["worker-1"],
            "applications": [{"id": "application-1"}],
            "created_at": "2026-08-01T00:00:00Z",
        }

        merged = api.merge_existing_workflow_state(incoming, existing)

        self.assertEqual(merged["status"], "IN_PROCESS")
        self.assertEqual(merged["assigned_worker_ids"], ["worker-1"])
        self.assertEqual(merged["applications"], [{"id": "application-1"}])
        self.assertEqual(merged["created_at"], "2026-08-01T00:00:00Z")

    def test_worker_response_redacts_contact_fields(self) -> None:
        order = api.normalize_external_order(sample_payload())
        order["telegram_username"] = "private"
        order["logist_phone"] = "+70000000001"

        visible = api.order_for_user(
            order,
            {"sub": "worker-1", "role": "worker"},
        )

        self.assertNotIn("client_email", visible)
        self.assertNotIn("client_phone", visible)
        self.assertNotIn("telegram_username", visible)
        self.assertNotIn("logist_phone", visible)

    def test_client_only_sees_owned_orders(self) -> None:
        own = api.normalize_external_order(
            sample_payload(source="manual"),
            created_by="client-1",
            created_by_role="client",
        )
        other = {**own, "id": "ORDER-2", "created_by": "client-2"}

        visible = api.orders_for_user(
            [own, other],
            {"sub": "client-1", "role": "client"},
        )

        self.assertEqual([item["id"] for item in visible], ["ORDER-1"])

    def test_logist_only_sees_own_orders(self) -> None:
        assigned_payload = sample_payload()
        assigned_payload["logist_phone"] = "+7 900 111-22-33"
        assigned_payload["order_data"]["order_number"] = "ORDER-ASSIGNED"
        assigned = api.normalize_external_order(assigned_payload)
        assigned["logist_account_id"] = "logist-1"
        other_payload = sample_payload()
        other_payload["logist_phone"] = "8 (900) 999-88-77"
        other_payload["order_data"]["order_number"] = "ORDER-OTHER"
        other = api.normalize_external_order(other_payload)
        other["logist_account_id"] = "logist-2"
        legacy_payload = sample_payload()
        legacy_payload["logist_phone"] = "8 (900) 111-22-33"
        legacy_payload["order_data"]["order_number"] = "ORDER-LEGACY"
        legacy = api.normalize_external_order(legacy_payload)
        unrouted_payload = sample_payload()
        unrouted_payload["logist_phone"] = ""
        unrouted_payload["order_data"]["order_number"] = "ORDER-UNROUTED"
        unrouted = api.normalize_external_order(unrouted_payload)
        published = {**other, "id": "ORDER-PUBLISHED", "status": "PROCESSED"}
        own_manual = api.normalize_external_order(
            sample_payload(source="manual"),
            created_by="logist-1",
            created_by_role="logist",
        )

        visible = api.orders_for_user(
            [assigned, other, legacy, unrouted, published, own_manual],
            {"sub": "logist-1", "role": "logist"},
            profile={"phone": "8 900 111 22 33"},
        )

        self.assertEqual(
            [item["id"] for item in visible],
            ["ORDER-ASSIGNED", "ORDER-LEGACY", "ORDER-1"],
        )

    def test_worker_only_discovers_published_orders_in_profile_cities(self) -> None:
        moscow_payload = sample_payload()
        moscow_payload["city"] = "г. Москва"
        moscow = api.normalize_external_order(moscow_payload)
        moscow["status"] = "PROCESSED"
        petersburg_payload = sample_payload()
        petersburg_payload["city"] = "Санкт-Петербург"
        petersburg_payload["order_data"]["order_number"] = "ORDER-SPB"
        petersburg = api.normalize_external_order(petersburg_payload)
        petersburg["status"] = "PROCESSED"

        visible = api.orders_for_user(
            [moscow, petersburg],
            {"sub": "worker-1", "role": "worker"},
            profile={"cities": ["Казань", "Москва"]},
        )

        self.assertEqual([item["id"] for item in visible], ["ORDER-1"])

    def test_worker_discovers_order_with_city_embedded_in_address(self) -> None:
        payload = sample_payload()
        payload["order_data"]["info"]["address"] = (
            "г Москва, шоссе Алтуфьевское 1-й км"
        )
        order = api.normalize_external_order(payload)
        order["status"] = "PROCESSED"

        self.assertEqual(order["city"], "Москва")
        self.assertTrue(
            api.worker_can_discover_order(order, {"cities": ["Москва"]})
        )

        order["city"] = ""
        self.assertTrue(
            api.worker_can_discover_order(order, {"cities": ["г. Москва"]})
        )
        self.assertFalse(
            api.worker_can_discover_order(order, {"cities": ["Тула"]})
        )

    def test_logist_publication_makes_city_order_visible_to_workers(self) -> None:
        payload = sample_payload()
        payload["city"] = "Москва"
        order = api.normalize_external_order(payload)
        order["logist_account_id"] = "logist-1"
        logist = {"sub": "logist-1", "role": "logist"}
        worker = {"sub": "worker-1", "role": "worker"}
        worker_profile = {"cities": ["Москва", "Казань"]}

        self.assertEqual(
            api.orders_for_user([order], worker, profile=worker_profile), []
        )

        patch = api.validate_order_patch(
            order,
            {"status": "PROCESSED"},
            actor=logist,
            integration=False,
        )
        published = {**order, **patch}

        self.assertEqual(published["status"], "PROCESSED")
        self.assertEqual(
            len(api.orders_for_user([published], worker, profile=worker_profile)),
            1,
        )

    def test_logist_cannot_publish_another_logists_order(self) -> None:
        order = api.normalize_external_order(sample_payload())
        order["logist_account_id"] = "logist-2"

        with self.assertRaises(HTTPException) as caught:
            api.validate_order_patch(
                order,
                {"status": "PROCESSED"},
                actor={"sub": "logist-1", "role": "logist"},
                integration=False,
            )

        self.assertEqual(caught.exception.status_code, 403)

    def test_public_patch_rejects_unknown_fields(self) -> None:
        order = api.normalize_external_order(
            sample_payload(source="manual"),
            created_by="client-1",
            created_by_role="client",
        )

        with self.assertRaises(HTTPException) as caught:
            api.validate_order_patch(
                order,
                {"assigned_worker_ids": ["worker-1"]},
                actor={"sub": "client-1", "role": "client"},
                integration=False,
            )

        self.assertEqual(caught.exception.status_code, 422)

    def test_server_assigns_role_from_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            environment = {
                "GPM_APP_CLIENT_USERNAME": "client-1",
                "GPM_APP_CLIENT_PASSWORD": "a-strong-test-password",
                "GPM_APP_JWT_SECRET": "x" * 32,
                "GPM_APP_SQLITE_DB_FILE": db_path,
            }
            with patch.dict(os.environ, environment, clear=True):
                api.init_db()
                account = api.check_app_credentials(
                    "client-1",
                    "a-strong-test-password",
                )

            self.assertEqual(account["role"], "client")
            self.assertNotEqual(account["account_id"], "client-1")

            connection = sqlite3.connect(db_path)
            try:
                password_hash = connection.execute(
                    f"SELECT password_hash FROM {api.ACCOUNTS_TABLE_NAME}"
                ).fetchone()[0]
                audit_events = connection.execute(
                    f"SELECT event_type, outcome FROM {api.AUDIT_TABLE_NAME}"
                ).fetchall()
            finally:
                connection.close()
            self.assertTrue(password_hash.startswith("scrypt$"))
            self.assertNotIn("a-strong-test-password", password_hash)
            self.assertIn(("account_bootstrapped", "success"), audit_events)
            self.assertIn(("login", "success"), audit_events)

            with patch.dict(
                os.environ,
                {
                    "GPM_APP_ENV": "production",
                    "GPM_APP_JWT_SECRET": "x" * 32,
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                },
                clear=True,
            ):
                api.validate_account_source_configuration()
                db_account = api.check_app_credentials(
                    "client-1",
                    "a-strong-test-password",
                )
                user = api.current_user(f"Bearer {account['access_token']}")
                self.assertEqual(user["sub"], account["account_id"])
                self.assertEqual(user["username"], "client-1")
                api.revoke_session(user)
                with self.assertRaises(HTTPException) as caught:
                    api.current_user(f"Bearer {account['access_token']}")
                api.revoke_session(
                    api.current_user(f"Bearer {db_account['access_token']}")
                )

            self.assertEqual(caught.exception.status_code, 401)

    def test_account_is_locked_after_repeated_failed_logins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            environment = {
                "GPM_APP_WORKER_USERNAME": "worker-1",
                "GPM_APP_WORKER_PASSWORD": "a-strong-test-password",
                "GPM_APP_JWT_SECRET": "x" * 32,
                "GPM_APP_SQLITE_DB_FILE": db_path,
            }
            with patch.dict(os.environ, environment, clear=True):
                api.init_db()
                for _ in range(api.LOGIN_FAILURE_LIMIT):
                    with self.assertRaises(HTTPException):
                        api.check_app_credentials("worker-1", "wrong-password")
                with self.assertRaises(HTTPException) as caught:
                    api.check_app_credentials("worker-1", "a-strong-test-password")

            self.assertEqual(caught.exception.status_code, 401)
            connection = sqlite3.connect(db_path)
            try:
                failed_count, locked_until = connection.execute(
                    f"""
                    SELECT failed_login_count, locked_until
                    FROM {api.ACCOUNTS_TABLE_NAME}
                    """
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(failed_count, api.LOGIN_FAILURE_LIMIT)
            self.assertIsNotNone(locked_until)

    def test_invitation_creates_db_account_and_cannot_be_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            environment = {
                "GPM_APP_JWT_SECRET": "x" * 32,
                "GPM_APP_SQLITE_DB_FILE": db_path,
            }
            with patch.dict(os.environ, environment, clear=True):
                api.init_db()
                invitation = api.create_account_invitation(
                    "tester-client",
                    "client",
                    created_by="owner",
                )
                account = api.redeem_account_invitation(
                    invitation["token"],
                    "Strong synthetic password 42!",
                    expected_role="client",
                )
                logged_in = api.check_app_credentials(
                    "tester-client",
                    "Strong synthetic password 42!",
                )
                with self.assertRaises(HTTPException) as replayed:
                    api.redeem_account_invitation(
                        invitation["token"],
                        "Another strong password 43!",
                        expected_role="client",
                    )

            self.assertEqual(account["role"], "client")
            self.assertEqual(logged_in["account_id"], account["account_id"])
            self.assertEqual(replayed.exception.status_code, 400)
            connection = sqlite3.connect(db_path)
            try:
                token_hash, used_at = connection.execute(
                    f"SELECT token_hash, used_at FROM {api.INVITATIONS_TABLE_NAME}"
                ).fetchone()
                audit_outcomes = connection.execute(
                    f"""
                    SELECT outcome FROM {api.AUDIT_TABLE_NAME}
                    WHERE event_type = 'invitation_redeemed'
                    ORDER BY occurred_at
                    """
                ).fetchall()
            finally:
                connection.close()
            self.assertNotEqual(token_hash, invitation["token"])
            self.assertEqual(token_hash, api.invitation_token_hash(invitation["token"]))
            self.assertIsNotNone(used_at)
            self.assertEqual(audit_outcomes, [("success",), ("failure",)])

    def test_invitation_role_mismatch_does_not_consume_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_JWT_SECRET": "x" * 32,
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                },
                clear=True,
            ):
                api.init_db()
                invitation = api.create_account_invitation(
                    "tester-worker",
                    "worker",
                    created_by="owner",
                )
                with self.assertRaises(HTTPException):
                    api.redeem_account_invitation(
                        invitation["token"],
                        "Strong synthetic password 42!",
                        expected_role="client",
                    )
                with self.assertRaises(HTTPException):
                    api.redeem_account_invitation(
                        invitation["token"],
                        "tester-worker-password-42",
                        expected_role="worker",
                    )
                account = api.redeem_account_invitation(
                    invitation["token"],
                    "Strong synthetic password 42!",
                    expected_role="worker",
                )

            self.assertEqual(account["role"], "worker")

    def test_expired_invitation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_JWT_SECRET": "x" * 32,
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                },
                clear=True,
            ):
                api.init_db()
                invitation = api.create_account_invitation(
                    "tester-logist",
                    "logist",
                    created_by="owner",
                )
                connection = sqlite3.connect(db_path)
                try:
                    connection.execute(
                        f"UPDATE {api.INVITATIONS_TABLE_NAME} SET expires_at = ?",
                        ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),),
                    )
                    connection.commit()
                finally:
                    connection.close()
                with self.assertRaises(HTTPException) as caught:
                    api.redeem_account_invitation(
                        invitation["token"],
                        "Strong synthetic password 42!",
                        expected_role="logist",
                    )

            self.assertEqual(caught.exception.status_code, 400)

    def test_cli_creates_three_role_invitations_in_protected_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "accounts.sqlite3")
            output = Path(temp_dir) / "tester-invitations.json"
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_JWT_SECRET": "x" * 32,
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                },
                clear=True,
            ):
                accounts = account_invite_cli.create_test_user_invitations(
                    prefix="tester-001",
                    created_by="owner",
                    output=output,
                )

            payload = json.loads(output.read_text(encoding="utf-8"))
            invitations = payload["invitations"]
            self.assertEqual(
                {account["role"] for account in accounts},
                {"client", "worker", "logist"},
            )
            self.assertEqual(len(invitations), 3)
            self.assertEqual(len({item["token"] for item in invitations}), 3)
            connection = sqlite3.connect(db_path)
            try:
                token_hashes = {
                    row[0]
                    for row in connection.execute(
                        f"SELECT token_hash FROM {api.INVITATIONS_TABLE_NAME}"
                    ).fetchall()
                }
            finally:
                connection.close()
            self.assertEqual(
                token_hashes,
                {api.invitation_token_hash(item["token"]) for item in invitations},
            )

    def test_terminal_order_cannot_be_cancelled(self) -> None:
        order = api.normalize_external_order(
            sample_payload(source="manual"),
            created_by="client-1",
            created_by_role="client",
        )
        order["status"] = "CONVERTED"

        with self.assertRaises(HTTPException) as caught:
            api.validate_order_patch(
                order,
                {"status": "JUNK"},
                actor={"sub": "client-1", "role": "client"},
                integration=False,
            )

        self.assertEqual(caught.exception.status_code, 409)

    def test_placeholder_integration_token_fails_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                api.check_token(None)

        self.assertEqual(caught.exception.status_code, 503)
        self.assertTrue(api.is_placeholder("admin"))
        self.assertTrue(api.is_placeholder("password"))

    def test_jwt_requires_strong_secret_and_validates_algorithm(self) -> None:
        with patch.dict(
            os.environ,
            {"GPM_APP_JWT_SECRET": "x" * 32},
            clear=False,
        ):
            token = api.create_access_token(
                "account-1",
                "client-1",
                "client",
                "session-1",
                1,
                datetime.now(timezone.utc) + timedelta(hours=12),
            )
            payload = api.decode_access_token(token)

        self.assertEqual(payload["sub"], "account-1")
        self.assertEqual(payload["username"], "client-1")
        self.assertEqual(payload["role"], "client")

        header_part, payload_part, _ = token.split(".")
        invalid_header = api.b64url_encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8")
        )
        signing_input = f"{invalid_header}.{payload_part}"
        with patch.dict(
            os.environ,
            {"GPM_APP_JWT_SECRET": "x" * 32},
            clear=False,
        ):
            forged_token = f"{signing_input}.{api.jwt_sign(signing_input)}"
            with self.assertRaises(HTTPException) as caught:
                api.decode_access_token(forged_token)

        self.assertEqual(caught.exception.status_code, 401)

    def test_sqlite_health_check_executes_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "orders.sqlite3")
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                    "GPM_APP_DATABASE_URL": "",
                    "DATABASE_URL": "",
                },
                clear=False,
            ):
                api.init_db()
                self.assertEqual(api.check_database_health(), "sqlite")

    def test_sqlite_publish_and_patch_are_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "orders.sqlite3")
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                    "GPM_APP_DATABASE_URL": "",
                    "DATABASE_URL": "",
                },
                clear=False,
            ):
                incoming = api.normalize_external_order(sample_payload())
                saved = api.persist_published_order(incoming, actor=None)
                updated = api.patch_order_atomically(
                    saved["id"],
                    {"status": "PROCESSED"},
                    actor=None,
                    integration=True,
                )

                self.assertEqual(updated["status"], "PROCESSED")
                self.assertEqual(api.get_order(saved["id"])["status"], "PROCESSED")

    def test_user_publish_rejects_existing_order_number(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "orders.sqlite3")
            with patch.dict(
                os.environ,
                {
                    "GPM_APP_SQLITE_DB_FILE": db_path,
                    "GPM_APP_DATABASE_URL": "",
                    "DATABASE_URL": "",
                },
                clear=False,
            ):
                incoming = api.normalize_external_order(
                    sample_payload(source="manual"),
                    created_by="client-1",
                    created_by_role="client",
                )
                actor = {"sub": "client-1", "role": "client"}
                api.persist_published_order(incoming, actor=actor)

                with self.assertRaises(HTTPException) as caught:
                    api.persist_published_order(incoming, actor=actor)

        self.assertEqual(caught.exception.status_code, 409)

    def test_worker_verification_submission_review_and_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "verifications.sqlite3")
            upload_dir = os.path.join(temp_dir, "private-uploads")
            environment = {
                "GPM_APP_SQLITE_DB_FILE": db_path,
                "GPM_APP_PRIVATE_UPLOAD_DIR": upload_dir,
                "GPM_APP_DATABASE_URL": "",
                "DATABASE_URL": "",
                "GPM_APP_WORKER_USERNAME": "verification-worker",
                "GPM_APP_WORKER_PASSWORD": "strong-worker-password",
                "GPM_APP_LOGIST_USERNAME": "verification-logist",
                "GPM_APP_LOGIST_PASSWORD": "strong-logist-password",
                "GPM_APP_JWT_SECRET": "x" * 32,
            }
            with patch.dict(os.environ, environment, clear=True):
                api.init_db()
                worker = api.current_user(
                    "Bearer "
                    + api.check_app_credentials(
                        "verification-worker", "strong-worker-password"
                    )["access_token"]
                )
                logist = api.current_user(
                    "Bearer "
                    + api.check_app_credentials(
                        "verification-logist", "strong-logist-password"
                    )["access_token"]
                )
                api.update_account_profile(
                    worker,
                    {
                        "display_name": "Синтетический Исполнитель",
                        "phone": "+70000000000",
                        "date_birth": "01.01.1990",
                        "cities": ["Москва"],
                        "payout_method": "card",
                        "card_last4": "1234",
                    },
                )
                jpeg = b"\xff\xd8\xffsynthetic-passport-image"
                submission = api.submit_worker_verification(
                    worker,
                    "identity",
                    {
                        "data": {
                            "full_name": "Синтетический Исполнитель",
                            "passport_series": "0000",
                            "passport_number": "000000",
                            "issued_at": "01.01.2020",
                            "department_code": "000-000",
                            "issued_by": "Синтетическое подразделение",
                        },
                        "attachment": {
                            "filename": "passport.jpg",
                            "media_type": "image/jpeg",
                            "base64": base64.b64encode(jpeg).decode("ascii"),
                        },
                    },
                )

                self.assertEqual(submission["status"], "pending")
                self.assertNotIn("data", submission)
                self.assertNotIn("attachment_path", submission)
                self.assertEqual(
                    api.get_account_profile(worker)["identity_status"], "pending"
                )
                queue = api.list_worker_verifications(logist)
                self.assertEqual(len(queue), 1)
                self.assertEqual(
                    queue[0]["data"]["passport_number"], "000000"
                )
                path, media_type, filename = api.worker_verification_attachment(
                    logist, submission["submission_id"]
                )
                self.assertEqual(path.read_bytes(), jpeg)
                self.assertEqual(media_type, "image/jpeg")
                self.assertEqual(filename, "passport.jpg")

                api.review_worker_verification(
                    logist,
                    submission["submission_id"],
                    {"status": "verified"},
                )
                self.assertEqual(
                    api.get_account_profile(worker)["identity_status"], "verified"
                )
                self.assertEqual(api.list_worker_verifications(logist), [])

                api.update_account_profile(
                    worker, {"display_name": "Исполнитель После Изменения"}
                )
                profile = api.get_account_profile(worker)
                self.assertEqual(profile["identity_status"], "rejected")
                self.assertIn(
                    "Подайте паспорт повторно",
                    profile["identity_rejection_reason"],
                )

                npd = api.submit_worker_verification(
                    worker,
                    "npd",
                    {"data": {"inn": "000000000000"}},
                )
                self.assertEqual(npd["status"], "pending")
                self.assertFalse(npd["has_attachment"])
                with self.assertRaises(HTTPException) as caught:
                    api.list_worker_verifications(worker)
                self.assertEqual(caught.exception.status_code, 403)

    def test_role_workspaces_are_server_backed_and_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "workspaces.sqlite3")
            environment = {
                "GPM_APP_SQLITE_DB_FILE": db_path,
                "GPM_APP_DATABASE_URL": "",
                "DATABASE_URL": "",
                "GPM_APP_CLIENT_USERNAME": "workspace-client",
                "GPM_APP_CLIENT_PASSWORD": "strong-client-password",
                "GPM_APP_WORKER_USERNAME": "workspace-worker",
                "GPM_APP_WORKER_PASSWORD": "strong-worker-password",
                "GPM_APP_LOGIST_USERNAME": "workspace-logist",
                "GPM_APP_LOGIST_PASSWORD": "strong-logist-password",
                "GPM_APP_JWT_SECRET": "x" * 32,
            }
            with patch.dict(os.environ, environment, clear=True):
                api.init_db()
                client = api.current_user(
                    "Bearer "
                    + api.check_app_credentials(
                        "workspace-client", "strong-client-password"
                    )["access_token"]
                )
                worker = api.current_user(
                    "Bearer "
                    + api.check_app_credentials(
                        "workspace-worker", "strong-worker-password"
                    )["access_token"]
                )
                logist = api.current_user(
                    "Bearer "
                    + api.check_app_credentials(
                        "workspace-logist", "strong-logist-password"
                    )["access_token"]
                )

                profile = api.update_account_profile(
                    worker,
                    {
                        "display_name": "Тестовый исполнитель",
                        "phone": "+70000000000",
                        "date_birth": "01.01.1990",
                        "cities": ["Москва"],
                        "payout_method": "card",
                        "card_last4": "1234",
                    },
                )
                self.assertEqual(profile["display_name"], "Тестовый исполнитель")
                self.assertEqual(profile["profile_completion"], 100)
                self.assertNotEqual(
                    api.get_account_profile(client)["display_name"],
                    profile["display_name"],
                )
                api.update_account_profile(
                    logist,
                    {
                        "display_name": "Тестовый логист",
                        "phone": "+7 900 111-22-33",
                        "email": "logist@example.test",
                        "cities": ["Москва"],
                    },
                )
                self.assertEqual(
                    api.resolve_active_logist_account_id("8 (900) 111-22-33"),
                    logist["sub"],
                )

                payload = sample_payload(source="manual")
                payload["city"] = "Москва"
                payload["order_data"]["loaders"]["loader_count"] = 1
                payload["order_data"]["price_per_hour"] = 700
                order = api.persist_published_order(
                    api.normalize_external_order(
                        payload,
                        created_by=client["sub"],
                        created_by_role="client",
                    ),
                    actor=client,
                )
                order = api.patch_order_atomically(
                    order["id"],
                    {"status": "PROCESSED"},
                    actor=client,
                    integration=False,
                )
                outside_payload = sample_payload(source="manual")
                outside_payload["city"] = "Санкт-Петербург"
                outside_payload["order_data"]["order_number"] = "ORDER-SPB"
                outside = api.persist_published_order(
                    api.normalize_external_order(
                        outside_payload,
                        created_by=client["sub"],
                        created_by_role="client",
                    ),
                    actor=client,
                )
                api.patch_order_atomically(
                    outside["id"],
                    {"status": "PROCESSED"},
                    actor=client,
                    integration=False,
                )
                with self.assertRaises(HTTPException) as caught:
                    api.apply_to_order_atomically(outside["id"], worker)
                self.assertEqual(caught.exception.status_code, 403)
                application = api.apply_to_order_atomically(order["id"], worker)
                api.decide_order_application_atomically(
                    order["id"],
                    application["id"],
                    "APPROVED",
                    client,
                )

                worker_order = api.orders_for_user(
                    api.list_orders(),
                    worker,
                    profile=api.get_account_profile(worker),
                )[0]
                self.assertTrue(worker_order["is_assigned_to_worker"])
                self.assertEqual(worker_order["worker_application_status"], "APPROVED")
                self.assertIn("address", worker_order)
                self.assertEqual(
                    api.account_dashboard(worker)["summary"]["active_orders"], 1
                )

                worker_threads = api.list_account_chat_threads(worker)
                client_threads = api.list_account_chat_threads(client)
                self.assertEqual(len(worker_threads), 2)
                self.assertEqual(len(client_threads), 1)
                self.assertEqual(
                    api.account_dashboard(logist)["summary"]["total_orders"], 0
                )
                worker_client_thread = next(
                    thread
                    for thread in worker_threads
                    if thread["type"] == "clientWorker"
                )
                api.send_account_chat_message(
                    worker_client_thread["id"], "Выхожу на заказ", worker
                )
                logist_threads = api.list_account_chat_threads(logist)
                self.assertFalse(
                    any(
                        thread["order_id"] == order["id"]
                        for thread in logist_threads
                    )
                )
                client_threads = api.list_account_chat_threads(client)
                self.assertTrue(
                    next(
                        thread
                        for thread in client_threads
                        if thread["id"] == worker_client_thread["id"]
                    )["requires_logist_attention"]
                )

                api.patch_order_atomically(
                    order["id"],
                    {"status": "DONE_PENDING"},
                    actor=worker,
                    integration=False,
                )
                api.patch_order_atomically(
                    order["id"],
                    {"status": "CONVERTED"},
                    actor=client,
                    integration=False,
                )
                finance = api.account_finance(worker)
                self.assertEqual(finance["available"], 2800)
                self.assertEqual(len(finance["transactions"]), 1)


if __name__ == "__main__":
    unittest.main()
