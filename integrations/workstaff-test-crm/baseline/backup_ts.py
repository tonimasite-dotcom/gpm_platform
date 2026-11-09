#!/usr/bin/env python3
"""Encrypted preparation backup of TS only. No writes to CRM, no plaintext dump.

An online preparation backup is not a final quiesced release checkpoint.
The source tree includes sensitive ts settings; all archive/manifest outputs are
encrypted in memory streams. Public output contains aggregate metadata only.
"""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import time

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
SEAL = Path('/root/gpm-snapshots/20261015-before-sync')
DEST = WORK / 'backup-preparation-02'
RECIPIENT = None


def age_writer(filename):
    return subprocess.Popen([str(SEAL / 'age'), '--encrypt', '--recipient',
                             RECIPIENT or (SEAL / 'age-recipient.txt').read_text().strip(),
                             '--output', str(DEST / filename)],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def close_age(process):
    process.stdin.close()
    stderr = process.stderr.read()
    if process.wait() != 0:
        raise RuntimeError('Encryption failed; private diagnostic withheld')


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def get_ts_environment():
    # Dotenv parser only: no Laravel/application bootstrap or side effects.
    code = "require '" + str(TS) + "/vendor/autoload.php'; echo json_encode(Dotenv\\Dotenv::parse(file_get_contents('" + str(TS) + "/.env')));"
    result = subprocess.run(['php', '-r', code], capture_output=True)
    if result.returncode: raise RuntimeError('Cannot read ts environment securely')
    env = json.loads(result.stdout)
    if env.get('APP_URL', '').rstrip('/') != 'https://ts.workstaffcrm.ru':
        raise RuntimeError('Not ts URL')
    if env.get('DB_CONNECTION', 'mysql') != 'mysql' or not env.get('DB_DATABASE'):
        raise RuntimeError('Unexpected ts database configuration')
    return env


class DigestReader:
    def __init__(self, stream): self.stream, self.hash = stream, hashlib.sha256()
    def read(self, size=-1):
        block = self.stream.read(size);self.hash.update(block);return block


def main():
    global DEST, RECIPIENT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination-name', default='backup-preparation-02')
    parser.add_argument('--recipient')
    options = parser.parse_args()
    if not re.fullmatch(r'backup-preparation-[a-z0-9-]+', options.destination_name):
        raise RuntimeError('Invalid private backup directory name')
    if options.recipient and not re.fullmatch(r'age1[0-9a-z]{58}', options.recipient):
        raise RuntimeError('Invalid age X25519 recipient')
    DEST = WORK / options.destination_name
    RECIPIENT = options.recipient
    os.umask(0o077)
    if TS.resolve() != TS or TS.is_symlink() or WORK.resolve() != WORK:
        raise RuntimeError('Unexpected root')
    if DEST.resolve() != DEST:
        raise RuntimeError('Unexpected backup destination')
    DEST.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic();env = get_ts_environment()
    backup = {'kind': 'online_preparation_not_release_checkpoint',
              'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'ts_root': str(TS), 'app_url': 'https://ts.workstaffcrm.ru',
              'files': {}, 'database': {'row_counts': {}, 'table_count': 0},
              'excluded': ['node_modules', '.git'],
              'consistency': 'mysqldump own single InnoDB snapshot; online files may change; writers not stopped'}
    args = ['mysqldump', '--no-defaults', '--single-transaction', '--skip-lock-tables',
            '--quick', '--no-tablespaces', '--set-gtid-purged=OFF', '--hex-blob',
            '--skip-extended-insert', '--default-character-set=utf8mb4',
            '--user=' + env['DB_USERNAME']]
    if env.get('DB_SOCKET'):
        args += ['--socket=' + env['DB_SOCKET']]
    else:
        args += ['--host=' + env.get('DB_HOST', '127.0.0.1'), '--port=' + env.get('DB_PORT', '3306')]
    args.append(env['DB_DATABASE'])
    dump_env = dict(os.environ, MYSQL_PWD=env.get('DB_PASSWORD', ''))
    dump = subprocess.Popen(args, env=dump_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    encrypted = age_writer('ts-mysql.sql.gz.age')
    sql_hash = hashlib.sha256();sql_bytes = 0
    create = re.compile(rb'^CREATE TABLE `([^`]+)`')
    # Tables with generated columns include an explicit column list before
    # VALUES. --skip-extended-insert still guarantees one row per INSERT.
    insert = re.compile(rb'^INSERT INTO `([^`]+)`(?:\s|\()')
    with gzip.GzipFile(fileobj=encrypted.stdin, mode='wb', compresslevel=1, mtime=0) as compressed:
        for line in dump.stdout:
            sql_hash.update(line);sql_bytes += len(line);compressed.write(line)
            match = create.match(line)
            if match: backup['database']['row_counts'].setdefault(match[1].decode(), 0)
            match = insert.match(line)
            if match:
                name = match[1].decode();backup['database']['row_counts'][name] = backup['database']['row_counts'].get(name, 0) + 1
    dump_error = dump.stderr.read()
    dump_code = dump.wait()
    close_age(encrypted)
    if dump_code: raise RuntimeError('TS dump failed; not a usable backup')
    backup['database'].update({'sql_sha256': sql_hash.hexdigest(), 'sql_bytes': sql_bytes,
                               'table_count': len(backup['database']['row_counts'])})
    if backup['database']['table_count'] != 72:
        raise RuntimeError('Unexpected table count; re-audit schema before proceeding')
    encrypted = age_writer('ts-files.tar.gz.age')
    unstable = []
    # Python 3.7's tar streaming mode does not accept compresslevel itself.
    # Use an explicit gzip stream without a plaintext intermediate archive.
    with gzip.GzipFile(fileobj=encrypted.stdin, mode='wb', compresslevel=1, mtime=0) as compressed, \
            tarfile.open(fileobj=compressed, mode='w|') as archive:
        for directory, dirs, files in os.walk(TS, followlinks=False):
            current = Path(directory)
            for name in list(dirs):
                path = current / name;rel = path.relative_to(TS).as_posix()
                if rel in ('node_modules', '.git'):
                    dirs.remove(name);continue
                if path.is_symlink():
                    dirs.remove(name)
                    info = archive.gettarinfo(str(path), arcname=rel)
                    archive.addfile(info)
                    backup['files'][rel] = {'kind': 'symlink', 'target': os.readlink(str(path))}
            for name in sorted(files):
                path = current / name;rel = path.relative_to(TS).as_posix()
                before = path.lstat();info = archive.gettarinfo(str(path), arcname=rel)
                if path.is_symlink():
                    archive.addfile(info);backup['files'][rel] = {'kind': 'symlink', 'target': os.readlink(str(path))}
                elif stat.S_ISREG(before.st_mode):
                    with path.open('rb') as stream:
                        source = DigestReader(stream);archive.addfile(info, source)
                    backup['files'][rel] = {'kind': 'file', 'sha256': source.hash.hexdigest(), 'bytes': info.size,
                                            'mode': stat.S_IMODE(before.st_mode)}
                    if path.stat().st_mtime_ns != before.st_mtime_ns: unstable.append(rel)
                else:
                    raise RuntimeError('Unexpected special file in ts; scope review required')
    close_age(encrypted)
    backup['unstable_online_files'] = unstable
    encrypted = age_writer('ts-manifest.json.age')
    encrypted.stdin.write(json.dumps(backup, ensure_ascii=False).encode())
    close_age(encrypted)
    files = {p.name: {'sha256': digest_file(p), 'bytes': p.stat().st_size}
             for p in DEST.iterdir() if p.is_file() and p.suffix == '.age'}
    public = {'kind': backup['kind'], 'encrypted': True, 'table_count': 72,
              'file_entries': len(backup['files']), 'unstable_online_file_count': len(unstable),
              'elapsed_seconds': round(time.monotonic() - start, 2), 'artifacts': files,
              'restore_verified': False, 'live_changed': False, 'main_crm_accessed': False}
    (DEST / 'verification.json').write_text(json.dumps(public, indent=2))
    print(json.dumps(public))


if __name__ == '__main__': main()
