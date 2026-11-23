"""Frozen QR confirmation, exception review and restricted CRM exchange."""
import hashlib
import json

from fastapi import HTTPException

from app import crew_storage as s
from app import crew_flow as flow


def for_challenge(connection, challenge_id):
    return s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE final_challenge_id=?", (challenge_id,))


def preview(challenge_id):
    with s.transaction() as connection:
        session = for_challenge(connection, challenge_id)
        if not session:
            return {}
        order = s.api().read_order_in_connection(connection, session["order_id"], for_update=True)
        if not order:
            raise HTTPException(404, "Заявка не найдена")
        s.require_roster(session, order)
        rows = s.query(connection, f"SELECT * FROM {s.MEMBERS} WHERE session_id=? AND status='awaiting_confirmation' ORDER BY collected_at",
                       (session["session_id"],))
        if not rows:
            raise HTTPException(409, "Список уже подтвержден или отменен")
        return {"crew_session_id": session["session_id"],
                "participants": [{"worker_name": s.api()._worker_name_in_connection(connection, row["worker_account_id"]),
                                  "collected_at": s.stamp(row["collected_at"]),
                                  "geo_status": row["geo_status"]} for row in rows]}


def _refresh_session(connection, session_id):
    rows = s.query(connection, f"SELECT status FROM {s.MEMBERS} WHERE session_id=?", (session_id,))
    statuses = [r["status"] for r in rows]
    pending = "pending_review" in statuses
    confirmed = "confirmed" in statuses
    status = "partially_confirmed" if pending and confirmed else "pending_review" if pending else "confirmed" if confirmed else "rejected"
    s.query(connection, f"UPDATE {s.SESSIONS} SET status=? WHERE session_id=?", (status, session_id))


def complete(connection, challenge, confirmer):
    session = for_challenge(connection, challenge["challenge_id"])
    if not session:
        return None
    if session["status"] != "awaiting_confirmation":
        raise HTTPException(409, "Этот список уже обработан")
    order = s.api().read_order_in_connection(connection, session["order_id"], for_update=True)
    if order is None:
        raise HTTPException(404, "Заявка не найдена")
    s.require_open(order)
    s.require_roster(session, order)
    rows = s.query(connection, f"SELECT * FROM {s.MEMBERS} WHERE session_id=? AND status='awaiting_confirmation' ORDER BY worker_account_id",
                   (session["session_id"],))
    if not rows:
        raise HTTPException(409, "Нет участников для подтверждения")
    # Validate the entire immutable snapshot before writing any individual row.
    for row in rows:
        if row["worker_account_id"] not in s.assigned(order) or not s.eligible(
                connection, session["order_id"], row["worker_account_id"], session["action"]):
            raise HTTPException(409, "Состав или отметки изменились. Повторите сбор")
    confirmed_at = s.stamp()
    s.query(connection, f"UPDATE {s.SESSIONS} SET client_confirmed_at=?,confirmed_by=? WHERE session_id=?",
            (confirmed_at, confirmer, session["session_id"]))
    result = []
    pending = 0
    for row in rows:
        timestamp = s.stamp(row["collected_at"])
        if row["geo_status"] != "valid":
            s.query(connection, f"UPDATE {s.MEMBERS} SET status='pending_review',effective_at=? WHERE evidence_id=?",
                    (timestamp, row["evidence_id"]))
            pending += 1
            continue
        s.query(connection, f"UPDATE {s.MEMBERS} SET status='confirmed',effective_at=? WHERE evidence_id=?",
                (timestamp, row["evidence_id"]))
        individual = {**challenge, "worker_account_id": row["worker_account_id"]}
        result.append(s.api()._complete_attendance_event_in_connection(
            connection, individual, confirmer=confirmer, event_at=s.api().parse_db_datetime(timestamp), _crew_member=True))
    # Even a wholly pending batch consumes the final QR.
    s.query(connection, f"UPDATE {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} SET used_at=? WHERE challenge_id=?",
            (confirmed_at, challenge["challenge_id"]))
    _refresh_session(connection, session["session_id"])
    s.audit(connection, "crew_client_confirmed", {"role": "client" if confirmer.startswith("client:") else "guest",
             "sub": confirmer.split(":",1)[1] if confirmer.startswith("client:") else ""},
            session["order_id"], {"session_id": session["session_id"], "confirmed": len(result), "pending_review": pending})
    return {"crew": True, "rows": result, "pending_review": pending, "session_id": session["session_id"]}


def review(evidence_id, user, decision, reason):
    if decision not in {"approve", "reject"} or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
        raise HTTPException(422, "Выберите решение и укажите причину от 3 до 1000 символов")
    with s.transaction() as connection:
        proof = s.one(connection, f"SELECT * FROM {s.MEMBERS} WHERE evidence_id=?", (evidence_id,))
        if not proof:
            raise HTTPException(404, "Отметка не найдена")
        order = s.load_order(connection, proof["order_id"], user, owner=True)
        s.require_open(order)
        # Re-read under the order lock; competing reviews cannot both pass.
        proof = s.one(connection, f"SELECT * FROM {s.MEMBERS} WHERE evidence_id=?", (evidence_id,))
        session = s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE session_id=?", (proof["session_id"],))
        if proof["status"] != "pending_review" or not session or not session["client_confirmed_at"]:
            raise HTTPException(409, "Отметка не ожидает решения после подтверждения клиента")
        if decision == "approve" and (proof["worker_account_id"] not in s.assigned(order) or not s.eligible(
                connection, proof["order_id"], proof["worker_account_id"], proof["action"])):
            raise HTTPException(409, "Назначение или отметки изменились")
        timestamp = s.stamp(proof["collected_at"])
        s.query(connection, f"""UPDATE {s.MEMBERS} SET status=?,reviewed_by=?,reviewed_at=?,
            review_reason=?,effective_at=? WHERE evidence_id=?""",
            ("confirmed" if decision=="approve" else "rejected", s.actor(user), s.stamp(), reason.strip(), timestamp, evidence_id))
        if decision == "approve":
            challenge = {"challenge_id": session["final_challenge_id"], "order_id": proof["order_id"],
                         "worker_account_id": proof["worker_account_id"], "action": proof["action"]}
            s.api()._complete_attendance_event_in_connection(connection, challenge,
                confirmer="logist:"+s.actor(user), event_at=s.api().parse_db_datetime(timestamp), _crew_member=True)
        _refresh_session(connection, session["session_id"])
        s.audit(connection, "crew_geo_reviewed", user, proof["order_id"],
                {"evidence_id": evidence_id, "decision": decision, "reason": reason.strip()})
    return {"success": True}


def crm_actor(connection, order, payload):
    if payload.get("source_instance") != s.api().CRM_SYNC_INSTANCE:
        raise HTTPException(403, "Поддерживается только тестовая CRM")
    s.api().crm_sync_snapshot(order)
    try:
        resolved = s.api().crm_logist_ids.resolve(connection, payload.get("sender_crm_id"))
    except (ValueError, TypeError):
        raise HTTPException(403, "Укажите сохраненный ID логиста GPM")
    # Resolver response contains the canonical recipient account, not a phone fallback.
    account_id = str(resolved.get("account_id") or resolved.get("logist_account_id") or "")
    user = {"sub": account_id, "role": "logist", "username": "crm-logist"}
    if not account_id or not s.api().logist_owns_order(order, user, profile=s.api().get_account_profile(user)):
        raise HTTPException(403, "Заявка принадлежит другому логисту")
    return user


def link_worker(order_id, payload):
    s.require_enabled()
    crm_id = str(payload.get("crm_worker_id") or "")
    worker_id = str(payload.get("worker_account_id") or "")
    if not crm_id.isdigit() or len(crm_id)>20 or int(crm_id)<=0:
        raise HTTPException(422, "Нужен ID рабочего CRM")
    with s.transaction() as connection:
        order = s.api().read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "Заявка не найдена")
        user = crm_actor(connection, order, payload)
        if worker_id not in s.assigned(order):
            raise HTTPException(422, "Сначала назначьте профиль исполнителя на эту заявку GPM")
        suffix = "" if s.api()._is_sqlite_connection(connection) else " FOR UPDATE"
        account = s.one(connection, f"SELECT role,is_active FROM {s.api().ACCOUNTS_TABLE_NAME} WHERE account_id=?"+suffix, (worker_id,))
        if not account or account["role"]!="worker" or not account["is_active"]:
            raise HTTPException(422, "Нужен активный исполнитель GPM")
        links = s.query(connection, f"SELECT * FROM {s.LINKS} WHERE source_instance=? AND (crm_worker_id=? OR worker_account_id=?)",
                        (s.api().CRM_SYNC_INSTANCE, crm_id, worker_id))
        if links:
            if len(links)==1 and links[0]["crm_worker_id"]==crm_id and links[0]["worker_account_id"]==worker_id:
                return {"success": True}
            raise HTTPException(409, "Рабочий уже связан с другим профилем. Автоматическая замена запрещена")
        s.query(connection, f"INSERT INTO {s.LINKS}(source_instance,crm_worker_id,worker_account_id,linked_by,linked_at) VALUES (?,?,?,?,?)",
                (s.api().CRM_SYNC_INSTANCE, crm_id, worker_id, s.actor(user), s.stamp()))
        s.audit(connection, "crew_crm_worker_linked", user, order["id"], {"crm_worker_id": crm_id, "worker_account_id": worker_id})
    return {"success": True}


def sync_roster(order_id, payload):
    s.require_enabled()
    ids = payload.get("crm_worker_ids")
    if not isinstance(ids, list) or not ids or len(ids)>200 or any(
            not isinstance(v,(str,int)) or isinstance(v,bool) or not str(v).isdigit() for v in ids):
        raise HTTPException(422, "Некорректный состав CRM")
    ids = list(dict.fromkeys(str(v) for v in ids))
    with s.transaction() as connection:
        order = s.api().read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "Заявка не найдена")
        user = crm_actor(connection, order, payload)
        s.require_open(order)
        links = s.query(connection, f"SELECT crm_worker_id,worker_account_id FROM {s.LINKS} WHERE source_instance=?",
                        (s.api().CRM_SYNC_INSTANCE,))
        mapping = {r["crm_worker_id"]:r["worker_account_id"] for r in links}
        missing = [x for x in ids if x not in mapping]
        if missing:
            raise HTTPException(409, "Сначала свяжите профили всех назначенных рабочих")
        workers = [mapping[x] for x in ids]
        chosen = str(payload.get("crm_leader_id") or "")
        if len(workers)>1 and chosen not in ids:
            raise HTTPException(409, "Назначьте бригадира в CRM")
        new_leader = mapping[chosen] if chosen in ids else workers[0]
        if set(workers) != set(s.assigned(order)):
            if payload.get("apply_roster") is not True or payload.get("expected_roster") != s.fingerprint(order):
                raise HTTPException(409, "Состав CRM и GPM различается. Подтвердите его явно")
            if len(workers)>int(order.get("workers_count") or 0):
                raise HTTPException(409, "Состав больше количества мест в заявке")
            removed = set(s.assigned(order))-set(workers)
            for worker_id in removed:
                if s.api()._read_attendance_in_connection(connection, str(order["id"]), worker_id) or s.one(
                        connection, f"SELECT evidence_id FROM {s.MEMBERS} WHERE order_id=? AND worker_account_id=? AND status NOT IN ('expired','rejected') LIMIT 1",
                        (str(order["id"]), worker_id)):
                    raise HTTPException(409, "У снимаемого исполнителя есть отметки. Нужна отдельная проверка")
            for worker_id in workers:
                account = s.one(connection, f"SELECT role,is_active FROM {s.api().ACCOUNTS_TABLE_NAME} WHERE account_id=?", (worker_id,))
                if not account or account["role"]!="worker" or not account["is_active"]:
                    raise HTTPException(409, "В составе есть неактивный профиль")
            order["assigned_worker_ids"] = workers
        if order.get("crew_leader_account_id") != new_leader or payload.get("apply_roster") is True:
            flow.assign_leader(connection, order, new_leader, user)
    return {"success": True}


def export(order_id, payload):
    with s.transaction() as connection:
        order = s.api().read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "Заявка не найдена")
        user = crm_actor(connection, order, payload)
        links = s.query(connection, f"SELECT crm_worker_id,worker_account_id FROM {s.LINKS} WHERE source_instance=?",
                        (s.api().CRM_SYNC_INSTANCE,))
        mapping = {r["worker_account_id"]:r["crm_worker_id"] for r in links}
        proofs = s.query(connection, f"SELECT * FROM {s.MEMBERS} WHERE order_id=? AND status NOT IN ('issued','expired') ORDER BY issued_at,evidence_id",
                         (str(order["id"]),))
        rows = []
        for worker_id in s.assigned(order):
            attendance = s.api()._read_attendance_in_connection(connection, str(order["id"]), worker_id) or {}
            rows.append({"worker_account_id": worker_id, "crm_worker_id": mapping.get(worker_id),
                         "worker_name": s.api()._worker_name_in_connection(connection, worker_id),
                         "is_leader": worker_id==s.leader(order),
                         "check_in_at": attendance.get("check_in_at"), "check_out_at": attendance.get("check_out_at"),
                         "duration_minutes": attendance.get("duration_minutes")})
        document = {"protocol":"gpm-crew-attendance-v1","source_instance":s.api().CRM_SYNC_INSTANCE,
                    "enabled":s.enabled() or s.protected(order), "order_id":str(order["id"]),
                    "roster_fingerprint":s.fingerprint(order), "rows":rows,
                    "proofs":[{**flow.proof_view(connection,p,private=True),"crm_worker_id":mapping.get(p["worker_account_id"])}
                              for p in proofs]}
        canonical = json.dumps(document, sort_keys=True, ensure_ascii=True, default=str)
        document["revision"] = hashlib.sha256(canonical.encode()).hexdigest()
        return document


def crm_review(order_id, payload):
    with s.transaction() as connection:
        order = s.api().read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(404, "Заявка не найдена")
        user = crm_actor(connection, order, payload)
        evidence = s.one(connection, f"SELECT order_id FROM {s.MEMBERS} WHERE evidence_id=?", (str(payload.get("evidence_id") or ""),))
        if not evidence or evidence["order_id"]!=str(order["id"]):
            raise HTTPException(404, "Отметка не найдена")
    return review(str(payload["evidence_id"]), user, str(payload.get("decision") or ""), payload.get("reason"))


def guest_list_html(context):
    import html
    rows = context.get("participants") or []
    if not rows:
        return ""
    items = []
    for row in rows:
        timestamp = s.api().parse_db_datetime(row.get("collected_at"))
        label = timestamp.astimezone(s.api().MOSCOW_TZ).strftime("%d.%m.%Y %H:%M") if timestamp else ""
        pending = " · геолокация на проверке у логиста" if row.get("geo_status") != "valid" else ""
        items.append("<li>"+html.escape(str(row["worker_name"]))+" — "+html.escape(label+pending)+"</li>")
    return "<div class='meta'><strong>Подтверждаемый список</strong><ul>"+"".join(items)+"</ul></div><p>Подтверждайте только если все перечисленные исполнители находятся рядом.</p>"
