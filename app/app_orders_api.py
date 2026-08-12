import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yml"
DB_FILE = BASE_DIR / "crm_app_orders.sqlite3"

app = FastAPI(title="GPM App Orders API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def read_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_app_orders (
                order_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def check_token(token: str | None) -> None:
    config = read_config()
    expected = config.get("GPM_APP_API_TOKEN") or config.get("CRM_API_KEY")
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid app token")


def normalize_crm_order(payload: dict[str, Any]) -> dict[str, Any]:
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
        "source": "crm",
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
        "crm_payload": payload,
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
    return {"status": "ok"}


@app.post("/app-api/orders")
async def publish_order(
    request: Request,
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(x_gpm_app_token)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        order = normalize_crm_order(payload)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    with sqlite3.connect(DB_FILE) as connection:
        connection.execute(
            """
            INSERT INTO crm_app_orders(order_id, data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(order_id) DO UPDATE SET
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
            """,
            (order["external_order_id"], json.dumps(order, ensure_ascii=False)),
        )

    return {"success": True, "order_number": order["external_order_id"]}


@app.get("/app-api/orders")
async def get_orders(
    x_gpm_app_token: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    check_token(x_gpm_app_token)
    init_db()
    with sqlite3.connect(DB_FILE) as connection:
        rows = connection.execute(
            "SELECT data FROM crm_app_orders ORDER BY updated_at DESC"
        ).fetchall()
    return {"orders": [json.loads(row[0]) for row in rows]}
