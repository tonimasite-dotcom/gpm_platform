"""Synthetic headless TS tests; no CRM/customer records or external network."""
import json
import os
import unittest
from unittest.mock import patch
from tests import test_crew_attendance as fixture
from app import app_orders_api as api, crew_storage as s, crew_flow as flow
from app import crew_leader_sync as bridge


class HeadlessLeaderTests(unittest.TestCase):
    postgres = False
    db = fixture.CrewAttendanceTests.db
    tearDown = fixture.CrewAttendanceTests.tearDown
    geo = fixture.CrewAttendanceTests.geo
    batch = fixture.CrewAttendanceTests.batch
    error = fixture.CrewAttendanceTests.error

    def setUp(self):
        fixture.CrewAttendanceTests.setUp(self)
        with self.db() as c:
            order = api.read_order_in_connection(c, self.order["id"])
            order.update(source="crm", source_system="workstaff", source_instance=api.CRM_SYNC_INSTANCE)
            order.pop("attendance_policy", None)
            order.pop("crew_leader_account_id", None)
            api.write_order_in_connection(c, order)
            api.crm_logist_ids.grant(c, "logist", assigned_by="synthetic")
            for worker, phone in [("leader", "+7 (999) 000-00-01"), ("member", "89990000002"), ("late", "79990000003")]:
                s.query(c, f"INSERT INTO {api.PROFILES_TABLE_NAME}(account_id,data) VALUES (?,?)",
                        (worker, json.dumps({"phone": phone})))
        self.payload = {"operation":"leader", "source_instance":api.CRM_SYNC_INSTANCE,
                        "sender_crm_id":"#1", "leader":{"crm_worker_id":"101","phone":"89990000001"}}

    def sync(self, **changes):
        return bridge.sync(self.order["id"], {**self.payload, **changes})

    def test_ordinary_brigadier_auto_enrolls_without_linking_or_assigning(self):
        before = api.get_order(self.order["id"])
        self.assertTrue(self.sync()["ready"])
        after = api.get_order(self.order["id"])
        self.assertEqual(after["crew_leader_account_id"], "leader")
        self.assertTrue(s.protected(after))
        for key in ["assigned_worker_ids","status","hours","min_time","price_per_hour"]:
            self.assertEqual(after[key],before[key])
        with self.db() as c:
            self.assertFalse(s.query(c,f"SELECT * FROM {s.LINKS}"))
            self.assertFalse(s.query(c,f"SELECT * FROM {api.ATTENDANCE_TABLE_NAME}"))
        self.assertFalse(flow.state(self.order["id"],self.logist)["setup_required"])

    def test_exact_phone_formats_match_without_modifying_profiles(self):
        for phone in ["79990000001","+7 999 000 00 01","+7 (999) 000-00-01","9990000001"]:
            self.assertTrue(self.sync(leader={"crm_worker_id":"101","phone":phone})["ready"])
        with self.db() as c:
            self.assertEqual(s.decode(s.one(c,f"SELECT data FROM {api.PROFILES_TABLE_NAME} WHERE account_id=?",("leader",))["data"])["phone"],"+7 (999) 000-00-01")

    def test_duplicate_and_short_phone_do_not_choose_a_worker(self):
        self.assertFalse(self.sync(leader={"crm_worker_id":"101","phone":"0000001"})["ready"])
        with self.db() as c:
            s.query(c,f"UPDATE {api.PROFILES_TABLE_NAME} SET data=? WHERE account_id=?",
                    (json.dumps({"phone":"79990000001"}),"member"))
        self.assertFalse(self.sync()["ready"])
        self.error(409,api.create_attendance_challenge,self.order["id"],self.member,public_api_url="https://example.test")
        self.assertTrue(flow.state(self.order["id"],self.member)["paused"])

    def test_unassigned_or_inactive_brigadier_does_not_gain_access(self):
        self.assertFalse(self.sync(leader={"crm_worker_id":"103","phone":"79990000003"})["ready"])
        with self.db() as c:
            s.query(c,f"UPDATE {api.ACCOUNTS_TABLE_NAME} SET is_active=FALSE WHERE account_id=?",("leader",))
        self.assertFalse(self.sync()["ready"])
        self.assertEqual(api.get_order(self.order["id"])["assigned_worker_ids"],["leader","member"])

    def test_other_source_and_other_owner_are_rejected(self):
        self.error(403,bridge.sync,self.order["id"],{**self.payload,"source_instance":"https://main.invalid"})
        self.error(403,bridge.sync,self.order["id"],{**self.payload,"sender_crm_id":"#2"})
        self.error(422,bridge.sync,self.order["id"],{**self.payload,"worker_account_id":"leader"})

    def test_existing_incompatible_identity_is_never_relinked(self):
        with self.db() as c:
            s.query(c,f"INSERT INTO {s.LINKS}(source_instance,crm_worker_id,worker_account_id,linked_by,linked_at) VALUES (?,?,?,?,?)",
                    (api.CRM_SYNC_INSTANCE,"101","member","logist",s.stamp()))
        self.assertFalse(self.sync()["ready"])
        with self.db() as c:
            self.assertEqual(s.one(c,f"SELECT worker_account_id FROM {s.LINKS}")["worker_account_id"],"member")

    def test_repeated_sync_keeps_collected_qr_valid_and_does_not_write_again(self):
        self.sync()
        _,_,token=self.batch()
        self.sync()
        result=api.confirm_attendance_by_client(self.client,token=token)
        self.assertTrue(result["crew"])
        self.assertEqual(len(result["rows"]),2)

    def test_new_brigadier_invalidates_unconfirmed_list_and_preserves_accepted_times(self):
        self.sync()
        _,_,token=self.batch()
        self.sync(leader={"crm_worker_id":"102","phone":"79990000002"})
        with self.assertRaises(fixture.HTTPException):
            api.confirm_attendance_by_client(self.client,token=token)
        self.assertEqual(api.get_order(self.order["id"])["crew_leader_account_id"],"member")
        self.error(403,flow.start,self.order["id"],self.leader,"check_in",self.geo())

    def test_clearing_brigadier_blocks_old_leader_then_new_assignment_recovers(self):
        self.sync()
        _,_,token=self.batch()
        self.assertFalse(self.sync(leader=None)["ready"])
        self.error(403,flow.start,self.order["id"],self.leader,"check_in",self.geo())
        with self.assertRaises(Exception):
            api.confirm_attendance_by_client(self.client,token=token)
        self.assertTrue(self.sync()["ready"])
        self.assertFalse(flow.state(self.order["id"],self.member)["paused"])

    def test_started_legacy_shift_and_outstanding_legacy_qr_are_preserved(self):
        challenge=api.create_attendance_challenge(self.order["id"],self.member,public_api_url="https://example.test")
        self.assertTrue(self.sync()["preserved"])
        token=challenge["confirmation_url"].split("/")[-1]
        api.confirm_attendance_by_client(self.client,token=token)
        self.assertTrue(self.sync()["preserved"])
        self.assertFalse(s.protected(api.get_order(self.order["id"])))
        self.assertEqual(api.list_order_attendance(self.order["id"],self.member)["attendance"][0]["status"],"checked_in")

    def test_solo_worker_is_ready_without_manual_enable(self):
        with self.db() as c:
            order=api.read_order_in_connection(c,self.order["id"])
            order["assigned_worker_ids"]=["leader"]
            api.write_order_in_connection(c,order)
        self.sync()
        qr=flow.presence(self.order["id"],self.leader,self.geo())
        self.assertEqual(qr["kind"],"confirmation")

    def test_client_confirms_full_crew_at_arrival_and_departure(self):
        self.sync()
        _,_,token=self.batch()
        api.confirm_attendance_by_client(self.client,token=token)
        self.sync()
        _,_,token=self.batch(action="check_out")
        api.confirm_attendance_by_client(self.client,token=token)
        rows=api.list_order_attendance(self.order["id"],self.client)["attendance"]
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r["check_in_at"] and r["check_out_at"] for r in rows))

    def test_feature_flag_preserves_paused_policy(self):
        with patch.dict(os.environ,{"GPM_APP_CREW_ATTENDANCE_ENABLED":"false"}):
            self.error(503,bridge.sync,self.order["id"],self.payload)


@unittest.skipUnless(os.getenv("GPM_TEST_POSTGRES_URL"),"isolated PostgreSQL CI only")
class HeadlessLeaderPostgresTests(HeadlessLeaderTests):
    postgres=True
