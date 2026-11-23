"""Validate the proposed additive schema in a disposable Actions database only."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse
import unittest
import uuid

try:
    import psycopg
    from psycopg import sql
except ImportError:
    psycopg = None

DSN = os.getenv("GPM_CREW_SCHEMA_TEST_URL", "")
IS_DISPOSABLE = os.getenv("GITHUB_ACTIONS") == "true" and bool(DSN)


@unittest.skipUnless(IS_DISPOSABLE and psycopg, "isolated Actions proposal database required")
class ProposedCrewSchemaTests(unittest.TestCase):
    def setUp(self):
        target = urlparse(DSN)
        self.assertIn(target.hostname, {"127.0.0.1", "localhost"})
        self.assertEqual(target.path, "/crew_proposal")
        self.connection = psycopg.connect(DSN, autocommit=True)
        self.schema = "crew_proposal_" + uuid.uuid4().hex
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        self.connection.execute("CREATE TABLE gpm_app_accounts(account_id TEXT PRIMARY KEY)")
        self.connection.execute(
            "INSERT INTO gpm_app_accounts VALUES ('worker'), ('other'), ('leader'), ('logist')"
        )
        self.connection.execute(
            "CREATE TABLE gpm_app_attendance_challenges(challenge_id TEXT PRIMARY KEY)"
        )
        self.connection.execute(
            "CREATE TABLE gpm_app_order_attendance(attendance_id TEXT PRIMARY KEY, data JSONB)"
        )
        self.connection.execute(
            """INSERT INTO gpm_app_order_attendance VALUES
               ('legacy', '{"check_in_at":"2026-11-20T08:00:00Z","worker":"worker"}')"""
        )
        proposal = Path(__file__).with_name("PROPOSED_SCHEMA.sql").read_text()
        self.connection.execute(proposal)

    def tearDown(self):
        # The entire database is a disposable job service; never drop live tables.
        self.connection.close()

    def issue(self, evidence="proof", token="token", worker="worker"):
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.connection.execute(
            """INSERT INTO gpm_app_crew_attendance_members(
                evidence_id,order_id,worker_account_id,action,token_hash,
                token_expires_at,issued_at,geo_status,status)
               VALUES (%s,'synthetic-order',%s,'check_in',%s,
                       NOW()+INTERVAL '60 seconds',NOW(),'valid','issued')""",
            (evidence, worker, digest),
        )

    def session(self, session="batch"):
        self.connection.execute(
            """INSERT INTO gpm_app_crew_attendance_sessions(
                session_id,order_id,leader_account_id,attendance_mode,action,
                roster_revision,status,expires_at)
               VALUES (%s,'synthetic-order','leader','crew','check_in',
                       1,'collecting',NOW()+INTERVAL '15 minutes')""",
            (session,),
        )

    def test_existing_attendance_is_preserved(self):
        value = self.connection.execute(
            "SELECT data FROM gpm_app_order_attendance WHERE attendance_id='legacy'"
        ).fetchone()[0]
        self.assertEqual(value, {"check_in_at": "2026-11-20T08:00:00Z", "worker": "worker"})
        names = {r[0] for r in self.connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
            (self.schema,),
        )}
        self.assertTrue({
            "gpm_app_crm_worker_links",
            "gpm_app_crew_attendance_sessions",
            "gpm_app_crew_attendance_members",
        }.issubset(names))

    def test_worker_links_are_one_to_one_for_a_source(self):
        self.connection.execute(
            """INSERT INTO gpm_app_crm_worker_links(
               source_instance,crm_worker_id,worker_account_id,linked_by)
               VALUES ('synthetic-ts','crm-worker','worker','logist')"""
        )
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.connection.execute(
                    """INSERT INTO gpm_app_crm_worker_links(
                       source_instance,crm_worker_id,worker_account_id,linked_by)
                       VALUES ('synthetic-ts','crm-worker','other','logist')"""
                )
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.connection.execute(
                    """INSERT INTO gpm_app_crm_worker_links(
                       source_instance,crm_worker_id,worker_account_id,linked_by)
                       VALUES ('synthetic-ts','other-crm-worker','worker','logist')"""
                )

    def test_a_presence_token_cannot_be_reused(self):
        self.issue()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.issue(evidence="other-proof", worker="other")

    def test_only_one_active_action_per_worker(self):
        self.issue()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.issue(evidence="new-proof", token="new-token")
        self.connection.execute(
            "UPDATE gpm_app_crew_attendance_members SET status='expired' WHERE evidence_id='proof'"
        )
        self.issue(evidence="replacement", token="replacement-token")

    def test_collecting_requires_session_and_server_time(self):
        self.issue()
        self.session()
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                self.connection.execute(
                    """UPDATE gpm_app_crew_attendance_members
                       SET status='collected',session_id='batch' WHERE evidence_id='proof'"""
                )
        self.connection.execute(
            """UPDATE gpm_app_crew_attendance_members
               SET status='collected',session_id='batch',collected_at=NOW(),
                   scanned_by='leader' WHERE evidence_id='proof'"""
        )

    def test_confirmed_batch_requires_client_confirmation(self):
        self.session()
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                self.connection.execute(
                    "UPDATE gpm_app_crew_attendance_sessions SET status='confirmed'"
                )
        self.connection.execute(
            """UPDATE gpm_app_crew_attendance_sessions
               SET status='confirmed',client_confirmed_at=NOW(),confirmed_by='synthetic-client'"""
        )

    def test_manual_review_requires_reason_and_reviewer_timestamp(self):
        self.issue()
        self.session()
        self.connection.execute(
            """UPDATE gpm_app_crew_attendance_members
               SET status='pending_review',session_id='batch',collected_at=NOW(),
                   scanned_by='leader',geo_status='unavailable'"""
        )
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                self.connection.execute(
                    """UPDATE gpm_app_crew_attendance_members
                       SET reviewed_by='logist',reviewed_at=NOW(),status='confirmed',
                           effective_at=collected_at"""
                )
        self.connection.execute(
            """UPDATE gpm_app_crew_attendance_members
               SET reviewed_by='logist',reviewed_at=NOW(),status='confirmed',
                   effective_at=collected_at,review_reason='Synthetic review evidence'"""
        )

    def test_qr_expiration_must_follow_issue_time(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                self.connection.execute(
                    """INSERT INTO gpm_app_crew_attendance_members(
                       evidence_id,order_id,worker_account_id,action,token_hash,
                       issued_at,token_expires_at,geo_status,status)
                       VALUES ('bad','synthetic-order','worker','check_in','hash',
                               NOW(),NOW()-INTERVAL '1 second','valid','issued')"""
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
