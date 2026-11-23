"""Test-only worker export for TS. Never creates/authenticates GPM accounts."""
import asyncio
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from fastapi import Header, HTTPException, Request, Response
from app import registration_preview as reg

INSTANCE = "https://ts.workstaffcrm.ru"
PROTOCOL = "gpm-preview-workers-v1"
PROFILE_ID = re.compile(r"preview_[a-f0-9]{32}")
ERRORS = {"duplicate_crm_phone", "staff_role_collision", "deleted_crm_card",
          "crm_card_already_linked", "trusted_branch_required", "invalid_preview_profile",
          "temporary_unavailable", "source_not_ready"}


def api():
    from app import app_orders_api
    return app_orders_api


def enabled():
    return str(api().get_setting("GPM_REGISTRATION_PREVIEW_CRM_ENABLED", "false")).lower() == "true"


def require_mode(payload):
    if not enabled():
        raise HTTPException(503, "Test worker synchronization is disabled")
    if payload.get("source_instance") != INSTANCE:
        raise HTTPException(403, "Only TS is supported")


@contextmanager
def receipts():
    parent = reg.db_path().parent
    directory = parent / "crm-sync"
    if parent.is_symlink() or directory.is_symlink():
        raise RuntimeError("Unsafe preview synchronization storage")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    lock_path = directory / "sync.lock"
    if lock_path.is_symlink():
        raise RuntimeError("Unsafe synchronization lock")
    with lock_path.open("a+") as lock:
        lock_path.chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield directory
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def receipt_path(directory, profile_id):
    if not isinstance(profile_id, str) or PROFILE_ID.fullmatch(profile_id) is None:
        raise HTTPException(422, "Invalid test profile")
    path = directory / (profile_id + ".json")
    if path.is_symlink():
        raise RuntimeError("Unsafe synchronization receipt")
    return path


def read_receipt(directory, profile_id):
    path = receipt_path(directory, profile_id)
    return json.loads(path.read_text()) if path.exists() else {}


def save_receipt(directory, profile_id, value):
    path = receipt_path(directory, profile_id)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(directory))
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def profile_document(row):
    answers = json.loads(row["answers"])
    phone = reg.normalize_phone(answers["phone"], answers.get("phone_country", "RU"))
    if row["verified_phone"] != phone:
        raise HTTPException(409, "Test profile phone is not confirmed")
    selected = set(answers.get("city_ids") or [])
    districts = set(answers.get("district_ids") or [])
    selected.update(item["city_id"] for item in reg.LOCATIONS
                    if item["kind"] == "district" and item["id"] in districts)
    cities = sorted({item["name"] for item in reg.LOCATIONS
                     if item["kind"] == "city" and item["id"] in selected})
    document = {
        "profile_id": row["id"], "environment": "registration-preview",
        "verification_method": "test_code", "phone_verified": True,
        "phone": phone, "phone_country": answers.get("phone_country", "RU"),
        "surname": answers["last_name"], "first_name": answers["first_name"],
        "middle_name": answers.get("middle_name", ""), "birth_date": answers["birth_date"],
        "cities": cities, "created_at": row["created"],
    }
    document["revision"] = hashlib.sha256(json.dumps(
        document, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    return document


def load_profile(connection, profile_id):
    row = connection.execute("""SELECT p.*,s.verified_phone FROM preview_profiles p
        JOIN preview_sessions s ON s.id=p.session_id WHERE p.id=?""", (profile_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Test profile not found")
    return profile_document(row)


def export(payload):
    require_mode(payload)
    if set(payload) != {"operation", "source_instance", "since", "limit"}:
        raise HTTPException(422, "Invalid test synchronization request")
    since, limit = payload["since"], payload["limit"]
    if (isinstance(since, bool) or not isinstance(since, (int, float))
            or not math.isfinite(since) or since < 0 or since > reg.clock()+30):
        raise HTTPException(422, "Invalid test start time")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid test page size")
    result = []
    # The laboratory has an explicit 5000-session cap. Completed profiles are
    # immutable, and linked/retry receipts prevent head-of-queue starvation.
    with reg.PreviewStore().connection() as db, receipts() as directory:
        rows = db.execute("""SELECT p.*,s.verified_phone FROM preview_profiles p
            JOIN preview_sessions s ON s.id=p.session_id
            WHERE p.created>=? ORDER BY p.created,p.id""", (since,)).fetchall()
        for row in rows:
            previous = read_receipt(directory, row["id"])
            if previous.get("status") == "linked" or previous.get("next_attempt_at", 0) > reg.clock():
                continue
            result.append(profile_document(row))
            if len(result) == limit:
                break
    return {"protocol": PROTOCOL, "source_instance": INSTANCE,
            "environment": "registration-preview", "profiles": result}


def acknowledge(payload):
    require_mode(payload)
    if set(payload) != {"operation", "source_instance", "profile_id", "revision",
                        "status", "crm_worker_id", "error_code"}:
        raise HTTPException(422, "Invalid test receipt")
    profile_id, status = payload["profile_id"], payload["status"]
    if status not in {"linked", "conflict", "deferred"}:
        raise HTTPException(422, "Invalid test synchronization status")
    crm_id = payload["crm_worker_id"]
    error = payload["error_code"]
    if status == "linked":
        if not isinstance(crm_id, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", crm_id) or error is not None:
            raise HTTPException(422, "Invalid CRM worker identity")
    elif crm_id is not None or error not in ERRORS:
        raise HTTPException(422, "Invalid synchronization error")
    with reg.PreviewStore().connection() as db, receipts() as directory:
        receipt_path(directory, profile_id)
        document = load_profile(db, profile_id)
        if document["revision"] != payload["revision"]:
            raise HTTPException(409, "Test profile revision changed")
        previous = read_receipt(directory, profile_id)
        if previous.get("status") == "linked":
            if status == "linked" and previous.get("crm_worker_id") == crm_id:
                return {"success": True, "already_linked": True}
            raise HTTPException(409, "A linked test profile cannot be rebound")
        if status == "linked":
            for path in directory.glob("preview_*.json"):
                other = json.loads(path.read_text())
                if other.get("status") == "linked" and other.get("crm_worker_id") == crm_id:
                    raise HTTPException(409, "CRM worker already has a different test profile")
        save_receipt(directory, profile_id, {
            "protocol": PROTOCOL, "profile_id": profile_id, "revision": document["revision"],
            "status": status, "crm_worker_id": crm_id, "error_code": error,
            "updated_at": reg.clock(), "next_attempt_at": reg.clock()+300,
        })
    return {"success": True}


def register_routes(app):
    @app.post("/app-api/integration/registration-preview/workers")
    async def test_workers(request: Request, response: Response,
                           x_gpm_app_token: str | None = Header(default=None)):
        api().check_token(x_gpm_app_token)
        response.headers["Cache-Control"] = "no-store"
        payload = await api().bounded_json_payload(request, max_bytes=8192)
        operation = payload.get("operation")
        if operation == "list":
            return await asyncio.to_thread(export, payload)
        if operation == "ack":
            return await asyncio.to_thread(acknowledge, payload)
        raise HTTPException(422, "Unknown test synchronization operation")
