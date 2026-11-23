"""Single-use presence QR collection. All changes lock the owning order."""
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException

from app import crew_storage as s


def _member(connection, order, worker_id, action, location, *, session_id=None, scanner=None):
    order_id = str(order["id"])
    if not s.eligible(connection, order_id, worker_id, action):
        raise HTTPException(409, "Это действие для исполнителя сейчас недоступно")
    existing = s.one(connection, f"""SELECT evidence_id FROM {s.MEMBERS}
        WHERE order_id=? AND worker_account_id=? AND action=?
        AND status IN ('collected','awaiting_confirmation','pending_review','confirmed')""",
        (order_id, worker_id, action))
    if existing:
        raise HTTPException(409, "Отметка уже в сборе или ожидает подтверждения")
    s.query(connection, f"""UPDATE {s.MEMBERS} SET status='expired'
        WHERE order_id=? AND worker_account_id=? AND action=? AND status='issued'""",
        (order_id, worker_id, action))
    evidence_id = s.uid()
    secret = secrets.token_urlsafe(32) if session_id is None else None
    evidence = s.geo_evidence(location, order)
    instant = s.stamp()
    s.query(connection, f"""INSERT INTO {s.MEMBERS}(
        evidence_id,order_id,worker_account_id,action,session_id,token_hash,
        token_expires_at,issued_at,collected_at,scanned_by,worker_evidence,
        scanner_evidence,geo_status,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (evidence_id, order_id, worker_id, action, session_id,
         s.api()._attendance_secret_hash(secret) if secret else None,
         s.stamp(s.now()+timedelta(seconds=60)) if secret else None, instant,
         instant if session_id else None, scanner if session_id else None,
         json.dumps(evidence), json.dumps(evidence if session_id else {}),
         "valid" if evidence["status"]=="valid" else "review",
         "collected" if session_id else "issued"))
    return evidence_id, secret


def presence(order_id, user, location=None, action=None, public_api_url=None):
    s.require_enabled()
    s.api().require_role(user, "worker")
    with s.transaction() as connection:
        order = s.load_order(connection, order_id, user)
        s.require_open(order)
        if not s.protected(order):
            raise HTTPException(409, "Сначала логист должен включить новый QR-табель")
        s.expire_unconfirmed(connection, str(order["id"]))
        if s.actor(user) == s.leader(order):
            session = _start(connection, order, user, action, location)
            return _freeze(connection, order, user, session, public_api_url=public_api_url)
        if not s.leader(order) or s.leader(order) not in s.assigned(order):
            raise HTTPException(409, "Логист должен назначить старшего этой заявки")
        action = s.action_value(action) if action else s.next_action(connection, str(order["id"]), s.actor(user))
        evidence_id, secret = _member(connection, order, s.actor(user), action, location)
        s.mark_policy(connection, order)
        s.audit(connection, "crew_presence_issued", user, order["id"], {"evidence_id": evidence_id, "action": action})
        return {
            "kind": "presence", "evidence_id": evidence_id, "action": action,
            "verifier_mode": "crew_scan",
            "confirmation_url": "gpm-crew-presence:" + secret,
            "expires_at": s.stamp(s.now()+timedelta(seconds=60)),
            "expires_in_seconds": 60,
        }


def _start(connection, order, user, action, location):
    s.require_leader(order, user)
    s.require_open(order)
    if not s.protected(order):
        raise HTTPException(409, "Сначала логист должен включить новый QR-табель")
    order_id = str(order["id"])
    s.expire_unconfirmed(connection, order_id)
    action = s.action_value(action) if action else s.next_action(connection, order_id, s.actor(user))
    existing = s.one(connection, f"""SELECT * FROM {s.SESSIONS}
        WHERE order_id=? AND leader_account_id=? AND status IN ('collecting','awaiting_confirmation')
        ORDER BY created_at DESC LIMIT 1""", (order_id, s.actor(user)))
    if existing:
        s.require_roster(existing, order)
        if existing["action"] != action:
            raise HTTPException(409, "Завершите или отмените текущий сбор")
        return existing
    session_id = s.uid()
    evidence = s.geo_evidence(location, order)
    evidence["roster_fingerprint"] = s.fingerprint(order)
    s.query(connection, f"""INSERT INTO {s.SESSIONS}(
        session_id,order_id,leader_account_id,attendance_mode,action,roster_revision,
        status,leader_evidence,created_at,expires_at)
        VALUES (?,?,?,?,?,?,'collecting',?,?,?)""",
        (session_id, order_id, s.actor(user), "solo" if len(s.assigned(order))==1 else "crew",
         action, max(1, int(order.get("crew_roster_revision") or 1)), json.dumps(evidence),
         s.stamp(), s.stamp(s.now()+timedelta(minutes=15))))
    if s.eligible(connection, order_id, s.actor(user), action):
        _member(connection, order, s.actor(user), action, location, session_id=session_id, scanner=s.actor(user))
    s.mark_policy(connection, order)
    s.audit(connection, "crew_collection_started", user, order_id, {"session_id": session_id, "action": action})
    return s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE session_id=?", (session_id,))


def start(order_id, user, action, location):
    s.require_enabled()
    with s.transaction() as connection:
        order = s.load_order(connection, order_id, user)
        session = _start(connection, order, user, action, location)
        return session_view(connection, session, user)


def _session(connection, session_id, user):
    session = s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE session_id=?", (session_id,))
    if not session:
        raise HTTPException(404, "Сбор не найден")
    order = s.load_order(connection, session["order_id"], user)
    s.require_leader(order, user)
    if session["leader_account_id"] != s.actor(user):
        raise HTTPException(403, "Сбор принадлежит другому старшему")
    s.require_open(order)
    s.require_roster(session, order)
    if s.api().parse_db_datetime(session["expires_at"]) <= s.now():
        raise HTTPException(410, "Срок сбора истек. Начните новый сбор")
    return session, order


def scan(session_id, user, token, location):
    s.require_enabled()
    if token.startswith("gpm-crew-presence:"):
        token = token[len("gpm-crew-presence:"):]
    if not 20 <= len(token) <= 128:
        raise HTTPException(422, "Это не QR присутствия исполнителя")
    with s.transaction() as connection:
        session, order = _session(connection, session_id, user)
        if session["status"] != "collecting":
            raise HTTPException(409, "Список уже зафиксирован. Создайте новый сбор")
        proof = s.one(connection, f"SELECT * FROM {s.MEMBERS} WHERE token_hash=?",
                      (s.api()._attendance_secret_hash(token),))
        if not proof:
            raise HTTPException(404, "QR не найден")
        if proof["status"] != "issued" or proof["session_id"] is not None:
            raise HTTPException(409, "Этот QR уже использован")
        if s.api().parse_db_datetime(proof["token_expires_at"]) <= s.now():
            raise HTTPException(410, "QR истек. Исполнитель должен обновить его")
        if proof["order_id"] != str(order["id"]) or proof["action"] != session["action"]:
            raise HTTPException(409, "QR относится к другому заказу или действию")
        if proof["worker_account_id"] not in s.assigned(order):
            raise HTTPException(403, "Исполнитель не назначен на эту заявку")
        if not s.eligible(connection, str(order["id"]), proof["worker_account_id"], proof["action"]):
            raise HTTPException(409, "Отметка исполнителя уже изменилась")
        scanner = s.geo_evidence(location, order)
        valid = scanner["status"] == "valid" and s.decode(proof["worker_evidence"]).get("status") == "valid"
        s.query(connection, f"""UPDATE {s.MEMBERS} SET session_id=?,collected_at=?,scanned_by=?,
            scanner_evidence=?,geo_status=?,status='collected' WHERE evidence_id=?""",
            (session_id, s.stamp(), s.actor(user), json.dumps(scanner),
             "valid" if valid else "review", proof["evidence_id"]))
        s.audit(connection, "crew_presence_scanned", user, order["id"],
                {"session_id": session_id, "evidence_id": proof["evidence_id"], "geo_status": "valid" if valid else "review"})
        return session_view(connection, session, user)


def _freeze(connection, order, user, session, public_api_url):
    s.require_leader(order, user)
    s.require_roster(session, order)
    if session["status"] not in {"collecting", "awaiting_confirmation"}:
        raise HTTPException(409, "Этот сбор уже завершен")
    if session.get("final_challenge_id"):
        previous = s.one(connection, f"SELECT * FROM {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} WHERE challenge_id=?",
                         (session["final_challenge_id"],))
        if previous and previous.get("verifier_confirmed_at") and s.api().parse_db_datetime(previous["expires_at"]) > s.now():
            raise HTTPException(409, "Клиент уже подтвердил этот список")
        s.query(connection, f"UPDATE {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} SET expires_at=? WHERE challenge_id=?",
                (s.stamp(), session["final_challenge_id"]))
    rows = s.query(connection, f"""SELECT * FROM {s.MEMBERS} WHERE session_id=?
        AND status IN ('collected','awaiting_confirmation') ORDER BY worker_account_id""", (session["session_id"],))
    if not rows:
        raise HTTPException(409, "Сначала отсканируйте исполнителей")
    for row in rows:
        if row["worker_account_id"] not in s.assigned(order) or not s.eligible(
                connection, str(order["id"]), row["worker_account_id"], session["action"]):
            raise HTTPException(409, "Отметки изменились. Начните новый сбор")
    token = secrets.token_urlsafe(32)
    code = s.api()._unique_attendance_code(connection, "request_code_hash",
                                          alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789", length=8)
    challenge_id = s.uid()
    expiry = min(s.now()+timedelta(seconds=60), s.api().parse_db_datetime(session["expires_at"]))
    mode = s.api()._attendance_verifier_mode(order)
    s.query(connection, f"""INSERT INTO {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME}(
        challenge_id,order_id,worker_account_id,action,token_hash,request_code_hash,
        verifier_mode,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (challenge_id, str(order["id"]), s.actor(user), session["action"],
         s.api()._attendance_secret_hash(token), s.api()._attendance_secret_hash(code), mode, s.stamp(expiry), s.stamp()))
    s.query(connection, f"""UPDATE {s.SESSIONS} SET status='awaiting_confirmation',
        final_challenge_id=?,frozen_at=? WHERE session_id=?""", (challenge_id, s.stamp(), session["session_id"]))
    s.query(connection, f"UPDATE {s.MEMBERS} SET status='awaiting_confirmation' WHERE session_id=? AND status='collected'",
            (session["session_id"],))
    s.audit(connection, "crew_collection_frozen", user, order["id"],
            {"session_id": session["session_id"], "participants": len(rows)})
    base = public_api_url or s.api().get_setting("GPM_APP_PUBLIC_API_URL", "https://app-api.gpmbot.ru")
    return {"kind": "confirmation", "session_id": session["session_id"], "challenge_id": challenge_id,
            "order_id": str(order["id"]), "action": session["action"], "verifier_mode": mode,
            "confirmation_url": base.rstrip("/")+"/attendance/confirm/"+token,
            "request_code": code, "expires_at": s.stamp(expiry), "expires_in_seconds": max(0, int((expiry-s.now()).total_seconds())),
            "participants": len(rows)}


def freeze(session_id, user, public_api_url):
    s.require_enabled()
    with s.transaction() as connection:
        session, order = _session(connection, session_id, user)
        return _freeze(connection, order, user, session, public_api_url)


def cancel(session_id, user):
    with s.transaction() as connection:
        session = s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE session_id=?", (session_id,))
        if not session:
            raise HTTPException(404, "Сбор не найден")
        order = s.load_order(connection, session["order_id"], user)
        s.require_leader(order, user)
        if session["leader_account_id"] != s.actor(user):
            raise HTTPException(403, "Чужой сбор")
        if session["status"] not in {"collecting", "awaiting_confirmation", "expired"}:
            raise HTTPException(409, "Подтвержденный сбор нельзя отменить")
        challenge = s.one(connection, f"SELECT * FROM {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} WHERE challenge_id=?",
                          (session.get("final_challenge_id"),))
        if challenge and challenge.get("verifier_confirmed_at") and s.api().parse_db_datetime(challenge["expires_at"]) > s.now():
            raise HTTPException(409, "Клиент уже подтвердил сбор")
        if challenge:
            s.query(connection, f"UPDATE {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} SET expires_at=? WHERE challenge_id=?",
                    (s.stamp(), challenge["challenge_id"]))
        s.query(connection, f"UPDATE {s.MEMBERS} SET status='expired' WHERE session_id=? AND status IN ('collected','awaiting_confirmation')",
                (session_id,))
        s.query(connection, f"UPDATE {s.SESSIONS} SET status='expired' WHERE session_id=?", (session_id,))
        s.audit(connection, "crew_collection_cancelled", user, order["id"], {"session_id": session_id})
    return {"success": True}


def set_leader(order_id, user, worker_id):
    s.require_enabled()
    with s.transaction() as connection:
        order = s.load_order(connection, order_id, user, owner=True)
        s.require_open(order)
        if order.get("source_instance") == s.api().CRM_SYNC_INSTANCE:
            raise HTTPException(409, "Старший этого заказа назначается в CRM")
        return assign_leader(connection, order, worker_id, user)


def assign_leader(connection, order, worker_id, user, *, force=False):
    if worker_id not in s.assigned(order):
        raise HTTPException(422, "Старший должен быть назначен на эту заявку")
    account = s.one(connection, f"SELECT role,is_active FROM {s.api().ACCOUNTS_TABLE_NAME} WHERE account_id=?", (worker_id,))
    if not account or account["role"] != "worker" or not account["is_active"]:
        raise HTTPException(422, "Нужен активный профиль исполнителя")
    if order.get("crew_leader_account_id") == worker_id and not force:
        return {"success": True}
    # Reassignment expires unconfirmed collections and keeps accepted history.
    old_sessions = s.query(connection, f"SELECT * FROM {s.SESSIONS} WHERE order_id=? AND status IN ('collecting','awaiting_confirmation')",
                           (str(order["id"]),))
    for previous in old_sessions:
        challenge = s.one(connection, f"SELECT * FROM {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} WHERE challenge_id=?",
                          (previous.get("final_challenge_id"),))
        if challenge and challenge.get("verifier_confirmed_at") and s.api().parse_db_datetime(challenge["expires_at"]) > s.now():
            raise HTTPException(409, "Сначала завершите подтвержденный клиентом сбор")
        if challenge:
            s.query(connection, f"UPDATE {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} SET expires_at=? WHERE challenge_id=?",
                    (s.stamp(), challenge["challenge_id"]))
        s.query(connection, f"UPDATE {s.MEMBERS} SET status='expired' WHERE session_id=? AND status IN ('collected','awaiting_confirmation')",
                (previous["session_id"],))
        s.query(connection, f"UPDATE {s.SESSIONS} SET status='expired' WHERE session_id=?", (previous["session_id"],))
    order["crew_leader_account_id"] = worker_id
    order["crew_roster_revision"] = int(order.get("crew_roster_revision") or 0)+1
    s.api().write_order_in_connection(connection, order)
    # In-flight lists of a former leader become unusable through fingerprint checks.
    s.audit(connection, "crew_leader_assigned", user, order["id"], {"worker_id": worker_id})
    return {"success": True}


def proof_view(connection, row, *, private=False):
    result = {k: s.stamp(row[k]) if row.get(k) is not None and k.endswith("_at") else row.get(k)
              for k in ("evidence_id","worker_account_id","action","status","collected_at","effective_at",
                        "geo_status","review_reason","reviewed_at")}
    result["worker_name"] = s.api()._worker_name_in_connection(connection, row["worker_account_id"])
    if private:
        result["worker_evidence"] = s.decode(row.get("worker_evidence"))
        result["scanner_evidence"] = s.decode(row.get("scanner_evidence"))
    return result


def session_view(connection, session, user):
    return {"session_id": session["session_id"], "action": session["action"], "status": session["status"],
            "expires_at": s.stamp(session["expires_at"]),
            "members": [proof_view(connection, row) for row in s.query(
                connection, f"SELECT * FROM {s.MEMBERS} WHERE session_id=? ORDER BY collected_at", (session["session_id"],))]}


def state(order_id, user):
    with s.transaction() as connection:
        order = s.load_order(connection, order_id, user)
        if not s.protected(order) and (not s.enabled() or user.get("role") != "logist"):
            return {"enabled": False}
        s.expire_unconfirmed(connection, str(order["id"]))
        role = user.get("role")
        is_leader = role == "worker" and s.actor(user) == s.leader(order)
        workers = s.assigned(order) if role != "worker" or is_leader else [s.actor(user)]
        roster = []
        for worker_id in workers:
            row = s.api()._read_attendance_in_connection(connection, str(order["id"]), worker_id) or {}
            roster.append({"worker_account_id": worker_id, "worker_name": s.api()._worker_name_in_connection(connection, worker_id),
                           "is_leader": worker_id == s.leader(order), "check_in_at": row.get("check_in_at"),
                           "check_out_at": row.get("check_out_at"), "duration_minutes": row.get("duration_minutes")})
        proofs = s.query(connection, f"""SELECT * FROM {s.MEMBERS}
            WHERE order_id=? AND status IN ('issued','collected','awaiting_confirmation','pending_review','rejected')
            ORDER BY issued_at""", (str(order["id"]),))
        visible = [p for p in proofs if role != "worker" or is_leader or p["worker_account_id"] == s.actor(user)]
        session = s.one(connection, f"""SELECT * FROM {s.SESSIONS} WHERE order_id=? AND leader_account_id=?
            AND status IN ('collecting','awaiting_confirmation') ORDER BY created_at DESC LIMIT 1""",
            (str(order["id"]), s.actor(user))) if is_leader else None
        return {"enabled": True, "setup_required": not s.protected(order), "paused": not s.enabled(), "role": role, "is_leader": is_leader,
                "mode": "solo" if len(s.assigned(order)) == 1 else "crew", "leader_account_id": s.leader(order),
                "leader_in_crm": order.get("source_instance") == s.api().CRM_SYNC_INSTANCE,
                "roster": roster, "proofs": [proof_view(connection, p, private=role=="logist") for p in visible] if role!="client" else [],
                "session": session_view(connection, session, user) if session else None}


def enable_order(order_id, user):
    s.require_enabled()
    with s.transaction() as connection:
        order = s.load_order(connection, order_id, user, owner=True)
        s.require_open(order)
        if s.protected(order):
            return {"success": True}
        workers = s.assigned(order)
        if not workers or s.leader(order) not in workers:
            raise HTTPException(409, "Сначала назначьте исполнителей и старшего")
        for worker_id in workers:
            if s.api()._read_attendance_in_connection(connection, str(order["id"]), worker_id):
                raise HTTPException(409, "Учет по старой схеме уже начат. Завершите эту смену по прежним правилам")
        active = s.one(connection, f"SELECT challenge_id FROM {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} WHERE order_id=? AND used_at IS NULL AND expires_at>? LIMIT 1",
                       (str(order["id"]), s.stamp()))
        if active:
            raise HTTPException(409, "Дождитесь завершения ранее выданного QR")
        if order.get("source_instance") == s.api().CRM_SYNC_INSTANCE:
            for worker_id in workers:
                if not s.one(connection, f"SELECT crm_worker_id FROM {s.LINKS} WHERE source_instance=? AND worker_account_id=?",
                             (s.api().CRM_SYNC_INSTANCE, worker_id)):
                    raise HTTPException(409, "Сначала свяжите профили всех рабочих в CRM")
        s.mark_policy(connection, order)
        s.audit(connection, "crew_attendance_enabled", user, order["id"], {"workers": len(workers)})
    return {"success": True}
