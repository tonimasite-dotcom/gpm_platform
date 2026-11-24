import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app import app_orders_api as api
from app.worker_payouts import BANK_NAMES

class WorkerSbpPayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"GPM_APP_SQLITE_DB_FILE": os.path.join(self.temp.name, "test.sqlite3"), "GPM_APP_JWT_SECRET": "s" * 32}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        api.init_db()
        self.worker = self.actor("worker", "synthetic-sbp-worker")
        self.other = self.actor("worker", "synthetic-other-worker")
        self.logist = self.actor("logist", "synthetic-sbp-logist")
        self.bank = next(iter(BANK_NAMES))
    def actor(self, role, name):
        invite = api.create_account_invitation(name, role, created_by="test")
        account = api.redeem_account_invitation(invite["token"], "Synthetic password 123!")
        return {"sub": account["account_id"], "username": name, "role": role}
    def valid(self):
        return {"payout_method": "sbp", "payout_bank_id": self.bank, "payout_phone": "8 (900) 000-00-01"}
    def test_payout_is_persisted_separately_from_contact_and_existing_account(self):
        api.update_account_profile(self.worker, {"phone": "+79000000000", "display_name": "Synthetic worker", "payout_account": "synthetic-account"})
        result = api.update_account_profile(self.worker, self.valid())
        self.assertEqual(result["payout_method"], "sbp")
        self.assertEqual(result["payout_bank_name"], BANK_NAMES[self.bank])
        self.assertEqual(result["payout_phone"], "+79000000001")
        self.assertEqual(result["phone"], "+7 (900) 000-00-00")
        self.assertEqual(result["payout_account"], "synthetic-account")
        self.assertEqual(api.get_account_profile(self.worker)["payout_phone"], "+79000000001")
        self.assertEqual(api.get_account_profile(self.other)["payout_phone"], "")
        api.update_account_profile(self.worker, {"display_name": "Changed name"})
        self.assertEqual(api.get_account_profile(self.worker)["payout_phone"], "+79000000001")
    def test_invalid_or_partial_details_never_overwrite_a_valid_profile(self):
        api.update_account_profile(self.worker, self.valid())
        before = api.get_account_profile(self.worker)
        for patch_value in [
            {"payout_phone": ""}, {"payout_bank_id": ""}, {"payout_bank_id": "000000000000"},
            {"payout_phone": "+449000000000"}, {"payout_phone": "a9000000001"},
            {"payout_phone": "++79000000001"}, {"payout_bank_id": []},
            {"payout_method": "wire-to-anywhere"},
        ]:
            with self.subTest(patch=patch_value), self.assertRaises(HTTPException) as caught:
                api.update_account_profile(self.worker, patch_value)
            self.assertEqual(caught.exception.status_code, 422)
            self.assertEqual(api.get_account_profile(self.worker), before)
    def test_new_sbp_choice_requires_both_bank_and_phone(self):
        for changes in [{"payout_method": "sbp"}, {"payout_method": "sbp", "payout_bank_id": self.bank}]:
            with self.assertRaises(HTTPException) as caught:
                api.update_account_profile(self.worker, changes)
            self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(api.get_account_profile(self.worker)["payout_method"], "")
    def test_bank_name_is_server_controlled_and_details_do_not_leak_to_directory(self):
        with self.assertRaises(HTTPException):
            api.update_account_profile(self.worker, {**self.valid(), "payout_bank_name": "forged bank"})
        with self.assertRaises(HTTPException):
            api.update_account_profile(self.logist, self.valid())
        api.update_account_profile(self.worker, self.valid())
        for row in [api.worker_summary(self.worker["sub"]), *api.list_worker_profiles(self.logist)["workers"]]:
            for field in ["payout_phone", "payout_bank_id", "payout_bank_name", "payout_method"]:
                self.assertNotIn(field, row)
    def test_card_and_account_methods_still_work_and_preserve_saved_sbp_details(self):
        api.update_account_profile(self.worker, self.valid())
        for method in ["card", "account", ""]:
            saved = api.update_account_profile(self.worker, {"payout_method": method})
            self.assertEqual(saved["payout_method"], method)
            self.assertEqual(saved["payout_phone"], "+79000000001")
