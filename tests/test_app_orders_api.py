import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

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
        with patch.dict(
            os.environ,
            {
                "GPM_APP_CLIENT_USERNAME": "client-1",
                "GPM_APP_CLIENT_PASSWORD": "a-strong-test-password",
            },
            clear=True,
        ):
            account = api.check_app_credentials(
                "client-1",
                "a-strong-test-password",
            )

        self.assertEqual(account["role"], "client")

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
            token = api.create_access_token("client-1", "client")
            payload = api.decode_access_token(token)

        self.assertEqual(payload["sub"], "client-1")
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


if __name__ == "__main__":
    unittest.main()
