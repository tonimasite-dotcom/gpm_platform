import argparse
import json
import os
from pathlib import Path

from app import app_orders_api as api


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create one-time GPM account invitations without logging tokens."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_test_user = subparsers.add_parser(
        "create-test-user",
        help="Create client, worker and logist invitations for one tester.",
    )
    create_test_user.add_argument(
        "--prefix",
        required=True,
        help="Username prefix; role suffixes are added automatically.",
    )
    create_test_user.add_argument("--created-by", required=True)
    create_test_user.add_argument("--output", required=True, type=Path)
    return parser


def create_test_user_invitations(
    *, prefix: str, created_by: str, output: Path
) -> list[dict[str, str]]:
    prefix = api.validate_invitation_username(prefix)
    usernames = {
        role: api.validate_invitation_username(f"{prefix}-{role}")
        for role in ("client", "worker", "logist")
    }
    if not output.is_absolute():
        raise ValueError("output must be an absolute path outside the repository")
    resolved_output = output.expanduser().resolve()
    repository_root = api.BASE_DIR.parent.resolve()
    if resolved_output.is_relative_to(repository_root):
        raise ValueError("invitation output must not be stored inside the repository")
    if resolved_output.exists():
        raise FileExistsError("output file already exists")
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    api.validate_runtime_configuration()
    api.init_db()
    invitations = [
        api.create_account_invitation(
            usernames[role],
            role,
            created_by=created_by,
        )
        for role in ("client", "worker", "logist")
    ]
    payload = {
        "warning": "Secret one-time invitations. Do not put this file in Git or chat.",
        "invitations": invitations,
    }
    descriptor = os.open(
        resolved_output,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
    try:
        os.chmod(resolved_output, 0o600)
    except OSError:
        pass
    return [
        {"username": item["username"], "role": item["role"]}
        for item in invitations
    ]


def main() -> None:
    arguments = build_parser().parse_args()
    if arguments.command != "create-test-user":
        raise SystemExit(2)
    accounts = create_test_user_invitations(
        prefix=arguments.prefix,
        created_by=arguments.created_by,
        output=arguments.output,
    )
    print(f"Created {len(accounts)} invitations in a protected output file.")
    for account in accounts:
        print(f"{account['role']}: {account['username']}")


if __name__ == "__main__":
    main()
