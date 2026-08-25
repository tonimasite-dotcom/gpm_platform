import asyncio
import json
import os
import base64
import hashlib
import hmac
import time
from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest, urlopen

import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yml"
LOCAL_CONFIG_FILE = BASE_DIR / "config.local.yml"
DEFAULT_SQLITE_DB_FILE = BASE_DIR / "gpm_app_orders.sqlite3"
LEGACY_SQLITE_DB_FILE = BASE_DIR / "crm_app_orders.sqlite3"
TABLE_NAME = "gpm_app_orders"
LEGACY_TABLE_NAME = "crm_app_orders"
APP_ROLES = {"client", "worker", "logist"}
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

    accounts = configured_app_accounts(strict=True)
    if not accounts:
        raise RuntimeError("at least one server-assigned app account is required")
    for account in accounts:
        if len(account["password"]) < 12:
            raise RuntimeError("production app account passwords need at least 12 characters")


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
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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


def create_access_token(username: str, role: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + 60 * 60 * 12,
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
    if payload.get("role") not in APP_ROLES:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return payload


def configured_app_accounts(*, strict: bool = False) -> list[dict[str, str]]:
    accounts: list[dict[str, str]] = []
    seen_usernames: set[str] = set()

    for role in sorted(APP_ROLES):
        prefix = f"GPM_APP_{role.upper()}"
        username = (get_setting(f"{prefix}_USERNAME") or "").strip()
        password = get_setting(f"{prefix}_PASSWORD") or ""
        if not username and not password:
            continue
        if not username or not password:
            raise RuntimeError(f"{prefix}_USERNAME and {prefix}_PASSWORD must be set together")
        if is_placeholder(username) or is_placeholder(password):
            if strict:
                raise RuntimeError(f"{prefix} uses an unsafe placeholder credential")
            continue
        if username in seen_usernames:
            raise RuntimeError("app account usernames must be unique")
        seen_usernames.add(username)
        accounts.append({"username": username, "password": password, "role": role})

    legacy_username = (get_setting("GPM_APP_USERNAME") or "").strip()
    legacy_password = get_setting("GPM_APP_PASSWORD") or ""
    legacy_role = (get_setting("GPM_APP_ROLE") or "").strip().lower()
    if legacy_username or legacy_password or legacy_role:
        if legacy_role not in APP_ROLES:
            raise RuntimeError("GPM_APP_ROLE must define the server-assigned account role")
        if not is_placeholder(legacy_username) and not is_placeholder(legacy_password):
            if not legacy_username or not legacy_password:
                raise RuntimeError("GPM_APP_USERNAME and GPM_APP_PASSWORD must be set together")
            if legacy_username in seen_usernames:
                raise RuntimeError("app account usernames must be unique")
            accounts.append(
                {
                    "username": legacy_username,
                    "password": legacy_password,
                    "role": legacy_role,
                }
            )

    return accounts


def check_app_credentials(username: str, password: str) -> dict[str, str]:
    try:
        accounts = configured_app_accounts()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="app login is not configured") from error
    if not accounts:
        raise HTTPException(status_code=503, detail="app login is not configured")

    matched_account = next(
        (
            account
            for account in accounts
            if secure_compare(username, account["username"])
        ),
        None,
    )
    expected_password = matched_account["password"] if matched_account else "!" * 32
    password_matches = secure_compare(password, expected_password)
    if matched_account is None or not password_matches:
        raise HTTPException(status_code=401, detail="invalid login or password")
    return matched_account


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
        "logist_phone": str(payload.get("logist_phone") or ""),
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
    if role == "worker":
        for field in (
            "client_email",
            "client_phone",
            "telegram_username",
            "logist_phone",
            "created_by",
            "created_by_role",
        ):
            visible.pop(field, None)
        assigned = [str(item) for item in order.get("assigned_worker_ids") or []]
        if str(user.get("sub") or "") not in assigned:
            for field in (
                "address",
                "address_street",
                "address_number",
                "address_lat",
                "address_lon",
            ):
                visible.pop(field, None)
    return visible


def orders_for_user(
    orders: list[dict[str, Any]],
    user: dict[str, Any],
) -> list[dict[str, Any]]:
    role = str(user.get("role") or "")
    username = str(user.get("sub") or "")
    if role == "client":
        orders = [order for order in orders if order.get("created_by") == username]
    elif role == "worker":
        orders = [
            order
            for order in orders
            if str(order.get("status") or "") == "PROCESSED"
            or (
                str(user.get("sub") or "")
                in [str(item) for item in order.get("assigned_worker_ids") or []]
                and str(order.get("status") or "")
                in {"IN_PROCESS", "DONE_PENDING", "CONVERTED"}
            )
        ]
    return [order_for_user(order, user) for order in orders]


def require_role(user: dict[str, Any], *allowed_roles: str) -> None:
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")


def validate_order_patch(
    order: dict[str, Any],
    patch: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    integration: bool,
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
            pass
        elif role == "client":
            if (
                order.get("created_by") != username
                or str(order.get("status") or "").upper() != "NEW"
                or target_status != "JUNK"
            ):
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
            integration=integration,
        )
        if not normalized_patch:
            raise HTTPException(status_code=422, detail="empty order patch")
        order.update(normalized_patch)
        write_order_in_connection(connection, order)
        if is_postgres_enabled():
            connection.commit()
    return order


@app.on_event("startup")
async def startup() -> None:
    validate_runtime_configuration()
    await asyncio.to_thread(init_db)


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
    account = check_app_credentials(username, password)
    role = account["role"]

    return {
        "access_token": create_access_token(username, role),
        "token_type": "bearer",
        "role": role,
        "username": username,
    }


@app.get("/app-api/me")
async def me(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = current_user(authorization)
    return {
        "username": str(user.get("sub") or ""),
        "role": str(user.get("role") or ""),
    }


@app.post("/app-api/me/address-suggestions")
async def address_suggestions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    current_user(authorization)
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
    user = current_user(authorization)
    orders = await asyncio.to_thread(list_orders)
    return {"orders": orders_for_user(orders, user)}


@app.post("/app-api/me/orders")
async def publish_my_order(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = current_user(authorization)
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
    user = current_user(authorization)
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
