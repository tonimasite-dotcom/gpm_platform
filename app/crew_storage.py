"""Approved additive storage and authorization helpers for QR crew attendance."""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

LINKS = "gpm_app_crm_worker_links"
SESSIONS = "gpm_app_crew_attendance_sessions"
MEMBERS = "gpm_app_crew_attendance_members"
ACTIVE = ("issued", "collected", "awaiting_confirmation", "pending_review", "confirmed")


def api():
    from app import app_orders_api
    return app_orders_api


def enabled():
    return str(api().get_setting("GPM_APP_CREW_ATTENDANCE_ENABLED", "false")).lower() == "true"


def now():
    return api().utc_now()


def stamp(value=None):
    if isinstance(value, str):
        value = api().parse_db_datetime(value)
    return api().serialize_datetime(value or now())


def decode(value, default=None):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {} if default is None else default


def query(connection, statement, parameters=()):
    if api()._is_sqlite_connection(connection):
        cursor = connection.execute(statement, parameters)
    else:
        cursor = connection.cursor()
        cursor.execute(statement.replace("?", "%s"), parameters)
    try:
        if cursor.description is None:
            return []
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def one(connection, statement, parameters=()):
    rows = query(connection, statement, parameters)
    return rows[0] if rows else None


def ensure_schema(connection):
    text = Path(__file__).with_name("crew_attendance_schema.sql").read_text()
    text = text.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
    text = text.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")
    text = text.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
    if api()._is_sqlite_connection(connection):
        text = text.replace("TIMESTAMPTZ", "TEXT").replace("JSONB", "TEXT")
        text = text.replace("'{}'::jsonb", "'{}'").replace("NOW()", "CURRENT_TIMESTAMP")
    for statement in text.split(";"):
        if statement.strip():
            query(connection, statement)
    query(connection, f"INSERT INTO {api().MIGRATIONS_TABLE_NAME}(version) VALUES (?) ON CONFLICT(version) DO NOTHING",
          ("0010_crew_attendance",))


@contextmanager
def transaction():
    api().init_db()
    with api().db_connection() as connection:
        if api()._is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            if not api()._is_sqlite_connection(connection):
                connection.commit()
        except Exception:
            connection.rollback()
            raise


def uid():
    return str(uuid4())


def assigned(order):
    return list(dict.fromkeys(str(x) for x in order.get("assigned_worker_ids") or []))


def actor(user):
    return str(user.get("sub") or "")


def load_order(connection, order_id, user, *, owner=False):
    order = api().read_order_in_connection(connection, order_id, for_update=True)
    if order is None:
        raise HTTPException(404, "Заявка не найдена")
    if owner:
        api().require_role(user, "logist")
        if not api().logist_owns_order(order, user, profile=api().get_account_profile(user)):
            raise HTTPException(403, "Заявка принадлежит другому логисту")
    elif not api()._user_can_view_attendance(order, user):
        raise HTTPException(403, "Нет доступа к табелю")
    return order


def require_open(order):
    if order.get("status") not in {"PROCESSED", "IN_PROCESS"}:
        raise HTTPException(409, "Заявка сейчас не принимает отметки")


def require_enabled():
    if not enabled():
        raise HTTPException(503, "Учет отметок временно приостановлен")


def leader(order):
    workers = assigned(order)
    return workers[0] if len(workers) == 1 else str(order.get("crew_leader_account_id") or "")


def require_leader(order, user):
    api().require_role(user, "worker")
    if actor(user) not in assigned(order) or actor(user) != leader(order):
        raise HTTPException(403, "Это действие доступно только старшему этой заявки")


def fingerprint(order):
    payload = [sorted(assigned(order)), leader(order), order.get("address_lat"), order.get("address_lon")]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def require_roster(session, order):
    if decode(session["leader_evidence"]).get("roster_fingerprint") != fingerprint(order):
        raise HTTPException(409, "Состав или старший изменились. Начните новый сбор")


def protected(order):
    return order.get("attendance_policy") == "crew_geo_v1"


def mark_policy(connection, order):
    if not protected(order):
        order["attendance_policy"] = "crew_geo_v1"
        api().write_order_in_connection(connection, order)


def audit(connection, event, user, order_id, details):
    order = api().read_order_in_connection(connection, str(order_id), for_update=True)
    if order is not None:
        order["crew_event_revision"] = int(order.get("crew_event_revision") or 0)+1
        api().write_order_in_connection(connection, order)
    api().record_audit_event_in_connection(
        connection, event_type=event, outcome="success",
        actor_account_id=actor(user), actor_username=str(user.get("username") or user.get("role") or ""),
        target_type="order", target_id=str(order_id), details=details,
    )


def eligible(connection, order_id, worker_id, action):
    row = api()._read_attendance_in_connection(connection, order_id, worker_id) or {}
    return (not row.get("check_in_at")) if action == "check_in" else (
        bool(row.get("check_in_at")) and not row.get("check_out_at"))


def next_action(connection, order_id, worker_id):
    if eligible(connection, order_id, worker_id, "check_in"):
        return "check_in"
    if eligible(connection, order_id, worker_id, "check_out"):
        return "check_out"
    raise HTTPException(409, "Приход и уход уже подтверждены")


def action_value(value):
    if value not in {"check_in", "check_out"}:
        raise HTTPException(422, "Укажите приход или уход")
    return value


def geo_evidence(location, order):
    received = stamp()
    result = {"status": "review", "reason": "Геолокация недоступна", "received_at": received}
    if not isinstance(location, dict):
        return result
    try:
        fields = [location.get(k) for k in ("lat", "lon", "accuracy")]
        if any(isinstance(x, bool) for x in fields):
            return result
        lat, lon, accuracy = map(float, fields)
        if not all(math.isfinite(x) for x in (lat, lon, accuracy)):
            return result
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= accuracy <= 10000):
            return result
        result.update(lat=lat, lon=lon, accuracy=accuracy)
        measured = api().parse_db_datetime(location.get("measured_at"))
        if measured is None or abs((now() - measured).total_seconds()) > 30:
            result["reason"] = "Нет свежего измерения геолокации"
            return result
        result["measured_at"] = stamp(measured)
        if accuracy > 100:
            result["reason"] = "Недостаточная точность геолокации"
            return result
        target_lat, target_lon = float(order["address_lat"]), float(order["address_lon"])
        if not (math.isfinite(target_lat) and math.isfinite(target_lon) and
                -90 <= target_lat <= 90 and -180 <= target_lon <= 180):
            return result
        phi = math.radians(lat - target_lat)
        lam = math.radians(lon - target_lon)
        value = math.sin(phi / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(target_lat)) * math.sin(lam / 2) ** 2
        distance = 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, value))))
        result["distance_m"] = round(distance)
        if distance > 200:
            result["reason"] = "Координаты за пределами зоны объекта"
            return result
        result.update(status="valid", reason="")
    except (KeyError, ValueError, TypeError, OverflowError):
        result["reason"] = "Не задана точная точка объекта"
    return result


def expire_unconfirmed(connection, order_id):
    timestamp = stamp()
    # Client-confirmed rows awaiting human review must never expire with the QR.
    query(connection, f"""UPDATE {MEMBERS} SET status='expired'
        WHERE order_id=? AND status='issued' AND token_expires_at<=?""", (order_id, timestamp))
    sessions = query(connection, f"""SELECT session_id FROM {SESSIONS}
        WHERE order_id=? AND status IN ('collecting','awaiting_confirmation') AND expires_at<=?
        AND client_confirmed_at IS NULL""", (order_id, timestamp))
    for session in sessions:
        query(connection, f"""UPDATE {MEMBERS} SET status='expired'
            WHERE session_id=? AND status IN ('collected','awaiting_confirmation')""", (session["session_id"],))
        query(connection, f"UPDATE {SESSIONS} SET status='expired' WHERE session_id=?", (session["session_id"],))


def guard_close(connection, order):
    if not protected(order) or order.get("status") not in {"DONE_PENDING", "CONVERTED"}:
        return
    previous = api().read_order_in_connection(connection, str(order.get("id") or order["external_order_id"]))
    if previous and previous.get("status") in {"DONE_PENDING", "CONVERTED", "JUNK"}:
        return
    for worker_id in assigned(order):
        row = api()._read_attendance_in_connection(connection, str(order["id"]), worker_id) or {}
        if not row.get("check_out_at"):
            raise HTTPException(409, "Сначала подтвердите приход и уход каждого исполнителя")
    if one(connection, f"SELECT evidence_id FROM {MEMBERS} WHERE order_id=? AND status='pending_review' LIMIT 1",
           (str(order["id"]),)):
        raise HTTPException(409, "Есть отметки на проверке у логиста")
