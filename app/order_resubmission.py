"""Explicit manual TS resubmission. Background synchronization keeps its state."""
import asyncio
import re

from fastapi import Header, HTTPException, Request, Response

from app import crm_logist_ids as ids

EVENT = "order_resubmitted_for_moderation"
BUSY = "Повторная модерация доступна только до начала работ"
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def api():
    from app import app_orders_api
    return app_orders_api


def reply(order, request_id, repeated):
    return {
        "success": True,
        "order_id": str(order["id"]),
        "logist_account_id": order["logist_account_id"],
        "status": order["status"],
        "request_id": request_id,
        "already_applied": repeated,
    }


def request_moderation(order_id, payload):
    service = api()
    if not isinstance(payload, dict) or set(payload) != {
        "source_instance", "logist_crm_id", "request_id"
    }:
        raise HTTPException(422, "Invalid resubmission request")
    if payload["source_instance"] != service.CRM_SYNC_INSTANCE:
        raise HTTPException(403, "Only TS manual resubmission is supported")
    request_id = payload["request_id"]
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise HTTPException(422, "Invalid resubmission request ID")
    try:
        code = ids.parse_id(payload["logist_crm_id"])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    with service.db_connection() as connection:
        sqlite = service._is_sqlite_connection(connection)
        if sqlite:
            connection.execute("BEGIN IMMEDIATE")
        order = service.read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "order not found")
        service.crm_sync_snapshot(order)
        try:
            recipient = ids.resolve(connection, code)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if order.get("logist_account_id") != recipient["account_id"]:
            raise HTTPException(409, "Заявка уже закреплена за другим логистом")
        # Keep durable idempotency in the existing audit table. A late network
        # retry must not undo an approval that happened after the first response.
        marker = "?" if sqlite else "%s"
        expression = "json_extract(details, '$.request_id')" if sqlite else "details->>'request_id'"
        sql = (f"SELECT 1 FROM {service.AUDIT_TABLE_NAME} "
               f"WHERE event_type={marker} AND target_id={marker} "
               f"AND {expression}={marker} LIMIT 1")
        parameters = (EVENT, str(order["id"]), request_id)
        if sqlite:
            seen = connection.execute(sql, parameters).fetchone()
        else:
            with connection.cursor() as cursor:
                cursor.execute(sql, parameters)
                seen = cursor.fetchone()
        if seen:
            return reply(order, request_id, True)
        if order.get("status") not in {"NEW", "PROCESSED"} or any(
            order.get(field) for field in (
                "worker_hours", "started_at", "work_started_at",
                "completed_at", "paid_at", "client_paid",
            )
        ):
            raise HTTPException(409, BUSY)
        sql = f"SELECT 1 FROM {service.ATTENDANCE_TABLE_NAME} WHERE order_id={marker} LIMIT 1"
        if sqlite:
            attendance = connection.execute(sql, (str(order["id"]),)).fetchone()
        else:
            with connection.cursor() as cursor:
                cursor.execute(sql, (str(order["id"]),))
                attendance = cursor.fetchone()
        if attendance:
            raise HTTPException(409, BUSY)
        previous = order["status"]
        order["status"] = "NEW"
        service.write_order_in_connection(connection, order)
        service.record_audit_event_in_connection(
            connection, event_type=EVENT, outcome="success",
            actor_username="workstaff-test-crm",
            target_type="order", target_id=str(order["id"]),
            details={"request_id": request_id, "crm_logist_id": code,
                     "previous_status": previous, "status": "NEW", "manual": True},
        )
        connection.commit()
        return reply(order, request_id, False)


def register_routes(app):
    @app.post("/app-api/integration/order-resubmission/{order_id:path}")
    async def resubmit_order(
        order_id: str, request: Request, response: Response,
        x_gpm_app_token: str | None = Header(default=None),
    ):
        service = api()
        service.check_token(x_gpm_app_token)
        response.headers["Cache-Control"] = "no-store"
        payload = await service.bounded_json_payload(request, max_bytes=4096)
        return await asyncio.to_thread(request_moderation, order_id, payload)
