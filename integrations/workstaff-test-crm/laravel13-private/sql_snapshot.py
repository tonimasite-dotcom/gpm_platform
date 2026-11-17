"""Fingerprint mysqldump table DDL and each INSERT without retaining row values."""
import hashlib
import re

DROP = re.compile(rb'^DROP TABLE IF EXISTS `[A-Za-z0-9_]+`;\r?\n?$')
CREATE = re.compile(rb'^CREATE TABLE `([A-Za-z0-9_]+)` \(')
INSERT = re.compile(rb'^INSERT INTO `([A-Za-z0-9_]+)`(?:\s|\()')
FORBIDDEN = re.compile(rb'^\s*(?:USE\s|CREATE\s+DATABASE\s|DROP\s+DATABASE\s|GRANT\s|REVOKE\s|SOURCE\s|\\!|\\\.)', re.I)


class Snapshot:
    def __init__(self):
        self.sql = hashlib.sha256()
        self.sql_bytes = 0
        self.filtered_bytes = 0
        self.drops = 0
        self.rows = {}
        self.schemas = {}
        self.auto_increment = {}
        self.current = None
        self.schema = None
        self.schema_auto_column = False

    def line(self, line):
        self.sql.update(line)
        self.sql_bytes += len(line)
        if FORBIDDEN.match(line):
            raise RuntimeError('DATABASE_WIDE_OR_CLIENT_COMMAND_IN_DUMP')
        if line.startswith(b'DROP TABLE '):
            if not DROP.fullmatch(line):
                raise RuntimeError('UNEXPECTED_DROP_STATEMENT')
            self.drops += 1
            return False
        self.filtered_bytes += len(line)
        match = CREATE.match(line)
        if match:
            if self.current is not None or match[1].decode() in self.schemas:
                raise RuntimeError('DUPLICATE_OR_NESTED_CREATE')
            self.current = match[1].decode()
            self.schema = hashlib.sha256()
            self.schema_auto_column = False
            self.rows.setdefault(self.current, [])
        if self.current is not None:
            self.schema.update(line)
            if b'AUTO_INCREMENT' in line and not line.startswith(b')'):
                self.schema_auto_column = True
            if line.startswith(b')') and line.rstrip().endswith(b';'):
                value = re.search(rb'\bAUTO_INCREMENT=(\d+)\b', line)
                self.auto_increment[self.current] = int(value[1]) if value else (1 if self.schema_auto_column else None)
                self.schemas[self.current] = self.schema.hexdigest()
                self.current = None
        match = INSERT.match(line)
        if match:
            name = match[1].decode()
            if name not in self.rows:
                raise RuntimeError('INSERT_WITHOUT_TABLE')
            self.rows[name].append(hashlib.sha256(line).digest())
        return True

    def finish(self):
        if self.current is not None or not self.schemas or set(self.rows) != set(self.schemas):
            raise RuntimeError('INCOMPLETE_DUMP_SCHEMA')
        return dict(sql_sha256=self.sql.hexdigest(), sql_bytes=self.sql_bytes,
                    filtered_sql_bytes=self.filtered_bytes, drops_filtered=self.drops,
                    tables={name: dict(rows=len(values), row_sha256=hashlib.sha256(b''.join(sorted(values))).hexdigest(),
                                       schema_sha256=self.schemas[name], auto_increment=self.auto_increment[name])
                            for name, values in self.rows.items()})
