import unittest

from app.phone_numbers import normalize_russian_phone, format_russian_phone
from app import app_orders_api as api, registration_preview, worker_payouts


class PhoneNumbersTest(unittest.TestCase):
    def test_formats_have_one_identity_across_registration_profiles_and_matching(self):
        for raw in ("89999999977", "79999999977", "+79999999977",
                    "+7 999 999 99 77", "8 (999) 999-99-77",
                    "9999999977", "8.999.999.99.77"):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_russian_phone(raw), "+79999999977")
                self.assertEqual(format_russian_phone(raw), "+7 (999) 999-99-77")
                self.assertEqual(registration_preview.normalize_phone(raw), "+79999999977")
                self.assertEqual(worker_payouts.normalize_phone(raw), "+79999999977")
                self.assertEqual(api._clean_profile_value("phone", raw), "+7 (999) 999-99-77")
                self.assertEqual(api.normalized_phone_identity(raw), "9999999977")

    def test_wrong_length_or_country_cannot_match_by_suffix(self):
        for raw in ("999", "179999999977", "+49999999977", "+799999999770",
                    "abc9999999977", "++79999999977", "7+9999999977", 79999999977):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    normalize_russian_phone(raw)
                with self.assertRaises(ValueError):
                    api._clean_profile_value("phone", raw)
                self.assertEqual(api.normalized_phone_identity(raw), "")

    def test_optional_empty_profile_and_foreign_registration_still_work(self):
        self.assertEqual(api._clean_profile_value("phone", ""), "")
        self.assertEqual(registration_preview.normalize_phone("+49 (123) 456789", "INT"),
                         "+49123456789")
