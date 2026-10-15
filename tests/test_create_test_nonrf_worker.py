import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import app_orders_api as api
from scripts import create_test_nonrf_worker as maintenance


class RequestedWorkerCreationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        environment = patch.dict(os.environ, {
            'GPM_APP_ENV': 'production',
            'GPM_APP_SQLITE_DB_FILE': str(self.root / 'test.sqlite3'),
            'GPM_APP_JWT_SECRET': 'x' * 32,
        }, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        api.init_db()
        for target, value in [
            ('ROOT', self.root), ('DESTINATION', self.root / 'sealed' / maintenance.USERNAME),
        ]:
            mock = patch.object(maintenance, target, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.documents = []

    def run_creation(self, *, apply=True):
        def encrypt(command, **kwargs):
            self.documents.append(json.loads(kwargs['input']))
            Path(command[command.index('--output') + 1]).write_bytes(b'age-encryption.org/v1\nsealed-test-double')

        arguments = ['create_test_nonrf_worker', '--age', '/fake/age', '--recipient', 'age1synthetic']
        if apply:
            arguments.append('--apply')
        output = io.StringIO()
        with patch('sys.argv', arguments), patch('pathlib.Path.cwd', return_value=self.root), \
             patch.object(api, 'validate_runtime_configuration'), patch.object(api, 'is_postgres_enabled', return_value=True), \
             patch.object(maintenance.subprocess, 'run', side_effect=encrypt), contextlib.redirect_stdout(output):
            maintenance.main()
        return output.getvalue()

    def test_creation_sets_nonrf_and_never_prints_credentials_or_resets_on_retry(self):
        output = self.run_creation()
        document = self.documents[0]
        self.assertNotIn(document['password'], output)
        with api.db_connection() as connection:
            account = api._fetch_account_for_login(connection, maintenance.USERNAME)
        self.assertTrue(api.verify_password(document['password'], account[2]))
        user = {'sub': account[0], 'username': maintenance.USERNAME, 'role': 'worker'}
        profile = api.get_account_profile(user)
        self.assertIs(profile['nationality'], False)
        self.assertIs(profile['nationality_recorded'], True)
        self.assertEqual(profile['cities'], ['Москва', 'Санкт-Петербург'])
        retry = self.run_creation()
        self.assertIn('"already_exists": true', retry)
        self.assertEqual(len(self.documents), 1)
        with api.db_connection() as connection:
            after = api._fetch_account_for_login(connection, maintenance.USERNAME)
        self.assertEqual(account[2], after[2])

    def test_dry_run_creates_neither_an_account_nor_credentials(self):
        self.run_creation(apply=False)
        self.assertEqual(self.documents, [])
        self.assertFalse(maintenance.DESTINATION.exists())
        with api.db_connection() as connection:
            self.assertIsNone(api._fetch_account_for_login(connection, maintenance.USERNAME))

    def test_existing_account_without_our_marker_is_never_changed(self):
        invitation = api.create_account_invitation(maintenance.USERNAME, 'worker', created_by='test')
        api.redeem_account_invitation(invitation['token'], 'Synthetic password 123!')
        with self.assertRaisesRegex(RuntimeError, 'never resetting password'):
            self.run_creation()
        self.assertEqual(self.documents, [])
