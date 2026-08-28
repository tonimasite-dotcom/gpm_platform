import asyncio
import json
import os
import base64
import hashlib
import hmac
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4

import yaml
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yml"
LOCAL_CONFIG_FILE = BASE_DIR / "config.local.yml"
DEFAULT_SQLITE_DB_FILE = BASE_DIR / "gpm_app_orders.sqlite3"
LEGACY_SQLITE_DB_FILE = BASE_DIR / "crm_app_orders.sqlite3"
TABLE_NAME = "gpm_app_orders"
LEGACY_TABLE_NAME = "crm_app_orders"
ACCOUNTS_TABLE_NAME = "gpm_app_accounts"
SESSIONS_TABLE_NAME = "gpm_app_sessions"
AUDIT_TABLE_NAME = "gpm_app_audit_log"
MIGRATIONS_TABLE_NAME = "gpm_app_schema_migrations"
INVITATIONS_TABLE_NAME = "gpm_app_account_invitations"
PROFILES_TABLE_NAME = "gpm_app_profiles"
WORKER_VERIFICATIONS_TABLE_NAME = "gpm_app_worker_verifications"
CHAT_THREADS_TABLE_NAME = "gpm_app_chat_threads"
CHAT_MESSAGES_TABLE_NAME = "gpm_app_chat_messages"
CHAT_READS_TABLE_NAME = "gpm_app_chat_reads"
APP_ROLES = {"client", "worker", "logist"}
ACCOUNT_SCHEMA_VERSION = "0001_db_accounts"
INVITATION_SCHEMA_VERSION = "0002_account_invitations"
WORKSPACE_SCHEMA_VERSION = "0003_role_workspaces"
WORKER_VERIFICATION_SCHEMA_VERSION = "0004_worker_verifications"
ACCESS_TOKEN_TTL = timedelta(hours=12)
INVITATION_TTL = timedelta(days=3)
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_DURATION = timedelta(minutes=15)
PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
MAX_VERIFICATION_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_VERIFICATION_REQUEST_BYTES = 12 * 1024 * 1024
VERIFICATION_TYPES = {"identity", "npd"}
VERIFICATION_ATTACHMENT_MEDIA_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
DADATA_SUGGEST_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
)
ADDRESS_SUGGEST_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
PLACEHOLDER_VALUES = {
    "",
    "admin",
    "change-me",
    "changeme",
    "password",
    "replace-me",
    "secret",
    "token",
}
ORDER_STATUSES = {
    "NEW",
    "PROCESSED",
    "IN_PROCESS",
    "DONE_PENDING",
    "CONVERTED",
    "JUNK",
}
PUBLIC_ORDER_SOURCES = {"manual", "external", "crm"}
WORKFLOW_FIELDS = {"status", "assigned_worker_ids", "applications"}
ALLOWED_STATUS_TRANSITIONS = {
    "NEW": {"PROCESSED", "JUNK"},
    "PROCESSED": {"IN_PROCESS", "JUNK"},
    "IN_PROCESS": {"DONE_PENDING", "JUNK"},
    "DONE_PENDING": {"IN_PROCESS", "CONVERTED", "JUNK"},
    "CONVERTED": set(),
    "JUNK": set(),
}

try:
    import psycopg2
except ImportError:  # pragma: no cover - local SQLite fallback does not need it.
    psycopg2 = None

def read_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


CONFIG = {
    **read_config(),
    **read_config(LOCAL_CONFIG_FILE),
}


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None and value != "":
        return value
    config_value = CONFIG.get(name)
    if config_value is None:
        return default
    return str(config_value)


def parse_allowed_origins() -> list[str]:
    raw = get_setting(
        "GPM_APP_ALLOWED_ORIGINS",
        "http://127.0.0.1:8090,http://localhost:8090",
    ) or ""
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def is_placeholder(value: str | None) -> bool:
    return (value or "").strip().lower() in PLACEHOLDER_VALUES


def is_production_environment() -> bool:
    return (get_setting("GPM_APP_ENV", "development") or "").strip().lower() in {
        "prod",
        "production",
    }


def validate_runtime_configuration() -> None:
    if not is_production_environment():
        return

    if not postgres_dsn():
        raise RuntimeError("GPM_APP_DATABASE_URL is required in production")

    origins = parse_allowed_origins()
    if os.getenv("GPM_APP_ALLOWED_ORIGINS") is None:
        raise RuntimeError("GPM_APP_ALLOWED_ORIGINS must be set in production env")
    if not origins or "*" in origins:
        raise RuntimeError("explicit GPM_APP_ALLOWED_ORIGINS are required in production")
    for origin in origins:
        parsed_origin = urlsplit(origin)
        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.netloc
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise RuntimeError("GPM_APP_ALLOWED_ORIGINS contains an invalid origin")

    required_secrets = {
        "GPM_APP_API_TOKEN": get_setting("GPM_APP_API_TOKEN"),
        "GPM_APP_JWT_SECRET": get_setting("GPM_APP_JWT_SECRET"),
    }
    for name, value in required_secrets.items():
        if is_placeholder(value):
            raise RuntimeError(f"{name} must be configured in production")

    jwt_value = required_secrets["GPM_APP_JWT_SECRET"] or ""
    if len(jwt_value.encode("utf-8")) < 32:
        raise RuntimeError("GPM_APP_JWT_SECRET must contain at least 32 bytes")

    private_upload_setting = get_setting("GPM_APP_PRIVATE_UPLOAD_DIR")
    if not private_upload_setting:
        raise RuntimeError("GPM_APP_PRIVATE_UPLOAD_DIR must be set in production env")
    if not Path(private_upload_setting).is_absolute():
        raise RuntimeError("GPM_APP_PRIVATE_UPLOAD_DIR must be an absolute path")

def postgres_dsn() -> str | None:
    dsn = get_setting("GPM_APP_DATABASE_URL") or get_setting("DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def sqlite_db_file() -> Path:
    configured = get_setting("GPM_APP_SQLITE_DB_FILE")
    if configured:
        return Path(configured)
    if LEGACY_SQLITE_DB_FILE.exists():
        return LEGACY_SQLITE_DB_FILE
    return DEFAULT_SQLITE_DB_FILE


def private_upload_dir() -> Path:
    configured = get_setting("GPM_APP_PRIVATE_UPLOAD_DIR")
    if configured:
        return Path(configured)
    return sqlite_db_file().parent / ".private_uploads"


app = FastAPI(title="GPM App Orders API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


def is_postgres_enabled() -> bool:
    return bool(postgres_dsn())


@contextmanager
def db_connection():
    dsn = postgres_dsn()
    if dsn:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required when GPM_APP_DATABASE_URL is set")
        connection = psycopg2.connect(dsn)
        try:
            yield connection
        finally:
            connection.close()
        return

    db_file = sqlite_db_file()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_file)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _is_sqlite_connection(connection: Any) -> bool:
    return isinstance(connection, sqlite3.Connection)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_db_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def create_auth_schema(connection: Any) -> None:
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE_NAME} (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {ACCOUNTS_TABLE_NAME} (
                    account_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('client', 'worker', 'logist')),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TIMESTAMPTZ,
                    token_version INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_login_at TIMESTAMPTZ
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {INVITATIONS_TABLE_NAME} (
                    invitation_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('client', 'worker', 'logist')),
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    used_at TIMESTAMPTZ,
                    revoked_at TIMESTAMPTZ,
                    account_id TEXT REFERENCES {ACCOUNTS_TABLE_NAME}(account_id)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS gpm_app_invitations_username_idx
                ON {INVITATIONS_TABLE_NAME}(username_normalized)
                """
            )
            cursor.execute(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS gpm_app_invitations_active_username_idx
                ON {INVITATIONS_TABLE_NAME}(username_normalized)
                WHERE used_at IS NULL AND revoked_at IS NULL
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SESSIONS_TABLE_NAME} (
                    session_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
                    token_version INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked_at TIMESTAMPTZ
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS gpm_app_sessions_account_idx
                ON {SESSIONS_TABLE_NAME}(account_id)
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {AUDIT_TABLE_NAME} (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    actor_account_id TEXT,
                    actor_username TEXT,
                    event_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS gpm_app_audit_occurred_idx
                ON {AUDIT_TABLE_NAME}(occurred_at)
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PROFILES_TABLE_NAME} (
                    account_id TEXT PRIMARY KEY REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {WORKER_VERIFICATIONS_TABLE_NAME} (
                    submission_id TEXT PRIMARY KEY,
                    worker_account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
                    verification_type TEXT NOT NULL CHECK (
                        verification_type IN ('identity', 'npd')
                    ),
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'verified', 'rejected')
                    ),
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    attachment_name TEXT,
                    attachment_media_type TEXT,
                    attachment_path TEXT,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    reviewed_at TIMESTAMPTZ,
                    reviewer_account_id TEXT REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
                    rejection_reason TEXT
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS gpm_app_worker_verifications_queue_idx
                ON {WORKER_VERIFICATIONS_TABLE_NAME}(status, submitted_at)
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CHAT_THREADS_TABLE_NAME} (
                    thread_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    thread_type TEXT NOT NULL CHECK (
                        thread_type IN ('clientLogist', 'workerLogist', 'clientWorker', 'support')
                    ),
                    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                    requires_attention BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(order_id, thread_type)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CHAT_MESSAGES_TABLE_NAME} (
                    message_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES {CHAT_THREADS_TABLE_NAME}(thread_id),
                    sender_account_id TEXT,
                    sender_role TEXT NOT NULL CHECK (
                        sender_role IN ('client', 'worker', 'logist', 'system')
                    ),
                    sender_name TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    is_system BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS gpm_app_chat_messages_thread_idx
                ON {CHAT_MESSAGES_TABLE_NAME}(thread_id, created_at)
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CHAT_READS_TABLE_NAME} (
                    thread_id TEXT NOT NULL REFERENCES {CHAT_THREADS_TABLE_NAME}(thread_id),
                    account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
                    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(thread_id, account_id)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO {MIGRATIONS_TABLE_NAME}(version)
                VALUES (%s)
                ON CONFLICT (version) DO NOTHING
                """,
                (ACCOUNT_SCHEMA_VERSION,),
            )
            cursor.execute(
                f"""
                INSERT INTO {MIGRATIONS_TABLE_NAME}(version)
                VALUES (%s)
                ON CONFLICT (version) DO NOTHING
                """,
                (INVITATION_SCHEMA_VERSION,),
            )
            cursor.execute(
                f"""
                INSERT INTO {MIGRATIONS_TABLE_NAME}(version)
                VALUES (%s)
                ON CONFLICT (version) DO NOTHING
                """,
                (WORKSPACE_SCHEMA_VERSION,),
            )
            cursor.execute(
                f"""
                INSERT INTO {MIGRATIONS_TABLE_NAME}(version)
                VALUES (%s)
                ON CONFLICT (version) DO NOTHING
                """,
                (WORKER_VERIFICATION_SCHEMA_VERSION,),
            )
        return

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE_NAME} (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ACCOUNTS_TABLE_NAME} (
            account_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            username_normalized TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('client', 'worker', 'logist')),
            is_active INTEGER NOT NULL DEFAULT 1,
            failed_login_count INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            token_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login_at TEXT
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {INVITATIONS_TABLE_NAME} (
            invitation_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            username_normalized TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('client', 'worker', 'logist')),
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            revoked_at TEXT,
            account_id TEXT REFERENCES {ACCOUNTS_TABLE_NAME}(account_id)
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS gpm_app_invitations_username_idx
        ON {INVITATIONS_TABLE_NAME}(username_normalized)
        """
    )
    connection.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS gpm_app_invitations_active_username_idx
        ON {INVITATIONS_TABLE_NAME}(username_normalized)
        WHERE used_at IS NULL AND revoked_at IS NULL
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SESSIONS_TABLE_NAME} (
            session_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
            token_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS gpm_app_sessions_account_idx
        ON {SESSIONS_TABLE_NAME}(account_id)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT_TABLE_NAME} (
            event_id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actor_account_id TEXT,
            actor_username TEXT,
            event_type TEXT NOT NULL,
            outcome TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            details TEXT NOT NULL DEFAULT '{{}}'
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS gpm_app_audit_occurred_idx
        ON {AUDIT_TABLE_NAME}(occurred_at)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {PROFILES_TABLE_NAME} (
            account_id TEXT PRIMARY KEY REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
            data TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {WORKER_VERIFICATIONS_TABLE_NAME} (
            submission_id TEXT PRIMARY KEY,
            worker_account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
            verification_type TEXT NOT NULL CHECK (
                verification_type IN ('identity', 'npd')
            ),
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'verified', 'rejected')
            ),
            data TEXT NOT NULL DEFAULT '{{}}',
            attachment_name TEXT,
            attachment_media_type TEXT,
            attachment_path TEXT,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewer_account_id TEXT REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
            rejection_reason TEXT
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS gpm_app_worker_verifications_queue_idx
        ON {WORKER_VERIFICATIONS_TABLE_NAME}(status, submitted_at)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {CHAT_THREADS_TABLE_NAME} (
            thread_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            thread_type TEXT NOT NULL CHECK (
                thread_type IN ('clientLogist', 'workerLogist', 'clientWorker', 'support')
            ),
            is_archived INTEGER NOT NULL DEFAULT 0,
            requires_attention INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(order_id, thread_type)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {CHAT_MESSAGES_TABLE_NAME} (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES {CHAT_THREADS_TABLE_NAME}(thread_id),
            sender_account_id TEXT,
            sender_role TEXT NOT NULL CHECK (
                sender_role IN ('client', 'worker', 'logist', 'system')
            ),
            sender_name TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS gpm_app_chat_messages_thread_idx
        ON {CHAT_MESSAGES_TABLE_NAME}(thread_id, created_at)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {CHAT_READS_TABLE_NAME} (
            thread_id TEXT NOT NULL REFERENCES {CHAT_THREADS_TABLE_NAME}(thread_id),
            account_id TEXT NOT NULL REFERENCES {ACCOUNTS_TABLE_NAME}(account_id),
            read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(thread_id, account_id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT OR IGNORE INTO {MIGRATIONS_TABLE_NAME}(version) VALUES (?)
        """,
        (ACCOUNT_SCHEMA_VERSION,),
    )
    connection.execute(
        f"""
        INSERT OR IGNORE INTO {MIGRATIONS_TABLE_NAME}(version) VALUES (?)
        """,
        (INVITATION_SCHEMA_VERSION,),
    )
    connection.execute(
        f"""
        INSERT OR IGNORE INTO {MIGRATIONS_TABLE_NAME}(version) VALUES (?)
        """,
        (WORKSPACE_SCHEMA_VERSION,),
    )
    connection.execute(
        f"""
        INSERT OR IGNORE INTO {MIGRATIONS_TABLE_NAME}(version) VALUES (?)
        """,
        (WORKER_VERIFICATION_SCHEMA_VERSION,),
    )


def count_accounts_in_connection(connection: Any, *, active_only: bool = False) -> int:
    predicate = " WHERE is_active = TRUE" if active_only else ""
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {ACCOUNTS_TABLE_NAME}{predicate}")
            return int(cursor.fetchone()[0])
    predicate = " WHERE is_active = 1" if active_only else ""
    row = connection.execute(
        f"SELECT COUNT(*) FROM {ACCOUNTS_TABLE_NAME}{predicate}"
    ).fetchone()
    return int(row[0]) if row else 0


def database_has_active_accounts() -> bool:
    try:
        with db_connection() as connection:
            return count_accounts_in_connection(connection, active_only=True) > 0
    except Exception:
        return False


def record_audit_event_in_connection(
    connection: Any,
    *,
    event_type: str,
    outcome: str,
    actor_account_id: str | None = None,
    actor_username: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    values = (
        str(uuid4()),
        serialize_datetime(utc_now()),
        actor_account_id,
        actor_username,
        event_type,
        outcome,
        target_type,
        target_id,
        json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
    )
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {AUDIT_TABLE_NAME}(
                    event_id, occurred_at, actor_account_id, actor_username,
                    event_type, outcome, target_type, target_id, details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                values,
            )
        return
    connection.execute(
        f"""
        INSERT INTO {AUDIT_TABLE_NAME}(
            event_id, occurred_at, actor_account_id, actor_username,
            event_type, outcome, target_type, target_id, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def bootstrap_configured_accounts(connection: Any) -> int:
    if count_accounts_in_connection(connection) > 0:
        return 0

    accounts = configured_app_accounts(strict=is_production_environment())
    for account in accounts:
        account_id = str(uuid4())
        username = account["username"].strip()
        values = (
            account_id,
            username,
            normalize_username(username),
            hash_password(account["password"]),
            account["role"],
            serialize_datetime(utc_now()),
            serialize_datetime(utc_now()),
        )
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {ACCOUNTS_TABLE_NAME}(
                        account_id, username, username_normalized, password_hash,
                        role, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (username_normalized) DO NOTHING
                    """,
                    values,
                )
        else:
            connection.execute(
                f"""
                INSERT OR IGNORE INTO {ACCOUNTS_TABLE_NAME}(
                    account_id, username, username_normalized, password_hash,
                    role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        record_audit_event_in_connection(
            connection,
            event_type="account_bootstrapped",
            outcome="success",
            actor_account_id=account_id,
            actor_username=username,
            target_type="account",
            target_id=account_id,
            details={"role": account["role"]},
        )
    return len(accounts)


def init_db() -> None:
    if is_postgres_enabled():
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        order_id TEXT PRIMARY KEY,
                        data JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            create_auth_schema(connection)
            bootstrap_configured_accounts(connection)
            connection.commit()
        return

    with db_connection() as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                order_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LEGACY_TABLE_NAME} (
                order_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            f"""
            INSERT OR IGNORE INTO {TABLE_NAME}(order_id, data, updated_at)
            SELECT order_id, data, updated_at FROM {LEGACY_TABLE_NAME}
            """
        )
        create_auth_schema(connection)
        bootstrap_configured_accounts(connection)


def check_token(token: str | None) -> None:
    expected = get_setting("GPM_APP_API_TOKEN") or get_setting("CRM_API_KEY")
    if is_placeholder(expected):
        raise HTTPException(status_code=503, detail="integration auth is not configured")
    if not token or not secure_compare(token, expected or ""):
        raise HTTPException(status_code=401, detail="invalid app token")


def secure_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def jwt_secret() -> str:
    secret = get_setting("GPM_APP_JWT_SECRET")
    if is_placeholder(secret) or len((secret or "").encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="app auth is not configured")
    return secret or ""


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def jwt_sign(message: str) -> str:
    signature = hmac.new(
        jwt_secret().encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return b64url_encode(signature)


def create_access_token(
    account_id: str,
    username: str,
    role: str,
    session_id: str,
    token_version: int,
    expires_at: datetime,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": account_id,
        "username": username,
        "role": role,
        "sid": session_id,
        "ver": token_version,
        "iat": now,
        "exp": int(expires_at.timestamp()),
    }
    signing_input = ".".join(
        [
            b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    return f"{signing_input}.{jwt_sign(signing_input)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature = token.split(".", 2)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="invalid bearer token") from error

    signing_input = f"{header_part}.{payload_part}"
    expected_signature = jwt_sign(signing_input)
    if not secure_compare(signature, expected_signature):
        raise HTTPException(status_code=401, detail="invalid bearer token")

    try:
        header = json.loads(b64url_decode(header_part))
        payload = json.loads(b64url_decode(payload_part))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="invalid bearer token") from error

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="invalid bearer token")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    try:
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="invalid bearer token") from error
    if expires_at < int(time.time()):
        raise HTTPException(status_code=401, detail="bearer token expired")

    return payload


def current_user(authorization: str | None) -> dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="authorization required")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="authorization required")

    payload = decode_access_token(token)
    account_id = str(payload.get("sub") or "")
    session_id = str(payload.get("sid") or "")
    role = str(payload.get("role") or "")
    try:
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="invalid bearer token") from error
    if not account_id or not session_id or role not in APP_ROLES or token_version < 1:
        raise HTTPException(status_code=401, detail="invalid bearer token")

    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT a.account_id, a.username, a.role, a.is_active,
                           a.token_version, s.expires_at, s.revoked_at,
                           s.token_version
                    FROM {SESSIONS_TABLE_NAME} s
                    JOIN {ACCOUNTS_TABLE_NAME} a ON a.account_id = s.account_id
                    WHERE s.session_id = %s
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
        else:
            row = connection.execute(
                f"""
                SELECT a.account_id, a.username, a.role, a.is_active,
                       a.token_version, s.expires_at, s.revoked_at,
                       s.token_version
                FROM {SESSIONS_TABLE_NAME} s
                JOIN {ACCOUNTS_TABLE_NAME} a ON a.account_id = s.account_id
                WHERE s.session_id = ?
                """,
                (session_id,),
            ).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    session_expires_at = parse_db_datetime(row[5])
    if (
        str(row[0]) != account_id
        or str(row[2]) != role
        or not bool(row[3])
        or int(row[4]) != token_version
        or int(row[7]) != token_version
        or row[6] is not None
        or session_expires_at is None
        or session_expires_at <= utc_now()
    ):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return {
        **payload,
        "sub": account_id,
        "username": str(row[1]),
        "role": str(row[2]),
    }


async def authenticated_user(authorization: str | None) -> dict[str, Any]:
    return await asyncio.to_thread(current_user, authorization)


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password is required")
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        maxmem=64 * 1024 * 1024,
        dklen=32,
    )
    return "$".join(
        [
            "scrypt",
            str(PASSWORD_SCRYPT_N),
            str(PASSWORD_SCRYPT_R),
            str(PASSWORD_SCRYPT_P),
            b64url_encode(salt),
            b64url_encode(digest),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, salt_value, digest_value = (
            password_hash.split("$", 5)
        )
        if algorithm != "scrypt":
            return False
        n = int(n_value)
        r = int(r_value)
        p = int(p_value)
        if n < 2**14 or n > 2**18 or r < 1 or r > 32 or p < 1 or p > 8:
            return False
        expected = b64url_decode(digest_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=b64url_decode(salt_value),
            n=n,
            r=r,
            p=p,
            maxmem=256 * 1024 * 1024,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


_DUMMY_PASSWORD_HASH: str | None = None


def dummy_password_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("gpm-invalid-password-candidate")
    return _DUMMY_PASSWORD_HASH


def normalize_invitation_token(token: str) -> str:
    return token.strip()


def invitation_token_hash(token: str) -> str:
    return hashlib.sha256(normalize_invitation_token(token).encode("utf-8")).hexdigest()


def validate_invitation_username(username: str) -> str:
    cleaned = username.strip()
    if not 3 <= len(cleaned) <= 64:
        raise ValueError("username must contain between 3 and 64 characters")
    if not all(character.isalnum() or character in {".", "_", "-"} for character in cleaned):
        raise ValueError("username contains unsupported characters")
    if is_placeholder(cleaned):
        raise ValueError("username is not allowed")
    return cleaned


def validate_new_password(password: str, username: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"password must contain between {MIN_PASSWORD_LENGTH} and "
            f"{MAX_PASSWORD_LENGTH} characters"
        )
    if is_placeholder(password) or normalize_username(username) in password.casefold():
        raise ValueError("password is too easy to guess")


def create_account_invitation(
    username: str,
    role: str,
    *,
    created_by: str,
    ttl: timedelta = INVITATION_TTL,
) -> dict[str, Any]:
    username = validate_invitation_username(username)
    normalized_username = normalize_username(username)
    role = role.strip().lower()
    if role not in APP_ROLES:
        raise ValueError("invalid account role")
    if not timedelta(minutes=5) <= ttl <= timedelta(days=14):
        raise ValueError("invitation lifetime must be between 5 minutes and 14 days")
    if not created_by.strip():
        raise ValueError("invitation creator is required")

    token = secrets.token_urlsafe(32)
    token_digest = invitation_token_hash(token)
    now = utc_now()
    expires_at = now + ttl
    invitation_id = str(uuid4())
    with db_connection() as connection:
        if _is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
            account_row = connection.execute(
                f"SELECT account_id FROM {ACCOUNTS_TABLE_NAME} WHERE username_normalized = ?",
                (normalized_username,),
            ).fetchone()
            if account_row is not None:
                raise ValueError("an account with this username already exists")
            connection.execute(
                f"""
                UPDATE {INVITATIONS_TABLE_NAME}
                SET revoked_at = ?
                WHERE username_normalized = ? AND used_at IS NULL AND revoked_at IS NULL
                """,
                (serialize_datetime(now), normalized_username),
            )
            connection.execute(
                f"""
                INSERT INTO {INVITATIONS_TABLE_NAME}(
                    invitation_id, token_hash, username, username_normalized,
                    role, created_by, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invitation_id,
                    token_digest,
                    username,
                    normalized_username,
                    role,
                    created_by.strip()[:120],
                    serialize_datetime(now),
                    serialize_datetime(expires_at),
                ),
            )
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT account_id FROM {ACCOUNTS_TABLE_NAME} WHERE username_normalized = %s",
                    (normalized_username,),
                )
                if cursor.fetchone() is not None:
                    raise ValueError("an account with this username already exists")
                cursor.execute(
                    f"""
                    UPDATE {INVITATIONS_TABLE_NAME}
                    SET revoked_at = %s
                    WHERE username_normalized = %s
                      AND used_at IS NULL AND revoked_at IS NULL
                    """,
                    (serialize_datetime(now), normalized_username),
                )
                cursor.execute(
                    f"""
                    INSERT INTO {INVITATIONS_TABLE_NAME}(
                        invitation_id, token_hash, username, username_normalized,
                        role, created_by, created_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invitation_id,
                        token_digest,
                        username,
                        normalized_username,
                        role,
                        created_by.strip()[:120],
                        serialize_datetime(now),
                        serialize_datetime(expires_at),
                    ),
                )
        record_audit_event_in_connection(
            connection,
            event_type="invitation_created",
            outcome="success",
            actor_username=created_by.strip()[:120],
            target_type="invitation",
            target_id=invitation_id,
            details={"username": username, "role": role, "expires_at": serialize_datetime(expires_at)},
        )
        if not _is_sqlite_connection(connection):
            connection.commit()
    return {
        "invitation_id": invitation_id,
        "token": token,
        "username": username,
        "role": role,
        "expires_at": serialize_datetime(expires_at),
    }


def redeem_account_invitation(
    token: str,
    password: str,
    *,
    expected_role: str | None = None,
    audit_details: dict[str, Any] | None = None,
) -> dict[str, str]:
    normalized_token = normalize_invitation_token(token)
    if not 20 <= len(normalized_token) <= 200:
        raise HTTPException(status_code=400, detail="invalid or expired invitation")
    token_digest = invitation_token_hash(normalized_token)
    now = utc_now()
    result: dict[str, str] | None = None
    failure_reason: str | None = None

    with db_connection() as connection:
        if _is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"""
                SELECT invitation_id, username, role, expires_at, used_at, revoked_at
                FROM {INVITATIONS_TABLE_NAME} WHERE token_hash = ?
                """,
                (token_digest,),
            ).fetchone()
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT invitation_id, username, role, expires_at, used_at, revoked_at
                    FROM {INVITATIONS_TABLE_NAME} WHERE token_hash = %s FOR UPDATE
                    """,
                    (token_digest,),
                )
                row = cursor.fetchone()

        expires_at = parse_db_datetime(row[3]) if row is not None else None
        invitation_valid = bool(
            row is not None
            and expires_at is not None
            and expires_at > now
            and row[4] is None
            and row[5] is None
        )
        role = str(row[2]) if row is not None else ""
        username = str(row[1]) if row is not None else ""
        if not invitation_valid:
            failure_reason = "invalid_or_expired"
        elif expected_role and expected_role.strip().lower() != role:
            failure_reason = "role_mismatch"
        else:
            try:
                validate_new_password(password, username)
            except ValueError:
                failure_reason = "password_policy"

        if failure_reason is None and row is not None:
            normalized_username = normalize_username(username)
            if _is_sqlite_connection(connection):
                existing = connection.execute(
                    f"SELECT account_id FROM {ACCOUNTS_TABLE_NAME} WHERE username_normalized = ?",
                    (normalized_username,),
                ).fetchone()
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT account_id FROM {ACCOUNTS_TABLE_NAME} WHERE username_normalized = %s",
                        (normalized_username,),
                    )
                    existing = cursor.fetchone()
            if existing is not None:
                failure_reason = "username_exists"

        if failure_reason is None and row is not None:
            account_id = str(uuid4())
            password_hash = hash_password(password)
            values = (
                account_id,
                username,
                normalize_username(username),
                password_hash,
                role,
                serialize_datetime(now),
                serialize_datetime(now),
            )
            if _is_sqlite_connection(connection):
                connection.execute(
                    f"""
                    INSERT INTO {ACCOUNTS_TABLE_NAME}(
                        account_id, username, username_normalized, password_hash,
                        role, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                connection.execute(
                    f"""
                    UPDATE {INVITATIONS_TABLE_NAME}
                    SET used_at = ?, account_id = ? WHERE invitation_id = ?
                    """,
                    (serialize_datetime(now), account_id, str(row[0])),
                )
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {ACCOUNTS_TABLE_NAME}(
                            account_id, username, username_normalized, password_hash,
                            role, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        values,
                    )
                    cursor.execute(
                        f"""
                        UPDATE {INVITATIONS_TABLE_NAME}
                        SET used_at = %s, account_id = %s WHERE invitation_id = %s
                        """,
                        (serialize_datetime(now), account_id, str(row[0])),
                    )
            record_audit_event_in_connection(
                connection,
                event_type="invitation_redeemed",
                outcome="success",
                actor_account_id=account_id,
                actor_username=username,
                target_type="account",
                target_id=account_id,
                details={**(audit_details or {}), "role": role, "invitation_id": str(row[0])},
            )
            result = {"account_id": account_id, "username": username, "role": role}
        else:
            record_audit_event_in_connection(
                connection,
                event_type="invitation_redeemed",
                outcome="failure",
                actor_username=username or None,
                target_type="invitation",
                target_id=str(row[0]) if row is not None else None,
                details={**(audit_details or {}), "reason": failure_reason},
            )
        if not _is_sqlite_connection(connection):
            connection.commit()

    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired invitation")
    return result


def configured_app_accounts(*, strict: bool = False) -> list[dict[str, str]]:
    accounts: list[dict[str, str]] = []
    seen_usernames: set[str] = set()

    for role in sorted(APP_ROLES):
        prefix = f"GPM_APP_{role.upper()}"
        username_name = f"{prefix}_USERNAME"
        password_name = f"{prefix}_PASSWORD"
        username = (get_setting(username_name) or "").strip()
        password = get_setting(password_name) or ""
        explicitly_configured = username_name in os.environ or password_name in os.environ
        if not username and not password:
            continue
        if not username or not password:
            raise RuntimeError(f"{prefix}_USERNAME and {prefix}_PASSWORD must be set together")
        if is_placeholder(username) or is_placeholder(password):
            if strict and explicitly_configured:
                raise RuntimeError(f"{prefix} uses an unsafe placeholder credential")
            continue
        normalized_username = normalize_username(username)
        if normalized_username in seen_usernames:
            raise RuntimeError("app account usernames must be unique")
        if strict and len(password) < 12:
            raise RuntimeError("production app account passwords need at least 12 characters")
        seen_usernames.add(normalized_username)
        accounts.append({"username": username, "password": password, "role": role})

    legacy_username = (get_setting("GPM_APP_USERNAME") or "").strip()
    legacy_password = get_setting("GPM_APP_PASSWORD") or ""
    legacy_role = (get_setting("GPM_APP_ROLE") or "").strip().lower()
    if legacy_username or legacy_password or legacy_role:
        if strict:
            raise RuntimeError("legacy shared app credentials are not allowed in production")
        if legacy_role not in APP_ROLES:
            raise RuntimeError("GPM_APP_ROLE must define the server-assigned account role")
        if not is_placeholder(legacy_username) and not is_placeholder(legacy_password):
            if not legacy_username or not legacy_password:
                raise RuntimeError("GPM_APP_USERNAME and GPM_APP_PASSWORD must be set together")
            normalized_username = normalize_username(legacy_username)
            if normalized_username in seen_usernames:
                raise RuntimeError("app account usernames must be unique")
            seen_usernames.add(normalized_username)
            accounts.append(
                {
                    "username": legacy_username,
                    "password": legacy_password,
                    "role": legacy_role,
                }
            )

    return accounts


def validate_account_source_configuration() -> None:
    try:
        accounts = configured_app_accounts(strict=is_production_environment())
    except RuntimeError as error:
        raise RuntimeError("app login bootstrap configuration is invalid") from error
    if accounts or database_has_active_accounts():
        return
    raise RuntimeError("DB-backed app login is not configured")


def _fetch_account_for_login(connection: Any, username: str) -> tuple[Any, ...] | None:
    normalized = normalize_username(username)
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT account_id, username, password_hash, role, is_active,
                       failed_login_count, locked_until, token_version
                FROM {ACCOUNTS_TABLE_NAME}
                WHERE username_normalized = %s
                FOR UPDATE
                """,
                (normalized,),
            )
            return cursor.fetchone()
    return connection.execute(
        f"""
        SELECT account_id, username, password_hash, role, is_active,
               failed_login_count, locked_until, token_version
        FROM {ACCOUNTS_TABLE_NAME}
        WHERE username_normalized = ?
        """,
        (normalized,),
    ).fetchone()


def check_app_credentials(
    username: str,
    password: str,
    *,
    audit_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    submitted_username = username.strip()[:254]
    result: dict[str, Any] | None = None
    auth_failed = False

    with db_connection() as connection:
        if _is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        row = _fetch_account_for_login(connection, submitted_username)
        password_matches = verify_password(
            password,
            str(row[2]) if row is not None else dummy_password_hash(),
        )
        locked_until = parse_db_datetime(row[6]) if row is not None else None
        account_available = bool(row and row[4])
        account_locked = bool(locked_until and locked_until > now)

        if row is None or not password_matches or not account_available or account_locked:
            auth_failed = True
            if row is not None and account_available and not account_locked:
                previous_failures = 0 if locked_until else int(row[5])
                failed_login_count = previous_failures + 1
                new_locked_until = (
                    now + LOGIN_LOCKOUT_DURATION
                    if failed_login_count >= LOGIN_FAILURE_LIMIT
                    else None
                )
                if not _is_sqlite_connection(connection):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"""
                            UPDATE {ACCOUNTS_TABLE_NAME}
                            SET failed_login_count = %s, locked_until = %s,
                                updated_at = %s
                            WHERE account_id = %s
                            """,
                            (
                                failed_login_count,
                                serialize_datetime(new_locked_until)
                                if new_locked_until
                                else None,
                                serialize_datetime(now),
                                str(row[0]),
                            ),
                        )
                else:
                    connection.execute(
                        f"""
                        UPDATE {ACCOUNTS_TABLE_NAME}
                        SET failed_login_count = ?, locked_until = ?, updated_at = ?
                        WHERE account_id = ?
                        """,
                        (
                            failed_login_count,
                            serialize_datetime(new_locked_until)
                            if new_locked_until
                            else None,
                            serialize_datetime(now),
                            str(row[0]),
                        ),
                    )
            record_audit_event_in_connection(
                connection,
                event_type="login",
                outcome="failure",
                actor_account_id=str(row[0]) if row is not None else None,
                actor_username=str(row[1]) if row is not None else submitted_username,
                target_type="account",
                target_id=str(row[0]) if row is not None else None,
                details={**(audit_details or {}), "reason": "invalid_credentials"},
            )
        else:
            account_id = str(row[0])
            account_username = str(row[1])
            role = str(row[3])
            token_version = int(row[7])
            session_id = str(uuid4())
            expires_at = now + ACCESS_TOKEN_TTL
            if not _is_sqlite_connection(connection):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE {ACCOUNTS_TABLE_NAME}
                        SET failed_login_count = 0, locked_until = NULL,
                            last_login_at = %s, updated_at = %s
                        WHERE account_id = %s
                        """,
                        (serialize_datetime(now), serialize_datetime(now), account_id),
                    )
                    cursor.execute(
                        f"""
                        INSERT INTO {SESSIONS_TABLE_NAME}(
                            session_id, account_id, token_version, created_at, expires_at
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            account_id,
                            token_version,
                            serialize_datetime(now),
                            serialize_datetime(expires_at),
                        ),
                    )
            else:
                connection.execute(
                    f"""
                    UPDATE {ACCOUNTS_TABLE_NAME}
                    SET failed_login_count = 0, locked_until = NULL,
                        last_login_at = ?, updated_at = ?
                    WHERE account_id = ?
                    """,
                    (serialize_datetime(now), serialize_datetime(now), account_id),
                )
                connection.execute(
                    f"""
                    INSERT INTO {SESSIONS_TABLE_NAME}(
                        session_id, account_id, token_version, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        account_id,
                        token_version,
                        serialize_datetime(now),
                        serialize_datetime(expires_at),
                    ),
                )
            record_audit_event_in_connection(
                connection,
                event_type="login",
                outcome="success",
                actor_account_id=account_id,
                actor_username=account_username,
                target_type="session",
                target_id=session_id,
                details=audit_details,
            )
            result = {
                "account_id": account_id,
                "username": account_username,
                "role": role,
                "session_id": session_id,
                "token_version": token_version,
                "expires_at": expires_at,
            }
        if not _is_sqlite_connection(connection):
            connection.commit()

    if auth_failed or result is None:
        raise HTTPException(status_code=401, detail="invalid login or password")
    result["access_token"] = create_access_token(
        result["account_id"],
        result["username"],
        result["role"],
        result["session_id"],
        result["token_version"],
        result["expires_at"],
    )
    return result


def revoke_session(user: dict[str, Any], *, audit_details: dict[str, Any] | None = None) -> None:
    session_id = str(user.get("sid") or "")
    account_id = str(user.get("sub") or "")
    if not session_id or not account_id:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    revoked_at = serialize_datetime(utc_now())
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SESSIONS_TABLE_NAME}
                    SET revoked_at = COALESCE(revoked_at, %s)
                    WHERE session_id = %s AND account_id = %s
                    """,
                    (revoked_at, session_id, account_id),
                )
        else:
            connection.execute(
                f"""
                UPDATE {SESSIONS_TABLE_NAME}
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE session_id = ? AND account_id = ?
                """,
                (revoked_at, session_id, account_id),
            )
        record_audit_event_in_connection(
            connection,
            event_type="logout",
            outcome="success",
            actor_account_id=account_id,
            actor_username=str(user.get("username") or ""),
            target_type="session",
            target_id=session_id,
            details=audit_details,
        )
        if not _is_sqlite_connection(connection):
            connection.commit()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fetch_address_suggestions(query: str, city: str) -> list[dict[str, Any]]:
    api_key = get_setting("DADATA_API_KEY")
    if not api_key or api_key == "change-me":
        raise HTTPException(status_code=503, detail="address suggestions are not configured")

    cache_key = f"{city.strip().lower()}|{query.strip().lower()}"
    cached = ADDRESS_SUGGEST_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 300:
        return cached[1]

    search_text = ", ".join(part for part in (city.strip(), query.strip()) if part)
    payload = json.dumps({"query": search_text, "count": 7}).encode("utf-8")
    request = UrlRequest(
        DADATA_SUGGEST_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            raw_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(
                status_code=503,
                detail="address service authorization failed",
            ) from error
        if error.code == 429:
            raise HTTPException(
                status_code=503,
                detail="address suggestion limit reached",
            ) from error
        raise HTTPException(status_code=502, detail="address service error") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="address service unavailable") from error

    suggestions: list[dict[str, Any]] = []
    for item in raw_data.get("suggestions", []):
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            data = {}
        title = str(item.get("value") or "").strip()
        if not title:
            continue

        street = str(
            data.get("street_with_type")
            or data.get("settlement_with_type")
            or data.get("city_with_type")
            or title
        ).strip()
        house_number = str(data.get("house") or "").strip() or None
        latitude = _optional_float(data.get("geo_lat"))
        longitude = _optional_float(data.get("geo_lon"))
        suggestions.append(
            {
                "title": title,
                "details": str(item.get("unrestricted_value") or title).strip(),
                "street": street,
                "house_number": house_number,
                "latitude": latitude,
                "longitude": longitude,
                "complete": bool(house_number and latitude is not None and longitude is not None),
                "provider": "dadata",
            }
        )

    if len(ADDRESS_SUGGEST_CACHE) >= 500:
        ADDRESS_SUGGEST_CACHE.clear()
    ADDRESS_SUGGEST_CACHE[cache_key] = (time.time(), suggestions)
    return suggestions


def save_order(order: dict[str, Any]) -> None:
    init_db()
    with db_connection() as connection:
        write_order_in_connection(connection, order)
        if is_postgres_enabled():
            connection.commit()


def write_order_in_connection(connection: Any, order: dict[str, Any]) -> None:
    serialized = json.dumps(order, ensure_ascii=False)
    if is_postgres_enabled():
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {TABLE_NAME}(order_id, data, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT(order_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = NOW()
                """,
                (order["external_order_id"], serialized),
            )
        return

    connection.execute(
        f"""
        INSERT INTO {TABLE_NAME}(order_id, data, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(order_id) DO UPDATE SET
            data = excluded.data,
            updated_at = CURRENT_TIMESTAMP
        """,
        (order["external_order_id"], serialized),
    )


def list_orders() -> list[dict[str, Any]]:
    init_db()
    if is_postgres_enabled():
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT data FROM {TABLE_NAME} ORDER BY updated_at DESC"
                )
                rows = cursor.fetchall()
        return [
            row[0] if isinstance(row[0], dict) else json.loads(row[0])
            for row in rows
        ]

    with db_connection() as connection:
        rows = connection.execute(
            f"SELECT data FROM {TABLE_NAME} ORDER BY updated_at DESC"
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def get_order(order_id: str) -> dict[str, Any] | None:
    init_db()
    with db_connection() as connection:
        return read_order_in_connection(connection, order_id)


def read_order_in_connection(
    connection: Any,
    order_id: str,
    *,
    for_update: bool = False,
) -> dict[str, Any] | None:
    if is_postgres_enabled():
        lock_clause = " FOR UPDATE" if for_update else ""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT data FROM {TABLE_NAME}
                WHERE order_id = %s OR data->>'id' = %s
                LIMIT 1{lock_clause}
                """,
                (order_id, order_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    row = connection.execute(
        f"SELECT data FROM {TABLE_NAME} WHERE order_id = ? LIMIT 1",
        (order_id,),
    ).fetchone()
    return None if row is None else json.loads(row[0])


def check_database_health() -> str:
    with db_connection() as connection:
        if is_postgres_enabled():
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
        else:
            row = connection.execute("SELECT 1").fetchone()
    if not row or int(row[0]) != 1:
        raise RuntimeError("database health check failed")
    return "postgres" if is_postgres_enabled() else "sqlite"


def bounded_text(
    value: Any,
    field: str,
    *,
    max_length: int,
    required: bool = False,
) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"{field} must be text")
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field} is required")
    if len(text) > max_length:
        raise ValueError(f"{field} is too long")
    if any(ord(character) < 32 and character not in "\t\n" for character in text):
        raise ValueError(f"{field} contains control characters")
    return text


def bounded_integer(
    value: Any,
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be an integer") from error
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be an integer")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return parsed


def normalize_external_order(
    payload: dict[str, Any],
    *,
    created_by: str | None = None,
    created_by_role: str | None = None,
) -> dict[str, Any]:
    order_data = payload.get("order_data")
    if not isinstance(order_data, dict):
        raise ValueError("order_data is required")

    completion_date = order_data.get("completion_date")
    if not isinstance(completion_date, dict):
        raise ValueError("order_data.completion_date is required")

    loaders = order_data.get("loaders")
    if not isinstance(loaders, dict):
        raise ValueError("order_data.loaders is required")

    info = order_data.get("info")
    if not isinstance(info, dict):
        raise ValueError("order_data.info is required")

    order_number = bounded_text(
        order_data.get("order_number"),
        "order_data.order_number",
        max_length=120,
        required=True,
    )
    if any(ord(character) < 32 for character in order_number):
        raise ValueError("order_data.order_number contains control characters")

    additional = info.get("additional", "")
    if isinstance(additional, (list, dict)):
        additional = json.dumps(additional, ensure_ascii=False)
    additional = bounded_text(
        str(additional).replace("\\xa0", " "),
        "order_data.info.additional",
        max_length=2000,
    )

    rf_only = "Только РФ" in additional or "RF only" in additional
    address = bounded_text(
        info.get("address") or info.get("address_street") or "Адрес не указан",
        "order_data.info.address",
        max_length=500,
        required=True,
    )

    source = str(payload.get("source") or "external").strip().lower()
    if source not in PUBLIC_ORDER_SOURCES:
        raise ValueError("unsupported order source")

    scheduled_at = bounded_text(
        completion_date.get("date"),
        "order_data.completion_date.date",
        max_length=80,
        required=True,
    )
    if created_by is not None:
        try:
            parsed_schedule = datetime.fromisoformat(
                scheduled_at.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError("scheduled date must be ISO 8601") from error
        if parsed_schedule.tzinfo is None:
            raise ValueError("scheduled date must include a timezone")
        seconds_until_start = (
            parsed_schedule.astimezone(timezone.utc) - datetime.now(timezone.utc)
        ).total_seconds()
        if seconds_until_start < 30 * 60:
            raise ValueError("scheduled date must be at least 30 minutes ahead")
        if seconds_until_start > 366 * 24 * 60 * 60:
            raise ValueError("scheduled date must be within one year")
    workers_count = bounded_integer(
        loaders.get("loader_count"),
        "order_data.loaders.loader_count",
        minimum=1,
        maximum=100,
    )
    raw_hours = order_data.get("hours")
    if raw_hours in (None, ""):
        raw_hours = order_data.get("min_time", 4)
    hours = bounded_integer(
        raw_hours,
        "order_data.hours",
        minimum=1,
        maximum=24,
    )
    min_time = bounded_integer(
        order_data.get("min_time", hours),
        "order_data.min_time",
        minimum=1,
        maximum=24,
    )
    return {
        "id": order_number,
        "title": f"Заявка № {order_number}",
        "address": address,
        "workers_count": workers_count,
        "hours": hours,
        "description": bounded_text(
            order_data.get("note"),
            "order_data.note",
            max_length=800,
        ),
        "client_email": bounded_text(
            payload.get("client_email"),
            "client_email",
            max_length=254,
        ),
        "client_phone": bounded_text(
            payload.get("client_phone"),
            "client_phone",
            max_length=40,
        ),
        "scheduled_at": scheduled_at,
        "city": bounded_text(
            payload.get("city") or order_data.get("city"),
            "city",
            max_length=120,
        ),
        "source": source,
        "source_system": bounded_text(
            payload.get("source_system")
            or ("gpm-app" if source == "manual" else "workstaff"),
            "source_system",
            max_length=80,
            required=True,
        ),
        "external_order_id": order_number,
        "metro": info.get("metro_station"),
        "national": "yes" if rf_only else "every",
        "min_time": min_time,
        "price_per_hour": order_data.get("price_per_hour"),
        "price_regular": order_data.get("price_regular"),
        "price_state": order_data.get("price_state"),
        "individual_price": order_data.get("individual_price"),
        "legal_price": order_data.get("legal_price"),
        "nationality": "ru" if rf_only else "any",
        "worker_category": order_data.get("worker_category", "loader"),
        "work_mode": order_data.get("work_mode", "rate"),
        "shift_description": order_data.get("shift_description"),
        "telegram_username": str(payload.get("telegram_username") or "").replace("@", ""),
        "logist_phone": bounded_text(
            payload.get("logist_phone"),
            "logist_phone",
            max_length=40,
        ),
        "logist_account_id": "",
        "timezone": order_data.get("timezone", "Europe/Moscow"),
        "additional_info": additional,
        "address_street": info.get("address_street") or address,
        "address_number": info.get("address_number") or "0",
        "address_lat": info.get("address_lat") or 0,
        "address_lon": info.get("address_lon") or 0,
        "status": "NEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": created_by,
        "created_by_role": created_by_role,
        "assigned_worker_ids": [],
        "applications": [],
    }


def merge_existing_workflow_state(
    incoming: dict[str, Any],
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    if not existing:
        return incoming

    merged = dict(incoming)
    for field in WORKFLOW_FIELDS:
        if field in existing:
            merged[field] = existing[field]
    for field in ("created_at", "created_by", "created_by_role"):
        if existing.get(field) not in (None, ""):
            merged[field] = existing[field]
    return merged


def order_for_user(order: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    role = str(user.get("role") or "")
    visible = dict(order)
    visible.pop("source_payload", None)
    assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
    applications = [
        dict(item)
        for item in order.get("applications") or []
        if isinstance(item, dict)
    ]
    visible["assigned_count"] = len(assigned)
    if role == "worker":
        account_id = str(user.get("sub") or "")
        own_application = next(
            (
                item
                for item in applications
                if str(item.get("worker_id") or "") == account_id
            ),
            None,
        )
        visible["worker_application_status"] = (
            str(own_application.get("status") or "") or None
            if own_application is not None
            else None
        )
        visible["is_assigned_to_worker"] = account_id in assigned
        visible.pop("applications", None)
        visible.pop("assigned_worker_ids", None)
        for field in (
            "client_email",
            "client_phone",
            "telegram_username",
            "logist_phone",
            "logist_account_id",
            "created_by",
            "created_by_role",
        ):
            visible.pop(field, None)
        if account_id not in assigned:
            for field in (
                "address",
                "address_street",
                "address_number",
                "address_lat",
                "address_lon",
            ):
                visible.pop(field, None)
    elif role == "client":
        visible.pop("logist_account_id", None)
    return visible


def orders_for_user(
    orders: list[dict[str, Any]],
    user: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    role = str(user.get("role") or "")
    username = str(user.get("sub") or "")
    if role == "client":
        orders = [order for order in orders if order.get("created_by") == username]
    elif role == "logist":
        orders = [
            order
            for order in orders
            if logist_owns_order(order, user, profile=profile)
        ]
    elif role == "worker":
        account_id = str(user.get("sub") or "")
        orders = [
            order
            for order in orders
            if worker_can_discover_order(order, profile)
            or (
                account_id in [
                    str(item) for item in order.get("assigned_worker_ids") or []
                ]
                and str(order.get("status") or "")
                in {"PROCESSED", "IN_PROCESS", "DONE_PENDING", "CONVERTED"}
            )
        ]
    return [order_for_user(order, user) for order in orders]


def normalized_phone_identity(value: Any) -> str:
    digits = "".join(
        character for character in str(value or "") if character.isdigit()
    )
    # Russian phone numbers arrive from CRM in both +7 and 8 formats.
    return digits[-10:] if len(digits) >= 10 else digits


def normalized_city_identity(value: Any) -> str:
    city = " ".join(str(value or "").casefold().replace("ё", "е").split())
    for prefix in ("город ", "г. ", "г "):
        if city.startswith(prefix):
            city = city[len(prefix) :]
            break
    return city.strip(" .,\t\r\n")


def worker_profile_cities(profile: dict[str, Any] | None) -> set[str]:
    if profile is None:
        return set()
    raw_cities = profile.get("cities")
    if isinstance(raw_cities, list):
        values = raw_cities
    else:
        values = [profile.get("city")]
    return {
        normalized
        for value in values
        if (normalized := normalized_city_identity(value))
    }


def worker_can_discover_order(
    order: dict[str, Any], profile: dict[str, Any] | None
) -> bool:
    if str(order.get("status") or "").upper() != "PROCESSED":
        return False
    order_city = normalized_city_identity(order.get("city"))
    return bool(order_city and order_city in worker_profile_cities(profile))


def logist_owns_order(
    order: dict[str, Any],
    user: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
) -> bool:
    account_id = str(user.get("sub") or "")
    routed_account_id = str(order.get("logist_account_id") or "")
    if routed_account_id:
        return routed_account_id == account_id
    if (
        str(order.get("created_by_role") or "") == "logist"
        and str(order.get("created_by") or "") == account_id
    ):
        return True
    routed_phone = normalized_phone_identity(order.get("logist_phone"))
    current_phone = normalized_phone_identity((profile or {}).get("phone"))
    return bool(routed_phone and current_phone and routed_phone == current_phone)


def resolve_active_logist_account_id(logist_phone: Any) -> str:
    target_phone = normalized_phone_identity(logist_phone)
    if len(target_phone) != 10:
        raise ValueError("logist_phone must contain a valid Russian phone number")
    init_db()
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT a.account_id, p.data
                    FROM {ACCOUNTS_TABLE_NAME} a
                    LEFT JOIN {PROFILES_TABLE_NAME} p ON p.account_id = a.account_id
                    WHERE a.role = %s AND a.is_active = TRUE
                    """,
                    ("logist",),
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT a.account_id, p.data
                FROM {ACCOUNTS_TABLE_NAME} a
                LEFT JOIN {PROFILES_TABLE_NAME} p ON p.account_id = a.account_id
                WHERE a.role = ? AND a.is_active = 1
                """,
                ("logist",),
            ).fetchall()
    matches = [
        str(row[0])
        for row in rows
        if normalized_phone_identity(_profile_from_row((row[1],)).get("phone"))
        == target_phone
    ]
    if not matches:
        raise ValueError("logist_phone does not match an active GPM logist")
    if len(matches) > 1:
        raise ValueError("logist_phone matches more than one active GPM logist")
    return matches[0]


def require_role(user: dict[str, Any], *allowed_roles: str) -> None:
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")


def validate_order_patch(
    order: dict[str, Any],
    patch: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    integration: bool,
    actor_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed_fields = WORKFLOW_FIELDS if integration else {"status"}
    unknown_fields = set(patch) - allowed_fields
    if unknown_fields:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported fields: {', '.join(sorted(unknown_fields))}",
        )

    normalized: dict[str, Any] = {}
    if "status" in patch:
        status = str(patch["status"] or "").strip().upper()
        if status not in ORDER_STATUSES:
            raise HTTPException(status_code=422, detail="invalid order status")
        current_status = str(order.get("status") or "").strip().upper()
        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if status != current_status and status not in allowed_targets:
            raise HTTPException(status_code=409, detail="invalid order status transition")
        normalized["status"] = status

    if integration and "assigned_worker_ids" in patch:
        worker_ids = patch["assigned_worker_ids"]
        if not isinstance(worker_ids, list) or len(worker_ids) > 100:
            raise HTTPException(status_code=422, detail="invalid assigned_worker_ids")
        normalized["assigned_worker_ids"] = [
            str(worker_id)[:120]
            for worker_id in worker_ids
            if str(worker_id).strip()
        ]

    if integration and "applications" in patch:
        applications = patch["applications"]
        if not isinstance(applications, list) or len(applications) > 100:
            raise HTTPException(status_code=422, detail="invalid applications")
        if not all(isinstance(item, dict) for item in applications):
            raise HTTPException(status_code=422, detail="invalid applications")
        normalized["applications"] = applications

    if actor is not None:
        role = str(actor.get("role") or "")
        username = str(actor.get("sub") or "")
        target_status = normalized.get("status")
        if role == "logist":
            if not logist_owns_order(order, actor, profile=actor_profile):
                raise HTTPException(status_code=403, detail="insufficient permissions")
        elif role == "client":
            current_status = str(order.get("status") or "").upper()
            owns_order = order.get("created_by") == username
            allowed_transition = (
                current_status == "NEW"
                and target_status in {"PROCESSED", "JUNK"}
            ) or (
                current_status == "DONE_PENDING"
                and target_status in {"CONVERTED", "IN_PROCESS"}
            )
            if not owns_order or not allowed_transition:
                raise HTTPException(status_code=403, detail="insufficient permissions")
        elif role == "worker":
            assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
            if (
                username not in assigned
                or str(order.get("status") or "").upper() != "IN_PROCESS"
                or target_status != "DONE_PENDING"
            ):
                raise HTTPException(status_code=403, detail="insufficient permissions")
        else:
            raise HTTPException(status_code=403, detail="insufficient permissions")

    return normalized


def persist_published_order(
    incoming: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
) -> dict[str, Any]:
    init_db()
    with db_connection() as connection:
        if not is_postgres_enabled():
            connection.execute("BEGIN IMMEDIATE")
        existing = read_order_in_connection(
            connection,
            incoming["external_order_id"],
            for_update=True,
        )
        if actor is not None and existing is not None:
            raise HTTPException(status_code=409, detail="order number already exists")
        order = merge_existing_workflow_state(incoming, existing)
        write_order_in_connection(connection, order)
        if is_postgres_enabled():
            connection.commit()
    return order


def patch_order_atomically(
    order_id: str,
    patch: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    integration: bool,
) -> dict[str, Any]:
    init_db()
    actor_profile = None
    if actor is not None and str(actor.get("role") or "") == "logist":
        actor_profile = get_account_profile(actor)
    with db_connection() as connection:
        if not is_postgres_enabled():
            connection.execute("BEGIN IMMEDIATE")
        order = read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        normalized_patch = validate_order_patch(
            order,
            patch,
            actor=actor,
            actor_profile=actor_profile,
            integration=integration,
        )
        if not normalized_patch:
            raise HTTPException(status_code=422, detail="empty order patch")
        order.update(normalized_patch)
        write_order_in_connection(connection, order)
        if is_postgres_enabled():
            connection.commit()
    return order


COMMON_PROFILE_FIELDS = {
    "display_name",
    "phone",
    "email",
    "telegram",
    "city",
}
ROLE_PROFILE_FIELDS = {
    "client": COMMON_PROFILE_FIELDS
    | {
        "client_type",
        "payment_type",
        "company",
        "inn",
        "kpp",
        "ogrn",
        "contact",
        "address",
        "legal_address",
        "checking_account",
        "bank",
        "bik",
        "correspondent_account",
        "documents_email",
    },
    "worker": COMMON_PROFILE_FIELDS
    | {
        "date_birth",
        "nationality",
        "cities",
        "employment_type",
        "tools",
        "address_city",
        "address_street",
        "address_house",
        "address_apartment",
        "payout_method",
        "card_last4",
        "payout_account",
        "payout_bik",
    },
    "logist": COMMON_PROFILE_FIELDS
    | {
        "department",
        "cities",
        "max_orders",
        "notify_new_orders",
    },
}


def default_profile(user: dict[str, Any]) -> dict[str, Any]:
    username = str(user.get("username") or "Пользователь")
    role = str(user.get("role") or "")
    common: dict[str, Any] = {
        "display_name": username,
        "phone": "",
        "email": "",
        "telegram": "",
        "city": "",
    }
    if role == "client":
        return {
            **common,
            "client_type": "individual",
            "payment_type": "card",
            "company": "",
            "inn": "",
            "kpp": "",
            "ogrn": "",
            "contact": "",
            "address": "",
            "legal_address": "",
            "checking_account": "",
            "bank": "",
            "bik": "",
            "correspondent_account": "",
            "documents_email": "",
        }
    if role == "worker":
        return {
            **common,
            "date_birth": "",
            "nationality": False,
            "cities": [],
            "employment_type": "contract",
            "tools": {"straps": False, "tools": False},
            "address_city": "",
            "address_street": "",
            "address_house": "",
            "address_apartment": "",
            "payout_method": "",
            "card_last4": "",
            "payout_account": "",
            "payout_bik": "",
            "identity_status": "not_submitted",
            "work_status": "not_submitted",
            "npd_status": "not_submitted",
            "rating": 0,
            "success_requests": 0,
            "fail_requests": 0,
        }
    return {
        **common,
        "department": "operations",
        "cities": [],
        "max_orders": 25,
        "notify_new_orders": True,
        "access_level": "standard",
        "can_publish_orders": True,
        "can_approve_workers": True,
    }


def _profile_completion(profile: dict[str, Any], role: str) -> int:
    required = {
        "client": ("display_name", "phone", "email", "address"),
        "worker": (
            "display_name",
            "phone",
            "date_birth",
            "cities",
            "payout_method",
        ),
        "logist": ("display_name",),
    }.get(role, ("display_name",))
    completed = sum(bool(profile.get(field)) for field in required)
    return round(completed * 100 / len(required))


def _profile_from_row(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    raw = row[0]
    if isinstance(raw, dict):
        return dict(raw)
    try:
        decoded = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return {}
    return dict(decoded) if isinstance(decoded, dict) else {}


VERIFICATION_SELECT_FIELDS = """
    submission_id, worker_account_id, verification_type, status, data,
    attachment_name, attachment_media_type, attachment_path, submitted_at,
    reviewed_at, reviewer_account_id, rejection_reason
"""


def _verification_from_row(row: Any, *, include_sensitive: bool) -> dict[str, Any]:
    raw_data = row[4]
    if isinstance(raw_data, dict):
        data = dict(raw_data)
    else:
        try:
            decoded = json.loads(str(raw_data or "{}"))
        except (json.JSONDecodeError, TypeError):
            decoded = {}
        data = dict(decoded) if isinstance(decoded, dict) else {}
    result: dict[str, Any] = {
        "submission_id": str(row[0]),
        "worker_account_id": str(row[1]),
        "verification_type": str(row[2]),
        "status": str(row[3]),
        "has_attachment": bool(row[7]),
        "attachment_name": str(row[5] or ""),
        "attachment_media_type": str(row[6] or ""),
        "submitted_at": serialize_datetime(row[8])
        if isinstance(row[8], datetime)
        else str(row[8] or ""),
        "reviewed_at": serialize_datetime(row[9])
        if isinstance(row[9], datetime)
        else str(row[9] or ""),
        "rejection_reason": str(row[11] or ""),
    }
    if include_sensitive:
        result["data"] = data
    return result


def latest_worker_verifications(account_id: str) -> dict[str, dict[str, Any]]:
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {VERIFICATION_SELECT_FIELDS}
                    FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                    WHERE worker_account_id = %s
                    ORDER BY submitted_at DESC, submission_id DESC
                    """,
                    (account_id,),
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT {VERIFICATION_SELECT_FIELDS}
                FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                WHERE worker_account_id = ?
                ORDER BY submitted_at DESC, submission_id DESC
                """,
                (account_id,),
            ).fetchall()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _verification_from_row(row, include_sensitive=False)
        latest.setdefault(item["verification_type"], item)
    return latest


def _clean_verification_data(
    verification_type: str, raw_data: Any
) -> dict[str, str]:
    if verification_type not in VERIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="verification type not found")
    if not isinstance(raw_data, dict):
        raise HTTPException(status_code=422, detail="data must be an object")
    try:
        if verification_type == "identity":
            allowed = {
                "full_name",
                "passport_series",
                "passport_number",
                "issued_at",
                "department_code",
                "issued_by",
            }
            unknown = set(raw_data) - allowed
            if unknown:
                raise ValueError("unsupported identity fields")
            cleaned = {
                "full_name": bounded_text(
                    raw_data.get("full_name"), "full_name", max_length=200, required=True
                ),
                "passport_series": bounded_text(
                    raw_data.get("passport_series"),
                    "passport_series",
                    max_length=4,
                    required=True,
                ),
                "passport_number": bounded_text(
                    raw_data.get("passport_number"),
                    "passport_number",
                    max_length=6,
                    required=True,
                ),
                "issued_at": bounded_text(
                    raw_data.get("issued_at"), "issued_at", max_length=10, required=True
                ),
                "department_code": bounded_text(
                    raw_data.get("department_code"),
                    "department_code",
                    max_length=7,
                    required=True,
                ),
                "issued_by": bounded_text(
                    raw_data.get("issued_by"), "issued_by", max_length=500, required=True
                ),
            }
            if not cleaned["passport_series"].isdigit() or len(cleaned["passport_series"]) != 4:
                raise ValueError("passport_series must contain 4 digits")
            if not cleaned["passport_number"].isdigit() or len(cleaned["passport_number"]) != 6:
                raise ValueError("passport_number must contain 6 digits")
            code = cleaned["department_code"]
            if len(code) == 6 and code.isdigit():
                code = f"{code[:3]}-{code[3:]}"
                cleaned["department_code"] = code
            if len(code) != 7 or code[3] != "-" or not (code[:3] + code[4:]).isdigit():
                raise ValueError("department_code must use 000-000 format")
            issued_at = cleaned["issued_at"]
            try:
                datetime.strptime(issued_at, "%d.%m.%Y")
            except ValueError as error:
                raise ValueError("issued_at must use DD.MM.YYYY format") from error
            return cleaned

        unknown = set(raw_data) - {"inn"}
        if unknown:
            raise ValueError("unsupported npd fields")
        inn = bounded_text(raw_data.get("inn"), "inn", max_length=12, required=True)
        if len(inn) != 12 or not inn.isdigit():
            raise ValueError("inn must contain 12 digits")
        return {"inn": inn}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _decode_verification_attachment(
    verification_type: str, raw_attachment: Any
) -> tuple[str, str, bytes] | None:
    if raw_attachment is None and verification_type == "npd":
        return None
    if not isinstance(raw_attachment, dict):
        raise HTTPException(status_code=422, detail="passport photo is required")
    try:
        name = Path(
            bounded_text(
                raw_attachment.get("filename"),
                "filename",
                max_length=200,
                required=True,
            )
        ).name
        media_type = bounded_text(
            raw_attachment.get("media_type"),
            "media_type",
            max_length=50,
            required=True,
        ).lower()
        encoded = bounded_text(
            raw_attachment.get("base64"),
            "base64",
            max_length=MAX_VERIFICATION_REQUEST_BYTES,
            required=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if media_type not in VERIFICATION_ATTACHMENT_MEDIA_TYPES:
        raise HTTPException(status_code=422, detail="only JPEG and PNG images are allowed")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail="attachment is not valid base64") from error
    if not content or len(content) > MAX_VERIFICATION_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="attachment exceeds 8 MB")
    if media_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="attachment is not a JPEG image")
    if media_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="attachment is not a PNG image")
    return name, media_type, content


def _write_private_attachment(
    submission_id: str, media_type: str, content: bytes
) -> Path:
    upload_dir = private_upload_dir().resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        upload_dir.chmod(0o700)
    except OSError:
        pass
    path = upload_dir / f"{submission_id}{VERIFICATION_ATTACHMENT_MEDIA_TYPES[media_type]}"
    with path.open("xb") as file:
        file.write(content)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def submit_worker_verification(
    user: dict[str, Any], verification_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    require_role(user, "worker")
    init_db()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="payload must be an object")
    cleaned_data = _clean_verification_data(verification_type, payload.get("data"))
    attachment = _decode_verification_attachment(
        verification_type, payload.get("attachment")
    )
    submission_id = str(uuid4())
    attachment_name = ""
    attachment_media_type = ""
    attachment_path: Path | None = None
    if attachment is not None:
        attachment_name, attachment_media_type, content = attachment
        attachment_path = _write_private_attachment(
            submission_id, attachment_media_type, content
        )
    account_id = str(user.get("sub") or "")
    values = (
        submission_id,
        account_id,
        verification_type,
        json.dumps(cleaned_data, ensure_ascii=False),
        attachment_name or None,
        attachment_media_type or None,
        str(attachment_path) if attachment_path else None,
        serialize_datetime(utc_now()),
    )
    try:
        with db_connection() as connection:
            if not _is_sqlite_connection(connection):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
                        SET status = 'rejected', reviewed_at = NOW(),
                            rejection_reason = 'Заменено новой заявкой'
                        WHERE worker_account_id = %s AND verification_type = %s
                          AND status = 'pending'
                        """,
                        (account_id, verification_type),
                    )
                    cursor.execute(
                        f"""
                        INSERT INTO {WORKER_VERIFICATIONS_TABLE_NAME}(
                            submission_id, worker_account_id, verification_type,
                            status, data, attachment_name, attachment_media_type,
                            attachment_path, submitted_at
                        ) VALUES (%s, %s, %s, 'pending', %s::jsonb, %s, %s, %s, %s)
                        """,
                        values,
                    )
                    record_audit_event_in_connection(
                        connection,
                        event_type="worker_verification_submitted",
                        outcome="success",
                        actor_account_id=account_id,
                        actor_username=str(user.get("username") or ""),
                        target_type="worker_verification",
                        target_id=submission_id,
                        details={"verification_type": verification_type},
                    )
                connection.commit()
            else:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    f"""
                    UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
                    SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP,
                        rejection_reason = 'Заменено новой заявкой'
                    WHERE worker_account_id = ? AND verification_type = ?
                      AND status = 'pending'
                    """,
                    (account_id, verification_type),
                )
                connection.execute(
                    f"""
                    INSERT INTO {WORKER_VERIFICATIONS_TABLE_NAME}(
                        submission_id, worker_account_id, verification_type,
                        status, data, attachment_name, attachment_media_type,
                        attachment_path, submitted_at
                    ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                record_audit_event_in_connection(
                    connection,
                    event_type="worker_verification_submitted",
                    outcome="success",
                    actor_account_id=account_id,
                    actor_username=str(user.get("username") or ""),
                    target_type="worker_verification",
                    target_id=submission_id,
                    details={"verification_type": verification_type},
                )
    except Exception:
        if attachment_path is not None:
            attachment_path.unlink(missing_ok=True)
        raise
    return latest_worker_verifications(account_id)[verification_type]


def my_worker_verifications(user: dict[str, Any]) -> list[dict[str, Any]]:
    require_role(user, "worker")
    init_db()
    return list(latest_worker_verifications(str(user.get("sub") or "")).values())


def _worker_display_name(account_id: str) -> str:
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT a.username, p.data
                    FROM {ACCOUNTS_TABLE_NAME} a
                    LEFT JOIN {PROFILES_TABLE_NAME} p ON p.account_id = a.account_id
                    WHERE a.account_id = %s
                    """,
                    (account_id,),
                )
                row = cursor.fetchone()
        else:
            row = connection.execute(
                f"""
                SELECT a.username, p.data
                FROM {ACCOUNTS_TABLE_NAME} a
                LEFT JOIN {PROFILES_TABLE_NAME} p ON p.account_id = a.account_id
                WHERE a.account_id = ?
                """,
                (account_id,),
            ).fetchone()
    if row is None:
        return "Исполнитель"
    profile = _profile_from_row((row[1],))
    return str(profile.get("display_name") or row[0] or "Исполнитель")


def list_worker_verifications(user: dict[str, Any]) -> list[dict[str, Any]]:
    require_role(user, "logist")
    init_db()
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {VERIFICATION_SELECT_FIELDS}
                    FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                    WHERE status = 'pending'
                    ORDER BY submitted_at ASC
                    """
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT {VERIFICATION_SELECT_FIELDS}
                FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                WHERE status = 'pending'
                ORDER BY submitted_at ASC
                """
            ).fetchall()
    result = []
    for row in rows:
        item = _verification_from_row(row, include_sensitive=True)
        item["worker_name"] = _worker_display_name(item["worker_account_id"])
        result.append(item)
    return result


def review_worker_verification(
    user: dict[str, Any], submission_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    require_role(user, "logist")
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"verified", "rejected"}:
        raise HTTPException(status_code=422, detail="status must be verified or rejected")
    try:
        reason = bounded_text(
            payload.get("rejection_reason"), "rejection_reason", max_length=500
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if status == "rejected" and not reason:
        raise HTTPException(status_code=422, detail="rejection_reason is required")
    account_id = str(user.get("sub") or "")
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
                    SET status = %s, reviewed_at = NOW(), reviewer_account_id = %s,
                        rejection_reason = %s
                    WHERE submission_id = %s AND status = 'pending'
                    RETURNING {VERIFICATION_SELECT_FIELDS}
                    """,
                    (status, account_id, reason or None, submission_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=409, detail="submission is not pending")
                record_audit_event_in_connection(
                    connection,
                    event_type="worker_verification_reviewed",
                    outcome="success",
                    actor_account_id=account_id,
                    actor_username=str(user.get("username") or ""),
                    target_type="worker_verification",
                    target_id=submission_id,
                    details={"status": status, "verification_type": str(row[2])},
                )
            connection.commit()
        else:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                f"""
                SELECT {VERIFICATION_SELECT_FIELDS}
                FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                WHERE submission_id = ? AND status = 'pending'
                """,
                (submission_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(status_code=409, detail="submission is not pending")
            connection.execute(
                f"""
                UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
                SET status = ?, reviewed_at = CURRENT_TIMESTAMP,
                    reviewer_account_id = ?, rejection_reason = ?
                WHERE submission_id = ?
                """,
                (status, account_id, reason or None, submission_id),
            )
            record_audit_event_in_connection(
                connection,
                event_type="worker_verification_reviewed",
                outcome="success",
                actor_account_id=account_id,
                actor_username=str(user.get("username") or ""),
                target_type="worker_verification",
                target_id=submission_id,
                details={"status": status, "verification_type": str(existing[2])},
            )
            row = connection.execute(
                f"""
                SELECT {VERIFICATION_SELECT_FIELDS}
                FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                WHERE submission_id = ?
                """,
                (submission_id,),
            ).fetchone()
    return _verification_from_row(row, include_sensitive=True)


def worker_verification_attachment(
    user: dict[str, Any], submission_id: str
) -> tuple[Path, str, str]:
    require_role(user, "logist")
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT attachment_path, attachment_media_type, attachment_name
                    FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                    WHERE submission_id = %s
                    """,
                    (submission_id,),
                )
                row = cursor.fetchone()
        else:
            row = connection.execute(
                f"""
                SELECT attachment_path, attachment_media_type, attachment_name
                FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                WHERE submission_id = ?
                """,
                (submission_id,),
            ).fetchone()
    if row is None or not row[0]:
        raise HTTPException(status_code=404, detail="attachment not found")
    path = Path(str(row[0])).resolve()
    upload_dir = private_upload_dir().resolve()
    if not path.is_relative_to(upload_dir) or not path.is_file():
        raise HTTPException(status_code=404, detail="attachment not found")
    return path, str(row[1] or "application/octet-stream"), Path(str(row[2] or path.name)).name


def _invalidate_identity_verification_in_connection(
    connection: Any, worker_account_id: str
) -> None:
    reason = "Данные профиля изменены после отправки. Подайте паспорт повторно."
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
                SET status = 'rejected', reviewed_at = NOW(), rejection_reason = %s
                WHERE submission_id = (
                    SELECT submission_id FROM {WORKER_VERIFICATIONS_TABLE_NAME}
                    WHERE worker_account_id = %s AND verification_type = 'identity'
                      AND status IN ('pending', 'verified')
                    ORDER BY submitted_at DESC, submission_id DESC LIMIT 1
                )
                """,
                (reason, worker_account_id),
            )
        return
    connection.execute(
        f"""
        UPDATE {WORKER_VERIFICATIONS_TABLE_NAME}
        SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP,
            rejection_reason = ?
        WHERE submission_id = (
            SELECT submission_id FROM {WORKER_VERIFICATIONS_TABLE_NAME}
            WHERE worker_account_id = ? AND verification_type = 'identity'
              AND status IN ('pending', 'verified')
            ORDER BY submitted_at DESC, submission_id DESC LIMIT 1
        )
        """,
        (reason, worker_account_id),
    )


def get_account_profile(user: dict[str, Any]) -> dict[str, Any]:
    account_id = str(user.get("sub") or "")
    role = str(user.get("role") or "")
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT data FROM {PROFILES_TABLE_NAME} WHERE account_id = %s",
                    (account_id,),
                )
                profile = _profile_from_row(cursor.fetchone())
        else:
            profile = _profile_from_row(
                connection.execute(
                    f"SELECT data FROM {PROFILES_TABLE_NAME} WHERE account_id = ?",
                    (account_id,),
                ).fetchone()
            )
    result = {**default_profile(user), **profile}
    if role == "worker":
        latest = latest_worker_verifications(account_id)
        for verification_type, status_field in {
            "identity": "identity_status",
            "npd": "npd_status",
        }.items():
            verification = latest.get(verification_type)
            if verification is None:
                continue
            result[status_field] = verification["status"]
            result[f"{verification_type}_submitted_at"] = verification["submitted_at"]
            result[f"{verification_type}_rejection_reason"] = verification[
                "rejection_reason"
            ]
    result.update(
        {
            "username": str(user.get("username") or ""),
            "role": role,
            "profile_completion": _profile_completion(result, role),
        }
    )
    return result


def _clean_profile_value(field: str, value: Any) -> Any:
    if field in {"nationality", "notify_new_orders"}:
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be boolean")
        return value
    if field == "max_orders":
        return bounded_integer(value, field, minimum=1, maximum=500)
    if field == "cities":
        if not isinstance(value, list) or len(value) > 20:
            raise ValueError("cities must be a list")
        return [
            bounded_text(item, "city", max_length=120, required=True)
            for item in value
        ]
    if field == "tools":
        if not isinstance(value, dict):
            raise ValueError("tools must be an object")
        return {
            "straps": value.get("straps") is True,
            "tools": value.get("tools") is True,
        }
    text = bounded_text(value, field, max_length=500)
    if field == "email" and text and ("@" not in text or len(text) > 254):
        raise ValueError("email is invalid")
    if field == "documents_email" and text and "@" not in text:
        raise ValueError("documents_email is invalid")
    if field == "card_last4" and text and (len(text) != 4 or not text.isdigit()):
        raise ValueError("card_last4 is invalid")
    if field == "client_type" and text not in {"individual", "legal"}:
        raise ValueError("client_type is invalid")
    if field == "payment_type" and text not in {"card", "cash", "invoice"}:
        raise ValueError("payment_type is invalid")
    if field == "employment_type" and text not in {"contract", "state"}:
        raise ValueError("employment_type is invalid")
    if field == "payout_method" and text not in {"", "card", "account"}:
        raise ValueError("payout_method is invalid")
    if field == "department" and text not in {
        "operations",
        "key_accounts",
        "quality",
    }:
        raise ValueError("department is invalid")
    return text


def update_account_profile(
    user: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any]:
    role = str(user.get("role") or "")
    allowed = ROLE_PROFILE_FIELDS.get(role, set())
    unknown = set(patch) - allowed
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported profile fields: {', '.join(sorted(unknown))}",
        )
    if not patch:
        raise HTTPException(status_code=422, detail="empty profile patch")
    try:
        cleaned = {
            field: _clean_profile_value(field, value)
            for field, value in patch.items()
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    current = get_account_profile(user)
    invalidates_identity = role == "worker" and any(
        field in cleaned and cleaned[field] != current.get(field)
        for field in {"display_name", "date_birth", "nationality"}
    )
    stored_fields = ROLE_PROFILE_FIELDS.get(role, set())
    updated = {
        field: value
        for field, value in {**current, **cleaned}.items()
        if field in stored_fields
    }
    account_id = str(user.get("sub") or "")
    serialized = json.dumps(updated, ensure_ascii=False)
    with db_connection() as connection:
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {PROFILES_TABLE_NAME}(account_id, data, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT(account_id) DO UPDATE SET
                        data = excluded.data,
                        updated_at = NOW()
                    """,
                    (account_id, serialized),
                )
                if invalidates_identity:
                    _invalidate_identity_verification_in_connection(
                        connection, account_id
                    )
                record_audit_event_in_connection(
                    connection,
                    event_type="profile_updated",
                    outcome="success",
                    actor_account_id=account_id,
                    actor_username=str(user.get("username") or ""),
                    target_type="profile",
                    target_id=account_id,
                    details={"fields": sorted(cleaned)},
                )
            connection.commit()
        else:
            connection.execute(
                f"""
                INSERT INTO {PROFILES_TABLE_NAME}(account_id, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_id, serialized),
            )
            if invalidates_identity:
                _invalidate_identity_verification_in_connection(connection, account_id)
            record_audit_event_in_connection(
                connection,
                event_type="profile_updated",
                outcome="success",
                actor_account_id=account_id,
                actor_username=str(user.get("username") or ""),
                target_type="profile",
                target_id=account_id,
                details={"fields": sorted(cleaned)},
            )
    return get_account_profile(user)


def _worker_application(order: dict[str, Any], account_id: str) -> dict[str, Any] | None:
    return next(
        (
            dict(item)
            for item in order.get("applications") or []
            if isinstance(item, dict)
            and str(item.get("worker_id") or "") == account_id
        ),
        None,
    )


def apply_to_order_atomically(
    order_id: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    require_role(user, "worker")
    account_id = str(user.get("sub") or "")
    profile = get_account_profile(user)
    with db_connection() as connection:
        if _is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        order = read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        if str(order.get("status") or "") != "PROCESSED":
            raise HTTPException(status_code=409, detail="order is not accepting applications")
        if not worker_can_discover_order(order, profile):
            raise HTTPException(status_code=403, detail="order is outside worker cities")
        applications = [
            dict(item)
            for item in order.get("applications") or []
            if isinstance(item, dict)
        ]
        existing = _worker_application(order, account_id)
        if existing is None:
            existing = {
                "id": str(uuid4()),
                "order_id": str(order.get("id") or order_id),
                "worker_id": account_id,
                "worker_name": str(user.get("username") or "Исполнитель"),
                "status": "PENDING",
                "created_at": serialize_datetime(utc_now()),
            }
            applications.append(existing)
            order["applications"] = applications
            write_order_in_connection(connection, order)
            record_audit_event_in_connection(
                connection,
                event_type="order_application_created",
                outcome="success",
                actor_account_id=account_id,
                actor_username=str(user.get("username") or ""),
                target_type="order",
                target_id=str(order.get("id") or order_id),
            )
        if not _is_sqlite_connection(connection):
            connection.commit()
    return existing


def decide_order_application_atomically(
    order_id: str,
    application_id: str,
    decision: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    require_role(user, "logist", "client")
    role = str(user.get("role") or "")
    profile = get_account_profile(user) if role == "logist" else None
    normalized_decision = decision.strip().upper()
    if normalized_decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=422, detail="invalid application decision")
    with db_connection() as connection:
        if _is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        order = read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        if role == "logist":
            allowed = logist_owns_order(order, user, profile=profile)
        else:
            allowed = str(order.get("created_by") or "") == str(
                user.get("sub") or ""
            )
        if not allowed:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        applications = [
            dict(item)
            for item in order.get("applications") or []
            if isinstance(item, dict)
        ]
        application = next(
            (
                item
                for item in applications
                if str(item.get("id") or "") == application_id
            ),
            None,
        )
        if application is None:
            raise HTTPException(status_code=404, detail="application not found")
        assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
        worker_id = str(application.get("worker_id") or "")
        if normalized_decision == "APPROVED" and worker_id not in assigned:
            workers_count = int(order.get("workers_count") or 1)
            if len(assigned) >= workers_count:
                raise HTTPException(status_code=409, detail="all worker slots are filled")
            assigned.append(worker_id)
        application["status"] = normalized_decision
        application["decided_at"] = serialize_datetime(utc_now())
        application["decided_by"] = str(user.get("sub") or "")
        order["applications"] = applications
        order["assigned_worker_ids"] = assigned
        if normalized_decision == "APPROVED" and len(assigned) >= int(
            order.get("workers_count") or 1
        ):
            order["status"] = "IN_PROCESS"
        write_order_in_connection(connection, order)
        record_audit_event_in_connection(
            connection,
            event_type="order_application_decided",
            outcome="success",
            actor_account_id=str(user.get("sub") or ""),
            actor_username=str(user.get("username") or ""),
            target_type="application",
            target_id=application_id,
            details={"decision": normalized_decision},
        )
        if not _is_sqlite_connection(connection):
            connection.commit()
    return application


def _order_amount(order: dict[str, Any]) -> int:
    individual_price = order.get("individual_price")
    try:
        if individual_price not in (None, ""):
            return max(0, int(individual_price))
    except (TypeError, ValueError):
        pass
    try:
        rate = int(order.get("price_per_hour") or 0)
        hours = int(order.get("hours") or 0)
        return max(0, rate * hours)
    except (TypeError, ValueError):
        return 0


def account_finance(user: dict[str, Any]) -> dict[str, Any]:
    require_role(user, "worker")
    account_id = str(user.get("sub") or "")
    assigned_orders = [
        order
        for order in list_orders()
        if account_id in [str(item) for item in order.get("assigned_worker_ids") or []]
    ]
    transactions = []
    for order in assigned_orders:
        status = str(order.get("status") or "")
        if status not in {"DONE_PENDING", "CONVERTED"}:
            continue
        amount = _order_amount(order)
        transactions.append(
            {
                "id": f"accrual-{order.get('id') or order.get('external_order_id')}",
                "order_id": str(order.get("id") or ""),
                "title": str(order.get("title") or "Выполненный заказ"),
                "amount": amount,
                "status": "available" if status == "CONVERTED" else "pending",
                "date": str(order.get("updated_at") or order.get("scheduled_at") or ""),
            }
        )
    available = sum(
        item["amount"] for item in transactions if item["status"] == "available"
    )
    pending = sum(
        item["amount"] for item in transactions if item["status"] == "pending"
    )
    return {
        "currency": "RUB",
        "available": available,
        "pending": pending,
        "total_accrued": available,
        "transactions": transactions,
        "payout": {
            "method": get_account_profile(user).get("payout_method") or "",
            "configured": bool(get_account_profile(user).get("payout_method")),
        },
    }


def account_dashboard(user: dict[str, Any]) -> dict[str, Any]:
    role = str(user.get("role") or "")
    account_id = str(user.get("sub") or "")
    all_orders = list_orders()
    profile = get_account_profile(user)
    visible_orders = orders_for_user(all_orders, user, profile=profile)
    summary: dict[str, Any]
    if role == "worker":
        applications = [
            _worker_application(order, account_id)
            for order in all_orders
        ]
        applications = [item for item in applications if item is not None]
        assigned = [
            order
            for order in all_orders
            if account_id in [str(item) for item in order.get("assigned_worker_ids") or []]
        ]
        finance = account_finance(user)
        summary = {
            "available_orders": sum(
                str(order.get("status") or "") == "PROCESSED"
                and _worker_application(order, account_id) is None
                for order in visible_orders
            ),
            "pending_applications": sum(
                str(item.get("status") or "") == "PENDING" for item in applications
            ),
            "active_orders": sum(
                str(order.get("status") or "")
                in {"PROCESSED", "IN_PROCESS", "DONE_PENDING"}
                for order in assigned
            ),
            "completed_orders": sum(
                str(order.get("status") or "") == "CONVERTED" for order in assigned
            ),
            "available_balance": finance["available"],
        }
    elif role == "client":
        summary = {
            "total_orders": len(visible_orders),
            "active_orders": sum(
                str(order.get("status") or "")
                in {"NEW", "PROCESSED", "IN_PROCESS", "DONE_PENDING"}
                for order in visible_orders
            ),
            "completed_orders": sum(
                str(order.get("status") or "") == "CONVERTED"
                for order in visible_orders
            ),
        }
    else:
        summary = {
            "total_orders": len(visible_orders),
            "new_orders": sum(
                str(order.get("status") or "") == "NEW" for order in visible_orders
            ),
            "active_orders": sum(
                str(order.get("status") or "") in {"PROCESSED", "IN_PROCESS"}
                for order in visible_orders
            ),
            "pending_applications": sum(
                str(item.get("status") or "") == "PENDING"
                for order in visible_orders
                for item in order.get("applications") or []
                if isinstance(item, dict)
            ),
        }
    next_orders = sorted(
        [
            order
            for order in visible_orders
            if str(order.get("status") or "")
            not in {"CONVERTED", "JUNK"}
        ],
        key=lambda order: str(order.get("scheduled_at") or "9999"),
    )
    return {
        "role": role,
        "username": str(user.get("username") or ""),
        "profile": profile,
        "summary": summary,
        "next_order": next_orders[0] if next_orders else None,
    }


def _chat_thread_id(order_id: str, thread_type: str) -> str:
    return f"chat-{order_id}-{thread_type}"


def _ensure_chat_thread_in_connection(
    connection: Any,
    order: dict[str, Any],
    thread_type: str,
) -> str:
    order_id = str(order.get("id") or order.get("external_order_id") or "")
    thread_id = _chat_thread_id(order_id, thread_type)
    archived = str(order.get("status") or "") in {"CONVERTED", "JUNK"}
    created = False
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {CHAT_THREADS_TABLE_NAME}(
                    thread_id, order_id, thread_type, is_archived, requires_attention
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(order_id, thread_type) DO UPDATE SET
                    is_archived = excluded.is_archived
                RETURNING (xmax = 0)
                """,
                (
                    thread_id,
                    order_id,
                    thread_type,
                    archived,
                    thread_type == "clientLogist",
                ),
            )
            created = bool(cursor.fetchone()[0])
    else:
        cursor = connection.execute(
            f"""
            INSERT OR IGNORE INTO {CHAT_THREADS_TABLE_NAME}(
                thread_id, order_id, thread_type, is_archived, requires_attention
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                order_id,
                thread_type,
                1 if archived else 0,
                1 if thread_type == "clientLogist" else 0,
            ),
        )
        created = cursor.rowcount > 0
        connection.execute(
            f"UPDATE {CHAT_THREADS_TABLE_NAME} SET is_archived = ? WHERE thread_id = ?",
            (1 if archived else 0, thread_id),
        )
    if created:
        message_id = str(uuid4())
        message = "Чат создан для рабочих вопросов по заказу."
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {CHAT_MESSAGES_TABLE_NAME}(
                        message_id, thread_id, sender_role, sender_name,
                        message_text, is_system
                    ) VALUES (%s, %s, 'system', 'GPM', %s, TRUE)
                    """,
                    (message_id, thread_id, message),
                )
        else:
            connection.execute(
                f"""
                INSERT INTO {CHAT_MESSAGES_TABLE_NAME}(
                    message_id, thread_id, sender_role, sender_name,
                    message_text, is_system
                ) VALUES (?, ?, 'system', 'GPM', ?, 1)
                """,
                (message_id, thread_id, message),
            )
    return thread_id


def _ensure_order_chat_threads(connection: Any, orders: list[dict[str, Any]]) -> None:
    for order in orders:
        order_id = str(order.get("id") or order.get("external_order_id") or "")
        if not order_id:
            continue
        if order.get("created_by") and (
            order.get("logist_account_id") or order.get("logist_phone")
        ):
            _ensure_chat_thread_in_connection(connection, order, "clientLogist")
        assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
        if assigned:
            _ensure_chat_thread_in_connection(connection, order, "workerLogist")
            _ensure_chat_thread_in_connection(connection, order, "clientWorker")


def _read_chat_thread_in_connection(connection: Any, thread_id: str) -> Any:
    query = f"""
        SELECT thread_id, order_id, thread_type, is_archived,
               requires_attention, created_at, updated_at
        FROM {CHAT_THREADS_TABLE_NAME}
        WHERE thread_id = {{placeholder}}
    """
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(query.format(placeholder="%s"), (thread_id,))
            return cursor.fetchone()
    return connection.execute(query.format(placeholder="?"), (thread_id,)).fetchone()


def _chat_thread_access(
    connection: Any,
    row: Any,
    user: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    if row is None:
        return False, None
    order = read_order_in_connection(connection, str(row[1]))
    if order is None:
        return False, None
    role = str(user.get("role") or "")
    account_id = str(user.get("sub") or "")
    thread_type = str(row[2])
    if role == "logist":
        return logist_owns_order(order, user, profile=profile), order
    if role == "client":
        return (
            order.get("created_by") == account_id
            and thread_type in {"clientLogist", "clientWorker", "support"},
            order,
        )
    if role == "worker":
        assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
        return (
            account_id in assigned
            and thread_type in {"workerLogist", "clientWorker", "support"},
            order,
        )
    return False, order


def _chat_thread_title(thread_type: str, order: dict[str, Any]) -> str:
    title = str(order.get("title") or f"Заказ #{order.get('id') or ''}")
    return {
        "clientLogist": title,
        "workerLogist": f"Координация: {title}",
        "clientWorker": f"Рабочий чат: {title}",
        "support": f"Поддержка: {title}",
    }.get(thread_type, title)


def _messages_for_thread_in_connection(connection: Any, thread_id: str) -> list[Any]:
    query = f"""
        SELECT message_id, thread_id, sender_account_id, sender_role,
               sender_name, message_text, created_at, is_system
        FROM {CHAT_MESSAGES_TABLE_NAME}
        WHERE thread_id = {{placeholder}}
        ORDER BY created_at ASC
    """
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(query.format(placeholder="%s"), (thread_id,))
            return list(cursor.fetchall())
    return list(connection.execute(query.format(placeholder="?"), (thread_id,)).fetchall())


def _chat_read_at(connection: Any, thread_id: str, account_id: str) -> datetime | None:
    if not _is_sqlite_connection(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT read_at FROM {CHAT_READS_TABLE_NAME} WHERE thread_id = %s AND account_id = %s",
                (thread_id, account_id),
            )
            row = cursor.fetchone()
    else:
        row = connection.execute(
            f"SELECT read_at FROM {CHAT_READS_TABLE_NAME} WHERE thread_id = ? AND account_id = ?",
            (thread_id, account_id),
        ).fetchone()
    return parse_db_datetime(row[0]) if row else None


def _serialize_chat_message(row: Any) -> dict[str, Any]:
    created_at = parse_db_datetime(row[6]) or utc_now()
    return {
        "id": str(row[0]),
        "thread_id": str(row[1]),
        "sender_role": str(row[3]),
        "sender_name": str(row[4]),
        "text": str(row[5]),
        "created_at": serialize_datetime(created_at),
        "is_system": bool(row[7]),
    }


def list_account_chat_threads(user: dict[str, Any]) -> list[dict[str, Any]]:
    orders = list_orders()
    account_id = str(user.get("sub") or "")
    profile = (
        get_account_profile(user)
        if str(user.get("role") or "") == "logist"
        else None
    )
    result: list[dict[str, Any]] = []
    with db_connection() as connection:
        _ensure_order_chat_threads(connection, orders)
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT thread_id, order_id, thread_type, is_archived,
                           requires_attention, created_at, updated_at
                    FROM {CHAT_THREADS_TABLE_NAME}
                    ORDER BY updated_at DESC
                    """
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT thread_id, order_id, thread_type, is_archived,
                       requires_attention, created_at, updated_at
                FROM {CHAT_THREADS_TABLE_NAME}
                ORDER BY updated_at DESC
                """
            ).fetchall()
        for row in rows:
            allowed, order = _chat_thread_access(
                connection, row, user, profile=profile
            )
            if not allowed or order is None:
                continue
            messages = _messages_for_thread_in_connection(connection, str(row[0]))
            last_message = messages[-1] if messages else None
            read_at = _chat_read_at(connection, str(row[0]), account_id)
            unread = sum(
                (parse_db_datetime(message[6]) or utc_now()) > (read_at or datetime.min.replace(tzinfo=timezone.utc))
                and str(message[2] or "") != account_id
                for message in messages
            )
            updated_at = (
                parse_db_datetime(last_message[6])
                if last_message is not None
                else parse_db_datetime(row[6])
            ) or utc_now()
            result.append(
                {
                    "id": str(row[0]),
                    "order_id": str(row[1]),
                    "type": str(row[2]),
                    "title": _chat_thread_title(str(row[2]), order),
                    "subtitle": (
                        str(last_message[5])
                        if last_message is not None
                        else str(order.get("city") or "")
                    ),
                    "is_archived": bool(row[3]),
                    "requires_logist_attention": bool(row[4]),
                    "unread_count": unread,
                    "updated_at": serialize_datetime(updated_at),
                }
            )
        if not _is_sqlite_connection(connection):
            connection.commit()
    result.sort(
        key=lambda thread: str(thread.get("updated_at") or ""),
        reverse=True,
    )
    return result


def get_account_chat_messages(
    thread_id: str,
    user: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profile = (
        get_account_profile(user)
        if str(user.get("role") or "") == "logist"
        else None
    )
    with db_connection() as connection:
        row = _read_chat_thread_in_connection(connection, thread_id)
        allowed, order = _chat_thread_access(
            connection, row, user, profile=profile
        )
        if not allowed or row is None or order is None:
            raise HTTPException(status_code=404, detail="chat thread not found")
        messages = [
            _serialize_chat_message(item)
            for item in _messages_for_thread_in_connection(connection, thread_id)
        ]
        account_id = str(user.get("sub") or "")
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {CHAT_READS_TABLE_NAME}(thread_id, account_id, read_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT(thread_id, account_id) DO UPDATE SET read_at = NOW()
                    """,
                    (thread_id, account_id),
                )
            connection.commit()
        else:
            connection.execute(
                f"""
                INSERT INTO {CHAT_READS_TABLE_NAME}(thread_id, account_id, read_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(thread_id, account_id) DO UPDATE SET read_at = CURRENT_TIMESTAMP
                """,
                (thread_id, account_id),
            )
    thread = next(
        (
            item
            for item in list_account_chat_threads(user)
            if item["id"] == thread_id
        ),
        None,
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="chat thread not found")
    return thread, messages


def send_account_chat_message(
    thread_id: str,
    text: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    clean_text = bounded_text(text, "message", max_length=2000, required=True)
    profile = get_account_profile(user)
    with db_connection() as connection:
        row = _read_chat_thread_in_connection(connection, thread_id)
        allowed, _ = _chat_thread_access(
            connection, row, user, profile=profile
        )
        if not allowed or row is None:
            raise HTTPException(status_code=404, detail="chat thread not found")
        if bool(row[3]):
            raise HTTPException(status_code=409, detail="chat thread is archived")
        message_id = str(uuid4())
        account_id = str(user.get("sub") or "")
        role = str(user.get("role") or "")
        sender_name = str(
            profile.get("display_name")
            or user.get("username")
            or "Пользователь"
        )
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {CHAT_MESSAGES_TABLE_NAME}(
                        message_id, thread_id, sender_account_id, sender_role,
                        sender_name, message_text
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (message_id, thread_id, account_id, role, sender_name, clean_text),
                )
                cursor.execute(
                    f"""
                    UPDATE {CHAT_THREADS_TABLE_NAME}
                    SET updated_at = NOW(),
                        requires_attention = CASE
                            WHEN %s <> 'logist' THEN TRUE
                            ELSE requires_attention
                        END
                    WHERE thread_id = %s
                    """,
                    (role, thread_id),
                )
            connection.commit()
        else:
            connection.execute(
                f"""
                INSERT INTO {CHAT_MESSAGES_TABLE_NAME}(
                    message_id, thread_id, sender_account_id, sender_role,
                    sender_name, message_text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, thread_id, account_id, role, sender_name, clean_text),
            )
            connection.execute(
                f"""
                UPDATE {CHAT_THREADS_TABLE_NAME}
                SET updated_at = CURRENT_TIMESTAMP,
                    requires_attention = CASE
                        WHEN ? <> 'logist' THEN 1
                        ELSE requires_attention
                    END
                WHERE thread_id = ?
                """,
                (role, thread_id),
            )
        record_audit_event_in_connection(
            connection,
            event_type="chat_message_sent",
            outcome="success",
            actor_account_id=account_id,
            actor_username=str(user.get("username") or ""),
            target_type="chat_thread",
            target_id=thread_id,
        )
        if not _is_sqlite_connection(connection):
            connection.commit()
    _, messages = get_account_chat_messages(thread_id, user)
    return messages[-1]


def set_chat_attention(
    thread_id: str,
    user: dict[str, Any],
    *,
    requires_attention: bool,
) -> None:
    profile = (
        get_account_profile(user)
        if str(user.get("role") or "") == "logist"
        else None
    )
    with db_connection() as connection:
        row = _read_chat_thread_in_connection(connection, thread_id)
        allowed, _ = _chat_thread_access(
            connection, row, user, profile=profile
        )
        if not allowed or row is None:
            raise HTTPException(status_code=404, detail="chat thread not found")
        role = str(user.get("role") or "")
        if not requires_attention and role != "logist":
            raise HTTPException(status_code=403, detail="insufficient permissions")
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {CHAT_THREADS_TABLE_NAME} SET requires_attention = %s, updated_at = NOW() WHERE thread_id = %s",
                    (requires_attention, thread_id),
                )
            connection.commit()
        else:
            connection.execute(
                f"UPDATE {CHAT_THREADS_TABLE_NAME} SET requires_attention = ?, updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?",
                (1 if requires_attention else 0, thread_id),
            )


def request_chat_support(thread_id: str, user: dict[str, Any]) -> str:
    profile = (
        get_account_profile(user)
        if str(user.get("role") or "") == "logist"
        else None
    )
    with db_connection() as connection:
        row = _read_chat_thread_in_connection(connection, thread_id)
        allowed, order = _chat_thread_access(
            connection, row, user, profile=profile
        )
        if not allowed or row is None or order is None:
            raise HTTPException(status_code=404, detail="chat thread not found")
        if str(user.get("role") or "") == "logist":
            raise HTTPException(status_code=422, detail="logist support is already present")
        support_id = _ensure_chat_thread_in_connection(connection, order, "support")
        if not _is_sqlite_connection(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {CHAT_THREADS_TABLE_NAME} SET requires_attention = TRUE, updated_at = NOW() WHERE thread_id IN (%s, %s)",
                    (thread_id, support_id),
                )
            connection.commit()
        else:
            connection.execute(
                f"UPDATE {CHAT_THREADS_TABLE_NAME} SET requires_attention = 1, updated_at = CURRENT_TIMESTAMP WHERE thread_id IN (?, ?)",
                (thread_id, support_id),
            )
    return support_id


@app.on_event("startup")
async def startup() -> None:
    validate_runtime_configuration()
    await asyncio.to_thread(init_db)
    if is_production_environment() and not await asyncio.to_thread(
        database_has_active_accounts
    ):
        raise RuntimeError("at least one active DB-backed app account is required")


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        storage = await asyncio.to_thread(check_database_health)
    except Exception as error:
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return {
        "status": "ok",
        "storage": storage,
    }


@app.post("/app-api/auth/register")
async def register_with_invitation(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    invitation = str(payload.get("invitation") or "").strip()
    password = str(payload.get("password") or "")
    password_confirmation = str(payload.get("password_confirmation") or "")
    expected_role = str(payload.get("role") or "").strip().lower() or None
    if not invitation or not password:
        raise HTTPException(status_code=400, detail="invitation and password are required")
    if (
        len(invitation) > 200
        or len(password) > MAX_PASSWORD_LENGTH
        or len(password_confirmation) > MAX_PASSWORD_LENGTH
    ):
        raise HTTPException(status_code=400, detail="invalid registration payload")
    if password != password_confirmation:
        raise HTTPException(status_code=400, detail="passwords do not match")
    audit_details = {
        "remote_ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:256],
    }
    account = await asyncio.to_thread(
        redeem_account_invitation,
        invitation,
        password,
        expected_role=expected_role,
        audit_details=audit_details,
    )
    return {
        "success": True,
        "username": account["username"],
        "role": account["role"],
    }


@app.post("/app-api/auth/login")
async def login(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="login and password are required")
    audit_details = {
        "remote_ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:256],
    }
    account = await asyncio.to_thread(
        check_app_credentials,
        username,
        password,
        audit_details=audit_details,
    )
    role = account["role"]

    return {
        "access_token": account["access_token"],
        "token_type": "bearer",
        "role": role,
        "username": account["username"],
    }


@app.post("/app-api/auth/logout")
async def logout(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    user = await authenticated_user(authorization)
    audit_details = {
        "remote_ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:256],
    }
    await asyncio.to_thread(revoke_session, user, audit_details=audit_details)
    return {"success": True}


@app.get("/app-api/me")
async def me(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return {
        "username": str(user.get("username") or ""),
        "role": str(user.get("role") or ""),
    }


@app.get("/app-api/me/profile")
async def my_profile(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return {"profile": await asyncio.to_thread(get_account_profile, user)}


@app.patch("/app-api/me/profile")
async def patch_my_profile(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    try:
        patch = await request.json()
        if not isinstance(patch, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    profile = await asyncio.to_thread(update_account_profile, user, patch)
    return {"success": True, "profile": profile}


async def bounded_json_payload(request: Request, *, max_bytes: int) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="request is too large")
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid content-length") from error
    body = await request.body()
    if len(body) > max_bytes:
        raise HTTPException(status_code=413, detail="request is too large")
    try:
        payload = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="invalid JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    return payload


@app.get("/app-api/me/verifications")
async def get_my_verifications(
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    user = await authenticated_user(authorization)
    submissions = await asyncio.to_thread(my_worker_verifications, user)
    return {"submissions": submissions}


@app.post("/app-api/me/verifications/{verification_type}")
async def post_my_verification(
    verification_type: str,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    user = await authenticated_user(authorization)
    payload = await bounded_json_payload(
        request, max_bytes=MAX_VERIFICATION_REQUEST_BYTES
    )
    submission = await asyncio.to_thread(
        submit_worker_verification, user, verification_type, payload
    )
    return {"success": True, "submission": submission}


@app.get("/app-api/logist/worker-verifications")
async def get_worker_verification_queue(
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    user = await authenticated_user(authorization)
    submissions = await asyncio.to_thread(list_worker_verifications, user)
    return {"submissions": submissions}


@app.patch("/app-api/logist/worker-verifications/{submission_id}")
async def patch_worker_verification(
    submission_id: str,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    user = await authenticated_user(authorization)
    payload = await bounded_json_payload(request, max_bytes=4096)
    submission = await asyncio.to_thread(
        review_worker_verification, user, submission_id, payload
    )
    return {"success": True, "submission": submission}


@app.get("/app-api/logist/worker-verifications/{submission_id}/attachment")
async def get_worker_verification_attachment(
    submission_id: str,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    user = await authenticated_user(authorization)
    path, media_type, filename = await asyncio.to_thread(
        worker_verification_attachment, user, submission_id
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/app-api/me/dashboard")
async def my_dashboard(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return await asyncio.to_thread(account_dashboard, user)


@app.get("/app-api/me/finance")
async def my_finance(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return await asyncio.to_thread(account_finance, user)


@app.get("/app-api/me/chats")
async def my_chat_threads(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return {"threads": await asyncio.to_thread(list_account_chat_threads, user)}


@app.get("/app-api/me/chats/{thread_id}")
async def my_chat_messages(
    thread_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    thread, messages = await asyncio.to_thread(
        get_account_chat_messages,
        thread_id,
        user,
    )
    return {"thread": thread, "messages": messages}


@app.post("/app-api/me/chats/{thread_id}/messages")
async def post_my_chat_message(
    thread_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    message = await asyncio.to_thread(
        send_account_chat_message,
        thread_id,
        str(payload.get("text") or ""),
        user,
    )
    return {"success": True, "message": message}


@app.post("/app-api/me/chats/{thread_id}/support")
async def request_my_chat_support(
    thread_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    support_thread_id = await asyncio.to_thread(request_chat_support, thread_id, user)
    return {"success": True, "support_thread_id": support_thread_id}


@app.patch("/app-api/me/chats/{thread_id}/attention")
async def patch_my_chat_attention(
    thread_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    user = await authenticated_user(authorization)
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or not isinstance(
            payload.get("requires_attention"), bool
        ):
            raise ValueError("requires_attention must be boolean")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    await asyncio.to_thread(
        set_chat_attention,
        thread_id,
        user,
        requires_attention=payload["requires_attention"],
    )
    return {"success": True}


@app.post("/app-api/me/address-suggestions")
async def address_suggestions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    await authenticated_user(authorization)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    query = str(payload.get("query") or "").strip()
    city = str(payload.get("city") or "").strip()
    if len(query) < 3:
        return {"suggestions": []}
    if len(query) > 300 or len(city) > 120:
        raise HTTPException(status_code=400, detail="address query is too long")

    suggestions = await asyncio.to_thread(fetch_address_suggestions, query, city)
    return {"suggestions": suggestions}


@app.get("/app-api/me/orders")
async def get_my_orders(
    authorization: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    user = await authenticated_user(authorization)
    orders = await asyncio.to_thread(list_orders)
    profile = None
    if user.get("role") in {"logist", "worker"}:
        profile = await asyncio.to_thread(get_account_profile, user)
    return {"orders": orders_for_user(orders, user, profile=profile)}


@app.post("/app-api/me/orders/{order_id}/applications")
async def create_my_order_application(
    order_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    application = await asyncio.to_thread(apply_to_order_atomically, order_id, user)
    return {"success": True, "application": application}


@app.patch("/app-api/me/orders/{order_id}/applications/{application_id}")
async def decide_my_order_application(
    order_id: str,
    application_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        decision = str(payload.get("decision") or "")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    application = await asyncio.to_thread(
        decide_order_application_atomically,
        order_id,
        application_id,
        decision,
        user,
    )
    return {"success": True, "application": application}


@app.post("/app-api/me/orders")
async def publish_my_order(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    require_role(user, "client", "logist")
    return await publish_order_payload(request, actor=user)


@app.post("/app-api/orders")
async def publish_order(
    request: Request,
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(x_gpm_app_token)
    return await publish_order_payload(request, integration=True)


async def publish_order_payload(
    request: Request,
    *,
    actor: dict[str, Any] | None = None,
    integration: bool = False,
) -> dict[str, Any]:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        payload = dict(payload)
        if actor is not None:
            payload["source"] = "manual"
            payload["source_system"] = "gpm-app"
        elif integration:
            payload.setdefault("source", "external")
        order = normalize_external_order(
            payload,
            created_by=str(actor.get("sub") or "") if actor else None,
            created_by_role=str(actor.get("role") or "") if actor else None,
        )
        if integration:
            order["logist_account_id"] = await asyncio.to_thread(
                resolve_active_logist_account_id,
                order.get("logist_phone"),
            )
        elif actor is not None and str(actor.get("role") or "") == "logist":
            order["logist_account_id"] = str(actor.get("sub") or "")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    order = await asyncio.to_thread(
        persist_published_order,
        order,
        actor=actor,
    )

    response_order = order_for_user(order, actor) if actor else order
    return {
        "success": True,
        "order_number": order["external_order_id"],
        "order": response_order,
    }


@app.get("/app-api/orders")
async def get_orders(
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    check_token(x_gpm_app_token)
    return {"orders": await asyncio.to_thread(list_orders)}


@app.patch("/app-api/orders/{order_id}")
async def update_order(
    order_id: str,
    request: Request,
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(x_gpm_app_token)
    return await update_order_payload(order_id, request, integration=True)


@app.patch("/app-api/me/orders/{order_id}")
async def update_my_order(
    order_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = await authenticated_user(authorization)
    return await update_order_payload(order_id, request, actor=user)


async def update_order_payload(
    order_id: str,
    request: Request,
    *,
    actor: dict[str, Any] | None = None,
    integration: bool = False,
) -> dict[str, Any]:
    try:
        patch = await request.json()
        if not isinstance(patch, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    order = await asyncio.to_thread(
        patch_order_atomically,
        order_id,
        patch,
        actor=actor,
        integration=integration,
    )
    return {
        "success": True,
        "order": order_for_user(order, actor) if actor else order,
    }
