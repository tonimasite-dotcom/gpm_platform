import unittest
from sql_snapshot import Snapshot


def fingerprint(rows, ddl=b') ENGINE=InnoDB AUTO_INCREMENT=9;\n'):
    value = Snapshot()
    for line in [b'DROP TABLE IF EXISTS `sample`;\n', b'CREATE TABLE `sample` (\n',
                 b'  `id` int NOT NULL AUTO_INCREMENT,\n', b'  PRIMARY KEY (`id`)\n', ddl] + rows:
        value.line(line)
    return value.finish()


class SnapshotTests(unittest.TestCase):
    def test_duplicate_rows_and_order(self):
        a = b"INSERT INTO `sample` VALUES (1);\n"
        b = b"INSERT INTO `sample` VALUES (2);\n"
        first = fingerprint([a, b, a])['tables']['sample']
        self.assertEqual(first, fingerprint([b, a, a])['tables']['sample'])
        self.assertNotEqual(first, fingerprint([a, b])['tables']['sample'])
        self.assertEqual(first['auto_increment'], 9)

    def test_modified_value_schema_and_sequence(self):
        a = fingerprint([b'INSERT INTO `sample` VALUES (1);\n'])['tables']['sample']
        self.assertNotEqual(a, fingerprint([b'INSERT INTO `sample` VALUES (2);\n'])['tables']['sample'])
        b = fingerprint([b'INSERT INTO `sample` VALUES (1);\n'], b') ENGINE=InnoDB AUTO_INCREMENT=10;\n')['tables']['sample']
        self.assertNotEqual(a['schema_sha256'], b['schema_sha256'])
        self.assertNotEqual(a['auto_increment'], b['auto_increment'])

    def test_generated_column_insert(self):
        value = fingerprint([b'INSERT INTO `sample` (`id`) VALUES (1);\n'])
        self.assertEqual(value['tables']['sample']['rows'], 1)

    def test_reject_database_switch_and_client_escape(self):
        for line in [b'USE live;\n', b'CREATE DATABASE live;\n', b'DROP DATABASE live;\n',
                     b'GRANT ALL ON *.* TO x;\n', b'\\! touch /tmp/x\n', b'SOURCE private.sql\n']:
            with self.subTest(line=line), self.assertRaises(RuntimeError):
                Snapshot().line(line)

    def test_only_exact_table_drop_is_filtered(self):
        value = Snapshot()
        self.assertFalse(value.line(b'DROP TABLE IF EXISTS `sample`;\n'))
        with self.assertRaises(RuntimeError):
            value.line(b'DROP TABLE live.sample;\n')

    def test_empty_and_incomplete_schema(self):
        with self.assertRaises(RuntimeError):
            Snapshot().finish()
        value = Snapshot()
        value.line(b'CREATE TABLE `sample` (\n')
        with self.assertRaises(RuntimeError):
            value.finish()


if __name__ == '__main__':
    unittest.main()
