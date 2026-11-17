"""Read-only retirement audit on the OLD host; print aggregates, never secrets.

Does not bootstrap PHP, query the new production DB, change schedules or files.
Private settings/commands/log URLs stay in memory. This is not a deletion tool.
"""
import collections
import datetime
import gzip
import json
import os
import re
import shlex
import stat
import subprocess
import time
from pathlib import Path

OLD = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')


def env(path):
    values = {}
    for line in path.read_text(errors='replace').splitlines():
        match = re.match(r'\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)', line)
        if match:
            value = match[2].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
                value = value[1:-1]
            values[match[1]] = value
    return values


def configuration():
    found = []
    cron = []
    for directory in ['/etc/nginx', '/etc/apache2', '/etc/php', '/etc/systemd/system',
                      '/etc/supervisor', '/etc/cron.d', '/etc/cron.daily', '/etc/cron.hourly',
                      '/etc/cron.weekly', '/var/spool/cron/crontabs']:
        root = Path(directory)
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            data = path.read_bytes()
            for number, line in enumerate(data.splitlines(), 1):
                stripped = line.strip()
                if str(OLD).encode() not in line:
                    continue
                active = not stripped.startswith((b'#', b';'))
                record = dict(config=str(path), line=number, active=active)
                if 'cron' in directory:
                    record.update(scheduler=b'schedule:run' in line, artisan=b'artisan' in line,
                                  curl=b'curl' in line, backup=b'backup' in line.lower())
                    cron.append(record)
                else:
                    found.append(record)
    return dict(file_references=found, cron_references=cron)


def processes():
    result = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'cmdline').read_bytes()
            matched_command = str(OLD).encode() in command
            refs = 0
            for node in [proc / 'cwd', proc / 'root'] + list((proc / 'fd').iterdir()):
                try:
                    target = os.readlink(node)
                except OSError:
                    continue
                if target == str(OLD) or target.startswith(str(OLD) + '/'):
                    refs += 1
            if refs or matched_command:
                result.append(dict(pid=int(proc.name), comm=(proc / 'comm').read_text().strip(),
                                   command_references_old=matched_command, open_references=refs))
        except FileNotFoundError:
            continue
    return result


def logs():
    now = time.time()
    result = []
    for path in sorted(Path('/var/www/gruzpiter/data/logs').glob('workstaffcrm.ru*access*')):
        count = 0
        recent = collections.Counter()
        latest = None
        latest_successful_write = None
        if not path.is_file():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', errors='replace') as stream:
            for line in stream:
                match = re.search(r'\[([^]]+)\] "(\S+) ([^ ]*) [^"]*" (\d{3}) ', line)
                if not match:
                    continue
                try:
                    date = datetime.datetime.strptime(match[1], '%d/%b/%Y:%H:%M:%S %z')
                except ValueError:
                    continue
                count += 1
                stamp = date.timestamp()
                latest = max(latest or stamp, stamp)
                age = now - stamp
                if age > 7 * 86400:
                    continue
                method, url, code = match[2], match[3].split('?', 1)[0], int(match[4])
                recent['requests_7d'] += 1
                if age <= 86400:
                    recent['requests_24h'] += 1
                if method in {'POST', 'PUT', 'PATCH', 'DELETE'} and 200 <= code < 400:
                    recent['successful_write_requests_7d'] += 1
                    latest_successful_write = max(latest_successful_write or stamp, stamp)
                if 200 <= code < 300 and url.startswith(('/api/', '/auth/', '/login')):
                    recent['successful_api_or_auth_7d'] += 1
                recent['status_' + str(code)] += 1
        result.append(dict(log=path.name, bytes=path.stat().st_size, parsed_requests=count,
                           last_request_utc=datetime.datetime.utcfromtimestamp(latest).isoformat() if latest else None,
                           last_successful_write_utc=datetime.datetime.utcfromtimestamp(latest_successful_write).isoformat()
                           if latest_successful_write else None, recent=dict(recent)))
    return result


def dependencies(old, ts):
    matches = []
    links = []
    for directory, dirs, files in os.walk(TS, followlinks=False):
        parent = Path(directory)
        dirs[:] = [name for name in dirs if name not in {'node_modules', 'vendor', '.git'}]
        for name in dirs + files:
            path = parent / name
            if path.is_symlink():
                resolved = path.resolve()
                if resolved == OLD or OLD in resolved.parents:
                    links.append(path.relative_to(TS).as_posix())
        if parent == TS / 'storage':
            dirs[:] = []
        for name in files:
            path = parent / name
            if path.is_symlink() or path.suffix not in {'.php', '.js', '.json', '.vue', '.conf'}:
                continue
            if path.stat().st_size > 16 * 1024**2:
                continue
            if str(OLD).encode() in path.read_bytes():
                matches.append(path.relative_to(TS).as_posix())
    keys = ['DB_CONNECTION', 'DB_HOST', 'DB_PORT', 'DB_DATABASE']
    same_database = all(old.get(key, '') == ts.get(key, '') for key in keys)
    return dict(ts_links_to_old=links, ts_code_references_old_path=matches,
                same_database= same_database,
                old_database_host_local=old.get('DB_HOST') in {'localhost', '127.0.0.1', '::1'},
                ts_database_host_local=ts.get('DB_HOST') in {'localhost', '127.0.0.1', '::1'},
                same_db_username=old.get('DB_USERNAME') == ts.get('DB_USERNAME'))


def database(old, ts):
    results = {}
    for label, setting in [('old', old), ('ts', ts)]:
        name = setting.get('DB_DATABASE', '')
        if not re.fullmatch('[A-Za-z0-9_]+', name):
            results[label] = {'status': 'UNKNOWN_DATABASE_NAME'}
            continue
        query = ("SELECT COUNT(*),COALESCE(SUM(DATA_LENGTH+INDEX_LENGTH),0) FROM information_schema.TABLES "
                 "WHERE TABLE_SCHEMA='" + name + "';SELECT COMMAND,COUNT(*) FROM information_schema.PROCESSLIST "
                 "WHERE DB='" + name + "' GROUP BY COMMAND;")
        run = subprocess.run(['mysql', '-NBe', query], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode:
            results[label] = {'status': 'MYSQL_READ_UNAVAILABLE'}
            continue
        lines = run.stdout.decode().splitlines()
        table_count, allocated = map(int, lines[0].split('\t'))
        results[label] = dict(status='READ_ONLY', tables=table_count, approximate_bytes=allocated,
                              connections_by_command={line.split('\t')[0]: int(line.split('\t')[1]) for line in lines[1:]})
    return results


def main():
    if OLD.resolve() != OLD or TS.resolve() != TS:
        raise RuntimeError('EXACT_OLD_HOST_PATHS_REQUIRED')
    old = env(OLD / '.env')
    ts = env(TS / '.env')
    result = dict(audit='legacy_crm_retirement', read_only=True,
                  server_time_utc=datetime.datetime.utcnow().isoformat(),
                  configuration=configuration(), processes=processes(),
                  dependencies=dependencies(old, ts), database=database(old, ts), access_logs=logs())
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
