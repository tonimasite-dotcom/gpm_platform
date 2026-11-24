"""Versioned manual TS moderation; published orders stay live until approval."""
import asyncio
import copy
import hmac
import re
from uuid import uuid4

from fastapi import Header, HTTPException, Request, Response

from app import crm_logist_ids as ids

EVENT = "order_resubmitted_for_moderation"
PREFIX = "gpm-review-"
BUSY = "Повторная модерация доступна только до начала работ"
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def api():
    from app import app_orders_api
    return app_orders_api


def _one(connection, sql, params=()):
    service = api()
    if service._is_sqlite_connection(connection):
        return connection.execute(sql.replace("%s", "?"), params).fetchone()
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def _guard(connection, order):
    service = api()
    if order.get("status") not in {"NEW", "PROCESSED"} or any(
        order.get(field) for field in (
            "worker_hours", "started_at", "work_started_at",
            "completed_at", "paid_at", "client_paid",
        )
    ):
        raise HTTPException(409, BUSY)
    if _one(connection, f"SELECT 1 FROM {service.ATTENDANCE_TABLE_NAME} WHERE order_id=%s LIMIT 1",
            (str(order["id"]),)):
        raise HTTPException(409, BUSY)


def _reply(parent, request_id, repeated, draft_id=None):
    return {
        "success": True, "order_id": str(parent["id"]),
        "logist_account_id": parent["logist_account_id"],
        "status": "NEW", "request_id": request_id,
        "already_applied": repeated, "moderation_copy_id": draft_id,
    }


def request_moderation(order_id, payload):
    service = api()
    if not isinstance(payload, dict) or set(payload) != {
        "source_instance", "logist_crm_id", "request_id", "revision", "fields"
    }:
        raise HTTPException(422, "Invalid resubmission request")
    if payload["source_instance"] != service.CRM_SYNC_INSTANCE:
        raise HTTPException(403, "Only TS manual resubmission is supported")
    request_id = payload["request_id"]
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise HTTPException(422, "Invalid resubmission request ID")
    revision = payload["revision"]
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{64}", revision) is None:
        raise HTTPException(422, "Invalid publication revision")
    fields = payload["fields"]
    if not isinstance(fields, dict) or not fields or set(fields) - service.CRM_SYNC_FIELDS:
        raise HTTPException(422, "Invalid moderation fields")
    try:
        code = ids.parse_id(payload["logist_crm_id"])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    with service.db_connection() as connection:
        if service._is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        parent = service.read_order_in_connection(connection, order_id, for_update=True)
        if parent is None:
            raise HTTPException(404, "order not found")
        snapshot = service.crm_sync_snapshot(parent)
        try:
            recipient = ids.resolve(connection, code)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if parent.get("logist_account_id") != recipient["account_id"]:
            raise HTTPException(409, "Заявка уже закреплена за другим логистом")
        expression = ("json_extract(details, '$.request_id')"
                      if service._is_sqlite_connection(connection) else "details->>'request_id'")
        seen = _one(connection, f"SELECT details FROM {service.AUDIT_TABLE_NAME} "
                    f"WHERE event_type=%s AND target_id=%s AND {expression}=%s LIMIT 1",
                    (EVENT, str(parent["id"]), request_id))
        if seen:
            import json
            detail = seen[0] if isinstance(seen[0], dict) else json.loads(seen[0])
            return _reply(parent, request_id, True, detail.get("moderation_copy_id"))
        _guard(connection, parent)
        if not hmac.compare_digest(snapshot["revision"], revision):
            raise HTTPException(409, "Published order changed; refresh the candidate")
        changed = {key: value for key, value in fields.items()
                   if value != snapshot["fields"].get(key)}
        normalized = service.clean_crm_sync_patch(parent, changed) if changed else {}
        draft_id = None
        if parent["status"] == "PROCESSED":
            # Only the published parent owns assignments, attendance and finance.
            old_id = parent.get("pending_moderation_id")
            if old_id:
                old = service.read_order_in_connection(connection, str(old_id), for_update=True)
                if old and old.get("moderation_parent_id") == parent["id"]:
                    old.update(moderation_state="superseded")
                    service.write_order_in_connection(connection, old)
            draft_id = PREFIX + uuid4().hex
            draft = copy.deepcopy(parent)
            for field in service.WORKFLOW_FIELDS:
                draft.pop(field, None)
            for field in ("pending_moderation_id", "publication_review_hold",
                          "worker_reviews", "worker_hours", "attendance"):
                draft.pop(field, None)
            draft.update(normalized)
            draft.update(
                id=draft_id, external_order_id=draft_id, status="NEW",
                created_at=service.serialize_datetime(service.utc_now()),
                assigned_worker_ids=[], applications=[],
                moderation_parent_id=str(parent["id"]), moderation_state="pending",
                moderation_base_revision=snapshot["revision"],
                moderation_request_id=request_id,
                has_published_copy=True, published_copy_id=str(parent["id"]),
            )
            service.write_order_in_connection(connection, draft)
            parent.update(pending_moderation_id=draft_id, publication_review_hold=True)
            service.write_order_in_connection(connection, parent)
        else:
            # No published version exists yet: update the same unapproved draft.
            parent.update(normalized)
            service.write_order_in_connection(connection, parent)
        service.record_audit_event_in_connection(
            connection, event_type=EVENT, outcome="success",
            actor_username="workstaff-test-crm", target_type="order",
            target_id=str(parent["id"]), details={
                "request_id": request_id, "crm_logist_id": code,
                "moderation_copy_id": draft_id, "manual": True,
            },
        )
        connection.commit()
        return _reply(parent, request_id, False, draft_id)


def patch_copy(order_id, patch, *, actor, integration):
    service = api()
    if integration or actor is None or actor.get("role") != "logist":
        raise HTTPException(403, "Only the owning logist can review this version")
    # Discover the parent without locking the child first. All reviewers and
    # resubmissions lock parent -> child, avoiding reversed-lock deadlocks.
    with service.db_connection() as connection:
        probe = service.read_order_in_connection(connection, order_id)
    if not probe or not probe.get("moderation_parent_id"):
        raise HTTPException(404, "moderation version not found")
    with service.db_connection() as connection:
        if service._is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        parent = service.read_order_in_connection(connection, str(probe["moderation_parent_id"]),
                                                  for_update=True)
        draft = service.read_order_in_connection(connection, order_id, for_update=True)
        if not parent or not draft or parent.get("logist_account_id") != actor.get("sub"):
            raise HTTPException(403, "moderation owner mismatch")
        if (draft.get("moderation_state") != "pending"
                or parent.get("pending_moderation_id") != order_id):
            raise HTTPException(409, "This moderation version is no longer pending")
        status = patch.get("status")
        if status is not None and status not in {"PROCESSED", "JUNK"}:
            raise HTTPException(422, "Invalid moderation decision")
        normalized = service.validate_order_patch(draft, patch, actor=actor, integration=False)
        if not normalized:
            raise HTTPException(422, "empty moderation patch")
        draft.update({key: value for key, value in normalized.items() if key != "status"})
        if status == "PROCESSED":
            _guard(connection, parent)
            current = service.crm_sync_snapshot(parent)
            if not hmac.compare_digest(current["revision"], draft["moderation_base_revision"]):
                raise HTTPException(409, "Published order changed; request a fresh moderation version")
            content = {key: value for key, value in draft.items()
                       if key in service.ORDER_DRAFT_EDITABLE_FIELDS and value != parent.get(key)}
            content = service.validate_order_patch(parent, content, actor=actor, integration=False)
            for key in service.CRM_SYNC_GEO_FIELDS:
                if key in draft:
                    content[key] = draft[key]
            if int(content.get("workers_count", parent.get("workers_count") or 1)) < len(
                parent.get("assigned_worker_ids") or []
            ):
                raise HTTPException(409, "worker count cannot be lower than assigned workers")
            parent.update(content)
            parent.update(publication_review_hold=False)
            parent.pop("pending_moderation_id", None)
            draft.update(moderation_state="approved", status="PROCESSED")
        elif status == "JUNK":
            # Rejection never cancels the published order. Hold rejected CRM
            # edits until a later manual review instead of applying them by cron.
            parent.pop("pending_moderation_id", None)
            parent["publication_review_hold"] = True
            draft.update(moderation_state="rejected", status="JUNK")
        service.write_order_in_connection(connection, draft)
        if status is not None:
            service.write_order_in_connection(connection, parent)
        service.record_audit_event_in_connection(
            connection, event_type="order_moderation_version_reviewed" if status else "order_draft_updated",
            outcome="success", actor_account_id=str(actor["sub"]),
            target_type="order", target_id=order_id,
            details={"decision": status or "edited", "published_order_id": str(parent["id"])},
        )
        connection.commit()
        return service.order_for_user(parent if status == "PROCESSED" else draft, actor)


def register_routes(app):
    @app.post("/app-api/integration/order-resubmission/{order_id:path}")
    async def resubmit_order(
        order_id: str, request: Request, response: Response,
        x_gpm_app_token: str | None = Header(default=None),
    ):
        service = api()
        service.check_token(x_gpm_app_token)
        response.headers["Cache-Control"] = "no-store"
        payload = await service.bounded_json_payload(request, max_bytes=65536)
        return await asyncio.to_thread(request_moderation, order_id, payload)
