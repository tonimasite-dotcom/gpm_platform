import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from app import registration_preview as reg


class RegistrationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'GPM_REGISTRATION_PREVIEW_DB': self.temp.name + '/preview.sqlite3'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.time = 1795176000.0  # Fixed test clock; domain tests use explicit calendar dates below.
        self.timer = patch.object(reg, 'clock', side_effect=lambda: self.time)
        self.timer.start(); self.addCleanup(self.timer.stop)
        self.store = reg.PreviewStore()
        self.state = self.store.create()
        self.sid, self.token = self.state['registration_id'], self.state['session_token']

    def patch(self, values):
        self.state = self.store.patch(self.sid, self.token, self.state['revision'], values)
        return self.state

    def ready(self, phone='+79990000000'):
        self.patch({'phone': phone, 'phone_country': 'RU'})
        self.state = self.store.challenge(self.sid, self.token, self.state['revision'])
        self.state = self.store.verify(self.sid, self.token, self.state['revision'], reg.TEST_CODE)
        return self.patch({'district_ids': [502, 502], 'city_ids': [], 'first_name': 'Иван',
                           'last_name': 'Иванов', 'middle_name': '', 'birth_date': '1994-01-01',
                           'citizenship_ru': False, 'has_straps': False, 'has_tools': False})

    def error(self, code, function, *args):
        with self.assertRaises(HTTPException) as caught: function(*args)
        self.assertEqual(caught.exception.detail['code'], code)

    def test_persistence_false_answers_district_only_and_completion_are_isolated(self):
        self.ready()
        loaded = reg.PreviewStore().read(self.sid, self.token)
        self.assertEqual(loaded['answers']['district_ids'], [502])
        self.assertEqual(loaded['answers']['city_ids'], [])
        self.assertFalse(loaded['answers']['citizenship_ru'])
        self.assertTrue(loaded['can_complete'])
        result = self.store.complete(self.sid, self.token, loaded['revision'], uuid4().hex)
        self.assertTrue(result['profile_id'].startswith('preview_'))
        self.assertFalse(result['profile_active'])
        with self.store.connection() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(tables, {'preview_sessions', 'preview_profiles', 'preview_events'})
            self.assertEqual(db.execute('SELECT count(*) FROM preview_profiles').fetchone()[0], 1)

    def test_lost_response_retry_and_concurrent_confirmation_create_one_profile(self):
        self.ready(); revision = self.state['revision']; key = uuid4().hex
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.store.complete(self.sid, self.token, revision, key), range(2)))
        self.assertEqual(results[0]['profile_id'], results[1]['profile_id'])
        self.assertEqual(self.store.complete(self.sid, self.token, revision, uuid4().hex)['profile_id'], results[0]['profile_id'])
        self.error('IDEMPOTENCY_CONFLICT', self.store.complete, self.sid, self.token, revision+1, key)

    def test_cross_session_and_untrusted_confirmation_fields_are_rejected(self):
        other = self.store.create()
        self.error('UNAUTHORIZED', self.store.read, self.sid, other['session_token'])
        self.error('UNKNOWN_FIELD', self.store.patch, self.sid, self.token, 0, {'phone_verified': True})
        self.error('UNKNOWN_FIELD', self.store.patch, self.sid, self.token, 0, {'rating': 999})

    def test_patch_is_atomic_and_old_revision_cannot_overwrite(self):
        self.patch({'first_name': 'Иван'})
        self.error('INVALID_NAME', self.store.patch, self.sid, self.token, self.state['revision'], {'first_name': 'Петр', 'last_name': '123'})
        self.assertEqual(self.store.read(self.sid, self.token)['answers']['first_name'], 'Иван')
        self.error('REVISION_CONFLICT', self.store.patch, self.sid, self.token, 0, {'first_name': 'Петр'})

    def test_phone_change_invalidates_proof_and_completion_needs_new_verification(self):
        self.ready()
        self.patch({'phone': '+79990000002'})
        self.assertFalse(self.state['phone_verified'])
        self.error('INCOMPLETE', self.store.complete, self.sid, self.token, self.state['revision'], uuid4().hex)

    def test_challenge_expiry_attempt_limit_and_resend_limit(self):
        self.patch({'phone': '8 (999) 000-00-00', 'phone_country': 'RU'})
        self.assertEqual(self.state['answers']['phone'], '+79990000000')
        self.state = self.store.challenge(self.sid, self.token, self.state['revision'])
        self.error('RATE_LIMITED', self.store.challenge, self.sid, self.token, self.state['revision'])
        for _ in range(5): self.error('INVALID_CODE', self.store.verify, self.sid, self.token, self.state['revision'], '000000')
        self.error('RATE_LIMITED', self.store.verify, self.sid, self.token, self.state['revision'], reg.TEST_CODE)
        self.time += 301
        self.error('CODE_EXPIRED', self.store.verify, self.sid, self.token, self.state['revision'], reg.TEST_CODE)
        self.state = self.store.challenge(self.sid, self.token, self.state['revision'])
        self.state = self.store.verify(self.sid, self.token, self.state['revision'], reg.TEST_CODE)
        self.assertTrue(self.state['phone_verified'])

    def test_occupied_phone_does_not_leak_or_remove_existing_profile(self):
        self.ready(); self.store.complete(self.sid, self.token, self.state['revision'], uuid4().hex)
        second = self.store.create(); self.sid, self.token, self.state = second['registration_id'], second['session_token'], second
        self.ready()
        self.error('PHONE_IN_USE', self.store.complete, self.sid, self.token, self.state['revision'], uuid4().hex)
        with self.store.connection() as db: self.assertEqual(db.execute('SELECT count(*) FROM preview_profiles').fetchone()[0], 1)

    def test_expired_draft_rejects_changes_and_completion(self):
        self.ready(); self.time += reg.TTL + 1
        self.assertEqual(self.store.read(self.sid, self.token)['status'], 'expired')
        self.error('SESSION_EXPIRED', self.store.patch, self.sid, self.token, self.state['revision'], {'first_name': 'Петр'})
        self.error('SESSION_EXPIRED', self.store.complete, self.sid, self.token, self.state['revision'], uuid4().hex)

    def test_restart_needs_confirmation_and_cannot_remove_completed_profile(self):
        self.ready()
        self.error('CONFIRMATION_REQUIRED', self.store.restart, self.sid, self.token, self.state['revision'], False)
        result = self.store.complete(self.sid, self.token, self.state['revision'], uuid4().hex)
        self.error('ALREADY_COMPLETED', self.store.restart, self.sid, self.token, self.state['revision'], True)
        self.assertEqual(self.store.read(self.sid, self.token)['profile_id'], result['profile_id'])

    def test_catalogue_disabled_after_review_and_bool_null_rejected(self):
        self.ready()
        changed = [{**v, 'enabled': False if v['id']==502 else v['enabled']} for v in reg.LOCATIONS]
        with patch.object(reg, 'LOCATIONS', changed):
            self.error('LOCATION_UNAVAILABLE', self.store.complete, self.sid, self.token, self.state['revision'], uuid4().hex)
        for value in (None, 'false', 0):
            self.error('INVALID_BOOLEAN', self.store.patch, self.sid, self.token, self.state['revision'], {'has_tools': value})

    def test_names_keep_letters_and_normalize_unicode_without_guessing_citizenship(self):
        self.assertEqual(reg.normalize_name('  E\u0301mile  ', 'first_name'), 'Émile')
        for value in ['Jean-Pierre', 'Петр', 'Пётр', '李', 'محمد']:
            self.assertEqual(reg.normalize_name(value, 'first_name'), value)
        for value in ['Иван Иван', '123', '<script>', '-Иван', 'Иван--Петр']:
            self.error('INVALID_NAME', reg.normalize_name, value, 'first_name')

    def test_age_boundary_is_server_moscow_date(self):
        self.time = datetime(2026, 11, 19, 22, tzinfo=timezone.utc).timestamp()
        self.patch({'birth_date': '2008-11-20'})  # Already November 20 in Moscow.
        self.error('AGE_UNDER_18', self.store.patch, self.sid, self.token, self.state['revision'], {'birth_date': '2008-11-21'})
        for value in ['2026-02-31', '2100-01-01', 'not-a-date']:
            self.error('INVALID_BIRTH_DATE', self.store.patch, self.sid, self.token, self.state['revision'], {'birth_date': value})
