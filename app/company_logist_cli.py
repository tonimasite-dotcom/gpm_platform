"""Trusted company-logist provisioning; public registration cannot call it."""
import argparse
import json
import os
from pathlib import Path

from app import app_orders_api as api
from app import crm_logist_ids as ids


def protected_output(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or path.resolve().is_relative_to(api.BASE_DIR.parent.resolve()):
        raise ValueError("Invitation output must be an absolute private path outside the repository")
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("grant", "revoke"):
        command = commands.add_parser(name)
        command.add_argument("--account-id", required=True)
        command.add_argument("--by", required=True)
        command.add_argument("--apply", action="store_true")
    invite = commands.add_parser("invite")
    invite.add_argument("--username", required=True)
    invite.add_argument("--by", required=True)
    invite.add_argument("--output", required=True)
    args = parser.parse_args()
    api.validate_runtime_configuration()
    if args.command == "invite":
        descriptor = protected_output(args.output)
        try:
            invitation = api.create_account_invitation(args.username, "logist", created_by=args.by, gpm_company_logist=True)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"warning": "Secret invitation; do not put in Git or chat", "invitation": invitation}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        print("Company invitation saved in the protected output file; CRM ID will be assigned on registration.")
        return
    with api.db_connection() as connection:
        if api._is_sqlite_connection(connection):
            connection.execute("BEGIN IMMEDIATE")
        row = ids._run(connection, "SELECT role,is_active FROM gpm_app_accounts WHERE account_id=%s", (args.account_id,), one=True)
        if row is None or row[0] != "logist":
            raise ValueError("An existing logist account is required")
        if args.command == "grant" and not row[1]:
            raise ValueError("An active logist account is required for enrollment")
        if not args.apply:
            print("Plan verified; no membership or ID changed. Use --apply to enroll or revoke.")
            return
        result = ids.grant(connection, args.account_id, assigned_by=args.by) if args.command == "grant" else ids.revoke(connection, args.account_id)
        if result["changed"]:
            api.record_audit_event_in_connection(connection,
                event_type="company_logist_" + args.command, outcome="success", actor_username=args.by,
                target_type="account", target_id=args.account_id,
                details={"crm_logist_id": result["crm_logist_id"]})
        if not api._is_sqlite_connection(connection):
            connection.commit()
    print("CRM ID: #" + str(result["crm_logist_id"]))


if __name__ == "__main__":
    main()
