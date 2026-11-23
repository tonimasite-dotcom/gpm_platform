"""Explicit rollback preparation: expire unconfirmed crew QR, keep accepted data."""
import json

from app import crew_storage as s


def quiesce():
    if s.enabled():
        raise RuntimeError("Disable new crew collections before preparing rollback")
    expired = 0
    with s.transaction() as connection:
        orders = s.query(connection, f"SELECT DISTINCT order_id FROM {s.SESSIONS} WHERE client_confirmed_at IS NULL AND status IN ('collecting','awaiting_confirmation') UNION SELECT DISTINCT order_id FROM {s.MEMBERS} WHERE status='issued'")
        for item in sorted(orders, key=lambda row: row["order_id"]):
            order = s.api().read_order_in_connection(connection, item["order_id"], for_update=True)
            if order is None:
                continue
            sessions = s.query(connection, f"SELECT * FROM {s.SESSIONS} WHERE order_id=? AND client_confirmed_at IS NULL AND status IN ('collecting','awaiting_confirmation')",
                               (item["order_id"],))
            for session in sessions:
                if session["final_challenge_id"]:
                    s.query(connection, f"UPDATE {s.api().ATTENDANCE_CHALLENGES_TABLE_NAME} SET expires_at=? WHERE challenge_id=? AND used_at IS NULL",
                            (s.stamp(), session["final_challenge_id"]))
                s.query(connection, f"UPDATE {s.MEMBERS} SET status='expired' WHERE session_id=? AND status IN ('collected','awaiting_confirmation')",
                        (session["session_id"],))
                s.query(connection, f"UPDATE {s.SESSIONS} SET status='expired' WHERE session_id=? AND client_confirmed_at IS NULL",
                        (session["session_id"],))
                expired += 1
            s.query(connection, f"UPDATE {s.MEMBERS} SET status='expired' WHERE order_id=? AND status='issued'",
                    (item["order_id"],))
            s.audit(connection, "crew_rollback_prepared", {"role": "system"}, item["order_id"],
                    {"expired_unconfirmed_sessions": len(sessions)})
    return {"expired_sessions": expired, "confirmed_and_pending_review_preserved": True}


if __name__ == "__main__":
    print(json.dumps(quiesce()))
