import json
import os
import base64
import hashlib
import hmac
import time
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Any

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
    raw = get_setting("GPM_APP_ALLOWED_ORIGINS", "*") or "*"
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


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
    with sqlite3.connect(db_file) as connection:
        yield connection


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
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid app token")


def secure_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def jwt_secret() -> str:
    secret = get_setting("GPM_APP_JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="app auth is not configured")
    return secret


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
        payload = json.loads(b64url_decode(payload_part))
    except (json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="invalid bearer token") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    if int(payload.get("exp", 0)) < int(time.time()):
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


def check_app_credentials(username: str, password: str) -> None:
    expected_username = (
        os.getenv("GPM_APP_USERNAME")
        or get_setting("GPM_APP_LOGIST_USERNAME", "logist")
        or "logist"
    )
    expected_password = os.getenv("GPM_APP_PASSWORD") or get_setting(
        "GPM_APP_LOGIST_PASSWORD"
    )
    if not expected_password:
        raise HTTPException(status_code=503, detail="app login is not configured")
    if not secure_compare(username, expected_username):
        raise HTTPException(status_code=401, detail="invalid login or password")
    if not secure_compare(password, expected_password):
        raise HTTPException(status_code=401, detail="invalid login or password")


def save_order(order: dict[str, Any]) -> None:
    init_db()
    if is_postgres_enabled():
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {TABLE_NAME}(order_id, data, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT(order_id) DO UPDATE SET
                        data = excluded.data,
                        updated_at = NOW()
                    """,
                    (order["external_order_id"], json.dumps(order, ensure_ascii=False)),
                )
            connection.commit()
        return

    with db_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO {TABLE_NAME}(order_id, data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(order_id) DO UPDATE SET
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
            """,
            (order["external_order_id"], json.dumps(order, ensure_ascii=False)),
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
    if is_postgres_enabled():
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT data FROM {TABLE_NAME}
                    WHERE order_id = %s OR data->>'id' = %s
                    LIMIT 1
                    """,
                    (order_id, order_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    with db_connection() as connection:
        row = connection.execute(
            f"SELECT data FROM {TABLE_NAME} WHERE order_id = ? LIMIT 1",
            (order_id,),
        ).fetchone()
    return None if row is None else json.loads(row[0])


def normalize_external_order(payload: dict[str, Any]) -> dict[str, Any]:
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

    order_number = str(order_data.get("order_number") or "").strip()
    if not order_number:
        raise ValueError("order_data.order_number is required")

    additional = info.get("additional", "")
    if isinstance(additional, (list, dict)):
        additional = json.dumps(additional, ensure_ascii=False)
    additional = str(additional).replace("\\xa0", " ")

    rf_only = "Только РФ" in additional or "RF only" in additional
    address = info.get("address") or info.get("address_street") or "Адрес не указан"

    return {
        "id": order_number,
        "title": f"Заявка № {order_number}",
        "address": address,
        "workers_count": loaders.get("loader_count", 0),
        "hours": order_data.get("hours") or order_data.get("min_time", 4),
        "description": (order_data.get("note", "") or "")[:800],
        "client_email": payload.get("client_email", ""),
        "client_phone": payload.get("client_phone", ""),
        "scheduled_at": completion_date.get("date"),
        "city": payload.get("city") or order_data.get("city") or "",
        "source": "external",
        "source_system": str(payload.get("source_system") or "workstaff"),
        "external_order_id": order_number,
        "metro": info.get("metro_station"),
        "national": "yes" if rf_only else "every",
        "min_time": order_data.get("min_time", 4),
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
        "source_payload": payload,
        "status": "NEW",
        "created_at": completion_date.get("date"),
        "assigned_worker_ids": [],
        "applications": [],
    }


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "storage": "postgres" if is_postgres_enabled() else "sqlite",
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
    role = str(payload.get("role") or "logist").strip().lower()
    if role not in APP_ROLES:
        raise HTTPException(status_code=400, detail="invalid app role")
    check_app_credentials(username, password)

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


@app.get("/app-api/me/orders")
async def get_my_orders(
    authorization: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    current_user(authorization)
    return {"orders": list_orders()}


@app.post("/app-api/me/orders")
async def publish_my_order(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    current_user(authorization)
    return await publish_order_payload(request)


@app.post("/app-api/orders")
async def publish_order(
    request: Request,
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(x_gpm_app_token)
    return await publish_order_payload(request)


async def publish_order_payload(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        order = normalize_external_order(payload)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    save_order(order)

    return {"success": True, "order_number": order["external_order_id"]}


@app.get("/app-api/orders")
async def get_orders(
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    check_token(x_gpm_app_token)
    return {"orders": list_orders()}


@app.patch("/app-api/orders/{order_id}")
async def update_order(
    order_id: str,
    request: Request,
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(x_gpm_app_token)
    return await update_order_payload(order_id, request)


@app.patch("/app-api/me/orders/{order_id}")
async def update_my_order(
    order_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    current_user(authorization)
    return await update_order_payload(order_id, request)


async def update_order_payload(order_id: str, request: Request) -> dict[str, Any]:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    try:
        patch = await request.json()
        if not isinstance(patch, dict):
            raise ValueError("payload must be an object")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    allowed_fields = {
        "status",
        "assigned_worker_ids",
        "applications",
    }
    for key, value in patch.items():
        if key in allowed_fields:
            order[key] = value

    save_order(order)
    return {"success": True, "order": order}
