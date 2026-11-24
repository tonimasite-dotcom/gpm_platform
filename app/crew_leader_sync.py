"""Headless TS brigadier handoff. No CRM UI, assignments, hours or profile writes."""
from fastapi import HTTPException
from app import crew_storage as s, crew_flow as flow, crew_confirmation as confirmation
from app.phone_numbers import normalize_russian_phone


def _resolve(connection, order, leader):
    if leader is None:
        return None, "Назначьте бригадира этой заявки в TS"
    if not isinstance(leader, dict) or set(leader) != {"crm_worker_id", "phone"}:
        raise HTTPException(422, "Некорректное назначение бригадира")
    crm_id = leader["crm_worker_id"]
    if not isinstance(crm_id, str) or not crm_id.isascii() or not crm_id.isdigit() or not 0 < len(crm_id) <= 20 or int(crm_id) <= 0:
        raise HTTPException(422, "Некорректный ID бригадира")
    try:
        phone = normalize_russian_phone(leader["phone"])
    except ValueError:
        return None, "Проверьте телефон бригадира в TS и GPM"
    # Exact normalized identity; no suffix/name matching, no account creation.
    matches = []
    for row in s.query(connection, f"""SELECT a.account_id,p.data FROM {s.api().ACCOUNTS_TABLE_NAME} a
            JOIN {s.api().PROFILES_TABLE_NAME} p ON p.account_id=a.account_id
            WHERE a.role='worker' AND a.is_active=TRUE"""):
        try:
            if normalize_russian_phone(s.decode(row["data"]).get("phone", "")) == phone:
                matches.append(row["account_id"])
        except ValueError:
            pass
    if len(matches) != 1:
        return None, "Телефон бригадира должен соответствовать одному активному исполнителю GPM"
    worker_id = matches[0]
    if worker_id not in s.assigned(order):
        return None, "Бригадир TS должен быть назначен на эту заявку в GPM"
    links = s.query(connection, f"""SELECT crm_worker_id,worker_account_id FROM {s.LINKS}
        WHERE source_instance=? AND (crm_worker_id=? OR worker_account_id=?)""",
        (s.api().CRM_SYNC_INSTANCE, crm_id, worker_id))
    if any(str(r["crm_worker_id"]) != crm_id or r["worker_account_id"] != worker_id for r in links):
        return None, "Привязка бригадира к профилю GPM требует проверки логиста"
    return worker_id, ""


def sync(order_id, payload):
    s.require_enabled()
    if not isinstance(payload, dict) or set(payload) != {"operation", "source_instance", "sender_crm_id", "leader"}:
        raise HTTPException(422, "Некорректный запрос назначения бригадира")
    with s.transaction() as connection:
        order = s.api().read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "Заявка не найдена")
        user = confirmation.crm_actor(connection, order, payload)
        if order.get("moderation_parent_id"):
            raise HTTPException(409, "Назначайте старшего опубликованной заявки")
        if order.get("status") not in {"PROCESSED", "IN_PROCESS"}:
            return {"success": True, "ready": False, "preserved": True}
        # Enrollment never converts an existing legacy shift or invalidates its QR.
        if not s.protected(order):
            recorded = s.one(connection, f"SELECT attendance_id FROM {s.api().ATTENDANCE_TABLE_NAME} WHERE order_id=? LIMIT 1", (str(order["id"]),))
            outstanding = s.one(connection, f"""SELECT challenge_id FROM {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME}
                WHERE order_id=? AND used_at IS NULL AND expires_at>? LIMIT 1""", (str(order["id"]), s.stamp()))
            if recorded or outstanding:
                return {"success": True, "ready": False, "preserved": True}
        worker_id, reason = _resolve(connection, order, payload["leader"])
        previous = (order.get("crew_leader_account_id"), order.get("crew_leader_sync_blocked"),
                    order.get("crew_leader_sync_managed"), order.get("attendance_policy"))
        changed = previous != (worker_id or "", reason, True, "crew_geo_v1" if worker_id else order.get("attendance_policy"))
        if changed:
            if worker_id:
                flow.assign_leader(connection, order, worker_id, user)
                order = s.api().read_order_in_connection(connection, order_id, for_update=True)
                order["crew_crm_leader_id"] = payload["leader"]["crm_worker_id"]
                s.mark_policy(connection, order)
            else:
                flow.expire_collections(connection, order)
                order["crew_leader_account_id"] = ""
                order.pop("crew_crm_leader_id", None)
            order["crew_leader_sync_managed"] = True
            order["crew_leader_sync_blocked"] = reason
            s.api().write_order_in_connection(connection, order)
            s.audit(connection, "crew_ts_leader_synced", user, order["id"],
                    {"ready": worker_id is not None, "worker_account_id": worker_id})
        return {"success": True, "ready": worker_id is not None, "reason": reason}
