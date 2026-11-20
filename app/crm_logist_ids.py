"""Company-only routing IDs. Never changes login, phones or order numbering."""
import re
import sqlite3
from typing import Any

MEMBERS = "gpm_app_company_logists"
INVITES = "gpm_app_company_logist_invitations"
_LOCK = 0x47504D43524D


def _sqlite(connection: Any) -> bool:
    return isinstance(connection, sqlite3.Connection)


def _run(connection, sql, params=(), *, one=False):
    if _sqlite(connection):
        cursor = connection.execute(sql.replace("%s", "?"), params)
        return cursor.fetchone() if one else None
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone() if one else None


def ensure_schema(connection):
    moment = "TEXT" if _sqlite(connection) else "TIMESTAMPTZ"
    _run(connection, f"""CREATE TABLE IF NOT EXISTS {MEMBERS} (
        account_id TEXT PRIMARY KEY REFERENCES gpm_app_accounts(account_id),
        crm_id INTEGER NOT NULL UNIQUE CHECK (crm_id > 0),
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        assigned_by TEXT NOT NULL,
        assigned_at {moment} NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at {moment} NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    _run(connection, f"""CREATE TABLE IF NOT EXISTS {INVITES} (
        invitation_id TEXT PRIMARY KEY REFERENCES gpm_app_account_invitations(invitation_id),
        created_at {moment} NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")


def parse_id(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Укажите ID логиста в приложении, например #1")
    text = str(value).strip()
    if not re.fullmatch(r"#?[1-9][0-9]{0,8}", text):
        raise ValueError("Укажите ID логиста в приложении, например #1")
    return int(text.lstrip("#"))


def mark_invitation(connection, invitation_id):
    _run(connection, f"INSERT INTO {INVITES}(invitation_id) VALUES (%s)", (invitation_id,))


def company_invitation(connection, invitation_id) -> bool:
    return _run(connection, f"SELECT invitation_id FROM {INVITES} WHERE invitation_id=%s",
                (invitation_id,), one=True) is not None


def for_account(connection, account_id):
    row = _run(connection, f"""SELECT c.crm_id FROM {MEMBERS} c
        JOIN gpm_app_accounts a ON a.account_id=c.account_id
        WHERE c.account_id=%s AND c.enabled=TRUE
          AND a.role='logist' AND a.is_active=TRUE""", (account_id,), one=True)
    return int(row[0]) if row is not None else None


def resolve(connection, value):
    code = parse_id(value)
    row = _run(connection, f"""SELECT c.account_id FROM {MEMBERS} c
        JOIN gpm_app_accounts a ON a.account_id=c.account_id
        WHERE c.crm_id=%s AND c.enabled=TRUE
          AND a.role='logist' AND a.is_active=TRUE""", (code,), one=True)
    if row is None:
        raise ValueError("ID не найден среди активных логистов Джи Пи Эм")
    return {"crm_logist_id": code, "account_id": str(row[0])}


def grant(connection, account_id, *, assigned_by):
    """Trusted provisioning only, inside the caller's transaction.

    SQLite callers use BEGIN IMMEDIATE. PostgreSQL serializes allocation with
    a transaction lock. Retained disabled rows prevent ID reuse and renumbering.
    """
    if not isinstance(assigned_by, str) or not assigned_by.strip():
        raise ValueError("Provisioning actor is required")
    if not _sqlite(connection):
        _run(connection, "SELECT pg_advisory_xact_lock(%s)", (_LOCK,))
    suffix = "" if _sqlite(connection) else " FOR UPDATE"
    account = _run(connection, "SELECT role,is_active FROM gpm_app_accounts WHERE account_id=%s" + suffix,
                   (account_id,), one=True)
    if account is None or account[0] != "logist" or not account[1]:
        raise ValueError("Only an active logist can be enrolled as a GPM employee")
    existing = _run(connection, f"SELECT crm_id,enabled FROM {MEMBERS} WHERE account_id=%s",
                    (account_id,), one=True)
    if existing is not None:
        if not existing[1]:
            _run(connection, f"UPDATE {MEMBERS} SET enabled=TRUE,updated_at=CURRENT_TIMESTAMP WHERE account_id=%s",
                 (account_id,))
        return {"crm_logist_id": int(existing[0]), "changed": not bool(existing[1])}
    row = _run(connection, f"SELECT COALESCE(MAX(crm_id),0)+1 FROM {MEMBERS}", one=True)
    code = int(row[0])
    if code > 999999999:
        raise ValueError("Company routing ID capacity reached")
    _run(connection, f"INSERT INTO {MEMBERS}(account_id,crm_id,assigned_by) VALUES (%s,%s,%s)",
         (account_id, code, assigned_by.strip()[:120]))
    return {"crm_logist_id": code, "changed": True}


def revoke(connection, account_id):
    row = _run(connection, f"SELECT crm_id,enabled FROM {MEMBERS} WHERE account_id=%s",
               (account_id,), one=True)
    if row is None:
        raise ValueError("Company logist is not enrolled")
    _run(connection, f"UPDATE {MEMBERS} SET enabled=FALSE,updated_at=CURRENT_TIMESTAMP WHERE account_id=%s",
         (account_id,))
    return {"crm_logist_id": int(row[0]), "changed": bool(row[1])}
