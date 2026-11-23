import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi import HTTPException
from app import app_orders_api as api
from app import crew_storage as s, crew_flow as flow, crew_confirmation as confirmation


class CrewAttendanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "GPM_APP_SQLITE_DB_FILE": self.temp.name+"/crew.sqlite3",
            "GPM_APP_DATABASE_URL": "", "DATABASE_URL": "",
            "GPM_APP_JWT_SECRET": "x"*40, "GPM_APP_CREW_ATTENDANCE_ENABLED": "true",
        }, clear=True)
        self.environment.start()
        api.init_db()
        with api.db_connection() as c:
            for user,role in [("client","client"),("leader","worker"),("member","worker"),
                              ("late","worker"),("logist","logist"),("stranger","logist")]:
                c.execute(f"""INSERT INTO {api.ACCOUNTS_TABLE_NAME}
                    (account_id,username,username_normalized,password_hash,role) VALUES (?,?,?,?,?)""",
                    (user,user,user,"synthetic-hash",role))
        self.client={"sub":"client","role":"client"}
        self.leader={"sub":"leader","role":"worker"}
        self.member={"sub":"member","role":"worker"}
        self.logist={"sub":"logist","role":"logist"}
        self.order={"id":"SYNTHETIC/CREW","external_order_id":"SYNTHETIC/CREW","title":"Synthetic",
            "status":"PROCESSED","source":"manual","created_by_role":"client","created_by":"client",
            "logist_account_id":"logist","assigned_worker_ids":["leader","member"],"workers_count":2,
            "crew_leader_account_id":"leader","address_lat":59.93,"address_lon":30.31,
            "hours":4,"min_time":4,"price_per_hour":500}
        with api.db_connection() as c:
            api.write_order_in_connection(c,self.order)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def geo(self,**changes):
        return {"lat":59.93,"lon":30.31,"accuracy":10,
                "measured_at":datetime.now(timezone.utc).isoformat(),**changes}

    def batch(self,bad=False,action="check_in"):
        session=flow.start(self.order["id"],self.leader,action,self.geo())
        proof=flow.presence(self.order["id"],self.member,None if bad else self.geo(),action)
        flow.scan(session["session_id"],self.leader,proof["confirmation_url"],self.geo())
        challenge=flow.freeze(session["session_id"],self.leader,"https://example.test")
        return session,proof,challenge["confirmation_url"].split("/")[-1]

    def error(self,status,function,*args,**kwargs):
        with self.assertRaises(HTTPException) as caught:
            function(*args,**kwargs)
        self.assertEqual(caught.exception.status_code,status)

    def test_batch_records_individual_scan_time(self):
        _,proof,token=self.batch()
        self.assertEqual(len(api.preview_attendance_for_client(self.client,token=token)["participants"]),2)
        with api.db_connection() as c:
            scanned=s.one(c,f"SELECT collected_at FROM {s.MEMBERS} WHERE evidence_id=?",(proof["evidence_id"],))["collected_at"]
        self.assertTrue(api.confirm_attendance_by_client(self.client,token=token)["crew"])
        rows=api.list_order_attendance(self.order["id"],self.client)["attendance"]
        member=next(r for r in rows if r["worker_account_id"]=="member")
        self.assertEqual(api.parse_db_datetime(member["check_in_at"]),api.parse_db_datetime(scanned))
        self.error(409,api.confirm_attendance_by_client,self.client,token=token)

    def test_worker_qr_cannot_be_confirmed_by_client(self):
        proof=flow.presence(self.order["id"],self.member,self.geo())
        self.error(404,api.preview_attendance_for_client,self.client,token=proof["confirmation_url"].split(":")[-1])

    def test_only_leader_can_collect_and_each_qr_is_used_once(self):
        session=flow.start(self.order["id"],self.leader,"check_in",self.geo())
        proof=flow.presence(self.order["id"],self.member,self.geo())
        self.error(403,flow.scan,session["session_id"],self.member,proof["confirmation_url"],self.geo())
        flow.scan(session["session_id"],self.leader,proof["confirmation_url"],self.geo())
        self.error(409,flow.scan,session["session_id"],self.leader,proof["confirmation_url"],self.geo())

    def test_geo_review_is_scoped_and_preserves_time(self):
        _,proof,token=self.batch(bad=True)
        api.confirm_attendance_by_client(self.client,token=token)
        with api.db_connection() as c:
            self.assertIsNone(api._read_attendance_in_connection(c,self.order["id"],"member"))
            row=s.one(c,f"SELECT * FROM {s.MEMBERS} WHERE evidence_id=?",(proof["evidence_id"],))
            self.assertEqual(row["status"],"pending_review")
        self.error(403,confirmation.review,proof["evidence_id"],{"sub":"stranger","role":"logist"},"approve","checked")
        self.error(422,confirmation.review,proof["evidence_id"],self.logist,"approve","")
        confirmation.review(proof["evidence_id"],self.logist,"approve","Checked presence evidence")
        with api.db_connection() as c:
            record=api._read_attendance_in_connection(c,self.order["id"],"member")
            self.assertEqual(api.parse_db_datetime(record["check_in_at"]),api.parse_db_datetime(row["collected_at"]))
        self.error(409,confirmation.review,proof["evidence_id"],self.logist,"approve","retry")

    def test_review_requires_client_confirmation_first(self):
        _,proof,_=self.batch(bad=True)
        self.error(409,confirmation.review,proof["evidence_id"],self.logist,"approve","checked")

    def test_rejected_geo_does_not_create_hours(self):
        _,proof,token=self.batch(bad=True)
        api.confirm_attendance_by_client(self.client,token=token)
        confirmation.review(proof["evidence_id"],self.logist,"reject","Not present at object")
        with api.db_connection() as c:
            self.assertIsNone(api._read_attendance_in_connection(c,self.order["id"],"member"))
        flow.presence(self.order["id"],self.member,self.geo())

    def test_frozen_members_cannot_be_extended(self):
        session,proof,_=self.batch()
        self.error(409,flow.scan,session["session_id"],self.leader,proof["confirmation_url"],self.geo())

    def test_reassigned_leader_invalidates_frozen_qr(self):
        _,_,token=self.batch()
        with api.db_connection() as c:
            order=api.read_order_in_connection(c,self.order["id"])
            order["crew_leader_account_id"]="member"
            api.write_order_in_connection(c,order)
        self.error(409,api.confirm_attendance_by_client,self.client,token=token)

    def test_expired_presence_cannot_be_collected(self):
        session=flow.start(self.order["id"],self.leader,"check_in",self.geo())
        proof=flow.presence(self.order["id"],self.member,self.geo())
        with api.db_connection() as c:
            s.query(c,f"UPDATE {s.MEMBERS} SET token_expires_at=? WHERE evidence_id=?",
                    (s.stamp(s.now()-timedelta(seconds=1)),proof["evidence_id"]))
        self.error(410,flow.scan,session["session_id"],self.leader,proof["confirmation_url"],self.geo())

    def test_geo_accuracy_distance_age_and_invalid_values(self):
        self.assertEqual(s.geo_evidence(self.geo(),self.order)["status"],"valid")
        for location in [None,self.geo(accuracy=500),self.geo(lat=50),self.geo(lat=float("nan")),
                         self.geo(measured_at="2000-01-01T00:00:00Z"),self.geo(lat=True)]:
            self.assertEqual(s.geo_evidence(location,self.order)["status"],"review")

    def test_pending_checkout_prevents_closing_the_order(self):
        _,_,token=self.batch()
        api.confirm_attendance_by_client(self.client,token=token)
        _,proof,token=self.batch(action="check_out",bad=True)
        api.confirm_attendance_by_client(self.client,token=token)
        order=api.get_order(self.order["id"])
        self.assertNotEqual(order["status"],"DONE_PENDING")
        order["status"]="DONE_PENDING"
        with api.db_connection() as c:
            self.error(409,api.write_order_in_connection,c,order)
        confirmation.review(proof["evidence_id"],self.logist,"approve","Confirmed exception")
        self.assertEqual(api.get_order(self.order["id"])["status"],"DONE_PENDING")

    def test_solo_worker_uses_own_final_qr(self):
        with api.db_connection() as c:
            order=api.read_order_in_connection(c,self.order["id"])
            order["assigned_worker_ids"]=["member"]
            order.pop("crew_leader_account_id",None)
            api.write_order_in_connection(c,order)
        challenge=flow.presence(self.order["id"],self.member,self.geo())
        token=challenge["confirmation_url"].split("/")[-1]
        api.confirm_attendance_by_client(self.client,token=token)
        self.assertEqual(api.list_order_attendance(self.order["id"],self.member)["attendance"][0]["status"],"checked_in")

    def test_paused_feature_cannot_be_bypassed_via_legacy_qr(self):
        session=flow.start(self.order["id"],self.leader,"check_in",self.geo())
        with patch.dict(os.environ,{"GPM_APP_CREW_ATTENDANCE_ENABLED":"false"}):
            self.error(503,api.create_attendance_challenge,self.order["id"],self.member,public_api_url="https://example.test")
        flow.cancel(session["session_id"],self.leader)

    def test_crm_identity_and_roster_are_explicit(self):
        with api.db_connection() as c:
            order=api.read_order_in_connection(c,self.order["id"])
            order.update(source="crm",source_system="workstaff",source_instance=api.CRM_SYNC_INSTANCE)
            api.write_order_in_connection(c,order)
            api.crm_logist_ids.grant(c,"logist",assigned_by="synthetic")
        body={"source_instance":api.CRM_SYNC_INSTANCE,"sender_crm_id":"#1",
              "crm_worker_id":"101","worker_account_id":"leader"}
        confirmation.link_worker(self.order["id"],body)
        confirmation.link_worker(self.order["id"],{**body,"crm_worker_id":"102","worker_account_id":"member"})
        self.error(403,confirmation.export,self.order["id"],{**body,"sender_crm_id":"#2"})
        confirmation.sync_roster(self.order["id"],{**body,"crm_worker_ids":["101","102"],"crm_leader_id":"101"})
        result=confirmation.export(self.order["id"],body)
        self.assertEqual({r["crm_worker_id"] for r in result["rows"]},{"101","102"})
        self.error(409,confirmation.link_worker,self.order["id"],{**body,"crm_worker_id":"999"})
