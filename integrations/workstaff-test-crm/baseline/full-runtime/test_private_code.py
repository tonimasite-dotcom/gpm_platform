import unittest
from prepare_private_code import collect_secrets, sanitize, variants


class SecretBoundaryTests(unittest.TestCase):
    def test_escaped_quotes_do_not_truncate_secret(self):
        value = b"abc\\\"def'ghi\\\\jkl"
        raw = b'<?php\n"client_secret" => "' + value + b'",\n'
        secrets, _ = collect_secrets({'config.php': raw}, {'config.php': [[2, len(value)]]}, b'')
        safe, count = sanitize(raw, secrets)
        self.assertEqual(safe, b'<?php\n"client_secret" => "' + b'0' * len(value) + b'",\n')
        self.assertEqual(count, 1)

    def test_source_and_compiled_js_escaped_variants_are_removed(self):
        value = b'synthetic/secret\\"12345'
        raw = b'|'.join(variants(value))
        safe, count = sanitize(raw, variants(value))
        self.assertGreater(count, 0)
        self.assertTrue(all(item not in safe for item in variants(value)))

    def test_moved_reviewed_secret_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'LOCATION_CHANGED'):
            collect_secrets({'a.php': b"\n\n'password' => 'synthetic-secret'"},
                            {'a.php': [[2, 16]]}, b'')

    def test_env_values_never_appear_in_report(self):
        secrets, count = collect_secrets({}, {},
            b'APP_URL=https://example.invalid\nAPP_KEY=base64:synthetic-app-key\nDB_PASSWORD="synthetic-password"\n')
        self.assertEqual(count, 2)
        safe, _ = sanitize(b'synthetic-app-key synthetic-password https://example.invalid', secrets)
        self.assertNotIn(b'synthetic-app-key', safe)
        self.assertNotIn(b'synthetic-password', safe)
        self.assertIn(b'https://example.invalid', safe)

    def test_longer_secret_is_removed_before_substring(self):
        safe, count = sanitize(b'prefix-synthetic-secret', {b'synthetic-secret', b'prefix-synthetic-secret'})
        self.assertEqual(safe, b'0' * 23)
        self.assertEqual(count, 1)

    def test_dotenv_reference_is_not_a_literal_secret(self):
        secrets, count = collect_secrets({}, {}, b'MIX_PUSHER_APP_KEY="${PUSHER_APP_KEY}"\n')
        self.assertEqual(secrets, set())
        self.assertEqual(count, 0)

    def test_url_concatenation_is_not_a_credential_literal(self):
        raw = b"<?php return 'https://example.invalid/?client_id=' . $this->clientId . '&x=1';"
        with self.assertRaisesRegex(RuntimeError, 'LOCATION_CHANGED'):
            collect_secrets({'a.php': raw}, {'a.php': [[1, 21]]}, b'')

    def test_commented_credential_is_still_removed(self):
        raw = b"<?php\n// private $clientSecret = 'synthetic-secret';\n"
        values, _ = collect_secrets({'a.php': raw}, {'a.php': [[2, 16]]}, b'')
        safe, _ = sanitize(raw, values)
        self.assertNotIn(b'synthetic-secret', safe)


if __name__ == '__main__':
    unittest.main()
