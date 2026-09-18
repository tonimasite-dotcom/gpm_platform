import argparse

from app import app_orders_api as api


def backfill_actor_codes_in_connection(connection) -> dict[str, int]:
    """Assign missing actor codes to existing accounts, oldest registration first.

    Idempotent: accounts that already have a code (`ensure_actor_code` is
    get-or-assign) are left untouched, so this is safe to re-run.
    """
    assigned = {"client": 0, "logist": 0}
    for role in ("client", "logist"):
        if api._is_sqlite_connection(connection):
            rows = connection.execute(
                f"""
                SELECT account_id FROM {api.ACCOUNTS_TABLE_NAME}
                WHERE role = ?
                ORDER BY created_at ASC, account_id ASC
                """,
                (role,),
            ).fetchall()
            account_ids = [row[0] for row in rows]
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT account_id FROM {api.ACCOUNTS_TABLE_NAME}
                    WHERE role = %s
                    ORDER BY created_at ASC, account_id ASC
                    """,
                    (role,),
                )
                account_ids = [row[0] for row in cursor.fetchall()]
        for account_id in account_ids:
            already_had_code = api.get_actor_code(connection, account_id) is not None
            api.ensure_actor_code(connection, account_id, role)
            if not already_had_code:
                assigned[role] += 1
    return assigned


def backfill_actor_codes() -> dict[str, int]:
    """One-time migration: assign L#/C# codes to every existing logist/client
    account that doesn't have one yet, ordered by registration date so the
    earliest-registered account becomes L1/C1. Run this once against an
    environment before/alongside the deploy that starts consuming actor
    codes for new order numbers.
    """
    api.init_db()
    with api.db_connection() as connection:
        if not api.is_postgres_enabled():
            connection.execute("BEGIN IMMEDIATE")
        result = backfill_actor_codes_in_connection(connection)
        if api.is_postgres_enabled():
            connection.commit()
    return result


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "One-time backfill: assign L#/C# actor codes to existing "
            "logist/client accounts, ordered by registration date. "
            "Safe to re-run."
        )
    ).parse_args()
    assigned = backfill_actor_codes()
    print(
        f"Assigned {assigned['client']} new client code(s), "
        f"{assigned['logist']} new logist code(s)."
    )


if __name__ == "__main__":
    main()
