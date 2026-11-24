"""Trusted one-off onboarding. Private payload and credentials never enter Git/logs."""
import base64
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import traceback
from pathlib import Path
from uuid import uuid4

from app import app_orders_api as api, crm_logist_ids as ids
from app.phone_numbers import normalize_russian_phone, format_russian_phone


def run(connection, sql, params=(), one=False):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone() if one else (cursor.fetchall() if cursor.description else None)


def validate(request):
    assert request["owner_approved"] is True
    assert [p["expected_id"] for p in request["profiles"]] == [4, 5]
    for p in request["profiles"]:
        api.validate_invitation_username(p["username"])
        normalize_russian_phone(p["phone"])
        assert isinstance(p["display_name"], str) and 0 < len(p["display_name"]) < 200
        assert isinstance(p["email"], str) and "@" in p["email"] and len(p["email"]) < 254
    assert len({p["username"].casefold() for p in request["profiles"]}) == 2
    assert len({normalize_russian_phone(p["phone"]) for p in request["profiles"]}) == 2


def account_rows(connection):
    return run(connection, f"""SELECT a.account_id,a.username,a.role,a.is_active,p.data
        FROM {api.ACCOUNTS_TABLE_NAME} a LEFT JOIN {api.PROFILES_TABLE_NAME} p USING(account_id)""")


def plan(connection, profiles):
    rows = account_rows(connection)
    result = []
    for p in profiles:
        found = []
        for account_id, username, role, active, data in rows:
            data = api.parse_json_value(data) if hasattr(api, "parse_json_value") else data
            if isinstance(data, str):
                data = json.loads(data)
            data = data or {}
            try:
                same_phone = normalize_russian_phone(data.get("phone", "")) == normalize_russian_phone(p["phone"])
            except ValueError:
                same_phone = False
            same_email = bool(data.get("email")) and data["email"].strip().casefold() == p["email"].casefold()
            same_login = api.normalize_username(username) == api.normalize_username(p["username"])
            if same_phone or same_email or same_login:
                found.append((account_id, username, role, active, data, same_phone, same_email))
        assert len(found) <= 1, json.dumps({"reason":"ambiguous_identity","slot":p["expected_id"],
            "matches":[{"role":r[2],"active":bool(r[3]),"phone_match":r[5],"email_match":r[6],
                        "login_match":api.normalize_username(r[1])==api.normalize_username(p["username"]),
                        "crm_id":ids.for_account(connection,r[0])} for r in found]})
        existing = found[0] if found else None
        if existing:
            assert existing[2] == "logist" and existing[3], "Existing role/activation conflict"
            assert existing[5] or existing[6], "Existing username identity conflict"
            for field in ["email", "phone"]:
                old = existing[4].get(field)
                if old:
                    assert (normalize_russian_phone(old) == normalize_russian_phone(p[field]) if field == "phone" else old.casefold() == p[field].casefold()), "Existing contact conflict"
        occupant = run(connection, f"SELECT account_id FROM {ids.MEMBERS} WHERE crm_id=%s", (p["expected_id"],), one=True)
        assert not occupant or (existing and occupant[0] == existing[0]), "Requested ID occupied"
        if existing:
            current = run(connection, f"SELECT crm_id,enabled FROM {ids.MEMBERS} WHERE account_id=%s", (existing[0],), one=True)
            assert current is None or (current[0] == p["expected_id"] and current[1]), "Existing routing ID conflict"
        result.append({"profile": p, "existing": existing})
    existing_ids = [r["existing"][0] for r in result if r["existing"]]
    assert len(existing_ids) == len(set(existing_ids)), "Same account matched twice"
    return result


def public_key(request):
    def der(tag, data):
        n = len(data)
        length = bytes([n]) if n < 128 else bytes([128 + ((n.bit_length()+7)//8)]) + n.to_bytes((n.bit_length()+7)//8, "big")
        return bytes([tag])+length+data
    def integer(data):
        return der(2, (b"\0" if data[0] & 128 else b"")+data)
    modulus = base64.b64decode(request["delivery_key"]["modulus"], validate=True)
    exponent = base64.b64decode(request["delivery_key"]["exponent"], validate=True)
    assert len(modulus) >= 256 and exponent == b"\x01\x00\x01"
    rsa = der(48, integer(modulus)+integer(exponent))
    return der(48, bytes.fromhex("300d06092a864886f70d0101010500")+der(3, b"\0"+rsa))


def seal(value, keyfile):
    result = subprocess.run(["openssl","pkeyutl","-encrypt","-pubin","-keyform","DER","-inkey",str(keyfile),
        "-pkeyopt","rsa_padding_mode:oaep","-pkeyopt","rsa_oaep_md:sha1"], input=value.encode(), capture_output=True, check=True)
    return base64.b64encode(result.stdout).decode()


def fingerprint(connection, table, excluded):
    rows = run(connection, f"SELECT row_to_json(t)::text FROM {table} t WHERE NOT (account_id=ANY(%s)) ORDER BY account_id", (excluded,))
    return hashlib.sha256(json.dumps(rows, separators=(",",":")).encode()).hexdigest()


def execute(request, operation, run_id):
    assert operation in {"inspect", "rehearse", "apply"}
    root = Path("/opt/gpm/gpm_platform")
    assert Path.cwd() == root and root.resolve() == root
    assert subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip() == request["approved_runtime_commit"]
    api.validate_runtime_configuration()
    assert api.is_postgres_enabled()
    validate(request)
    report = Path("/opt/gpm/backups")/("named-logists-"+run_id+".json")
    assert not report.exists()
    os.umask(0o077)
    summary = {"ok": False, "operation": operation}
    try:
        with tempfile.TemporaryDirectory(prefix="gpm-public-delivery-") as temporary:
            keyfile = Path(temporary)/"public.der"
            keyfile.write_bytes(public_key(request))
            # Exercise delivery encryption before any DB mutation.
            seal("delivery-check", keyfile)
            with api.db_connection() as connection:
                run(connection, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                if operation == "inspect":
                    run(connection, "SET TRANSACTION READ ONLY")
                else:
                    run(connection, "SELECT pg_advisory_xact_lock(%s)", (ids._LOCK,))
                prepared = plan(connection, request["profiles"])
                targets = [row["existing"][0] if row["existing"] else str(uuid4()) for row in prepared]
                tables = [api.ACCOUNTS_TABLE_NAME, api.PROFILES_TABLE_NAME, api.ACTOR_CODES_TABLE_NAME, ids.MEMBERS]
                before = {t: fingerprint(connection,t,targets) for t in tables}
                deliveries = []
                for entry, account_id in zip(prepared, targets):
                    p = entry["profile"]
                    if operation == "inspect":
                        deliveries.append({"crm_id":p["expected_id"],"account": "existing" if entry["existing"] else "new"})
                        continue
                    password = None
                    if entry["existing"]:
                        run(connection, f"SELECT account_id FROM {api.ACCOUNTS_TABLE_NAME} WHERE account_id=%s FOR UPDATE", (account_id,))
                        username = entry["existing"][1]
                    else:
                        username = p["username"]
                        password = secrets.token_urlsafe(24)
                        api.validate_new_password(password, username)
                        digest = api.hash_password(password)
                        assert api.verify_password(password, digest)
                        run(connection, f"""INSERT INTO {api.ACCOUNTS_TABLE_NAME}
                            (account_id,username,username_normalized,password_hash,role,created_at,updated_at)
                            VALUES (%s,%s,%s,%s,'logist',%s,%s)""",
                            (account_id,username,api.normalize_username(username),digest,api.serialize_datetime(api.utc_now()),api.serialize_datetime(api.utc_now())))
                        api.ensure_actor_code(connection,account_id,"logist")
                        api._write_profile_in_connection(connection,account_id,{"display_name":p["display_name"],"phone":format_russian_phone(p["phone"]),"email":p["email"]})
                    current = run(connection,f"SELECT crm_id FROM {ids.MEMBERS} WHERE account_id=%s",(account_id,),one=True)
                    if current is None:
                        run(connection,f"INSERT INTO {ids.MEMBERS}(account_id,crm_id,assigned_by) VALUES (%s,%s,%s)",
                            (account_id,p["expected_id"],"owner-approved-named-logists"))
                    assert ids.for_account(connection,account_id) == p["expected_id"]
                    assert ids.resolve(connection,p["expected_id"])["account_id"] == account_id
                    api.record_audit_event_in_connection(connection,event_type="owner_logist_provision",outcome="success",
                        actor_username="owner-approved-provision",target_type="account",target_id=account_id,
                        details={"crm_logist_id":p["expected_id"],"account_created":password is not None})
                    deliveries.append({"crm_id":p["expected_id"],"created":password is not None,
                        "username_ciphertext":seal(username,keyfile),
                        "password_ciphertext":seal(password,keyfile) if password else None})
                assert {t:fingerprint(connection,t,targets) for t in tables} == before
                if operation == "apply":
                    connection.commit()
                else:
                    connection.rollback()
            summary = {"ok":True,"operation":operation,"ids":[4,5],"existing_accounts_preserved":True,
                "crm_touched":False,"rows":deliveries,"committed":operation=="apply"}
            report.write_text(json.dumps({"summary":summary,"request":request},ensure_ascii=False,indent=2))
            report.chmod(0o600)
        print(json.dumps(summary))
    except BaseException as error:
        report.write_text(json.dumps({"ok":False,"operation":operation,"error_type":type(error).__name__,"private_traceback":traceback.format_exc()}))
        report.chmod(0o600)
        print(json.dumps({"ok":False,"operation":operation,"error_type":type(error).__name__,
            "reason":str(error) if isinstance(error,AssertionError) else "",
            "failed_line":traceback.extract_tb(error.__traceback__)[-1].lineno}))
        raise SystemExit(1)
