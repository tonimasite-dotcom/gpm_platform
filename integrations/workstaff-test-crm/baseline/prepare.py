#!/usr/bin/env python3
"""Prepare a private source candidate; never modify either running CRM.

Run on the inspected CRM host. No Laravel bootstrap, database access, migrations,
package hooks or live file replacement. A candidate with conflicts cannot deploy.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
WORK_PARENT = Path('/root/gpm-ts-update')
SOURCE_DIRS = ('app', 'config', 'routes', 'resources', 'database/migrations')
SOURCE_FILES = ('artisan', 'bootstrap/app.php', 'public/index.php', 'public/.htaccess',
                'composer.json', 'composer.lock', 'package.json', 'package-lock.json',
                'webpack.mix.js', '.babelrc', '.eslintrc', '.eslintrc.js', '.eslintrc.json',
                'public/images/gpm_logo.png')
ALLOWED = {'.php', '.vue', '.js', '.json', '.xsd', '.css', '.scss', '.sass', '.less',
           '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.ttf', '.woff', '.woff2'}
PRIVATE_NAMES = {'.env', 'auth.json', '.npmrc', '.htpasswd'}
SECRET_PATTERNS = (
    re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{25,}|AGE-SECRET-KEY-[A-Z0-9]+'),
    re.compile(rb'(?:sk_live_|xox[baprs]-)[A-Za-z0-9-]{18,}'),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    if root.is_symlink() or root.resolve() != root:
        raise RuntimeError('Unexpected live root')
    paths = {root / name for name in SOURCE_FILES if (root / name).is_file()}
    for directory in SOURCE_DIRS:
        paths.update(p for p in (root / directory).rglob('*')
                     if p.is_file() and p.suffix.lower() in ALLOWED
                     and not re.search(r'\.(backup|bak|orig|old)\.', p.name, re.I))
    files = {}
    for p in sorted(paths):
        relative = p.relative_to(root).as_posix()
        if p.is_symlink() or p.resolve() != p or any(x.is_symlink() for x in p.parents if x != root):
            raise RuntimeError('Symlink in source: ' + relative)
        if p.name in PRIVATE_NAMES or p.name.startswith('.env'):
            raise RuntimeError('Private file in allowlist: ' + relative)
        before = p.stat()
        data = p.read_bytes()
        if p.stat().st_mtime_ns != before.st_mtime_ns:
            raise RuntimeError('Source changed while reading: ' + relative)
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            raise RuntimeError('Credential-shaped material; source excluded: ' + relative)
        files[relative] = {'sha256': digest(data), 'bytes': len(data)}
    return files


def snapshot(root, target, manifest):
    for relative, meta in manifest.items():
        data = (root / relative).read_bytes()
        if digest(data) != meta['sha256']:
            raise RuntimeError('Source hash changed before snapshot: ' + relative)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def original_ts_file(relative):
    result = subprocess.run(['git', '--no-optional-locks', '-c', 'safe.directory=' + str(TS),
                             '-C', str(TS), 'show', 'HEAD:' + relative],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return result.stdout if result.returncode == 0 else None


def prepare(work):
    if not WORK_PARENT.exists():
        WORK_PARENT.mkdir(mode=0o700)
    if WORK_PARENT.is_symlink() or WORK_PARENT.resolve() != WORK_PARENT:
        raise RuntimeError('Unsafe workspace parent')
    if work.parent != WORK_PARENT or work.exists() or work.is_symlink():
        raise RuntimeError('Use a new direct child of private workspace parent')
    manifests = {'main': inventory(MAIN), 'ts': inventory(TS)}
    work.mkdir(mode=0o700)
    for label, root in [('main', MAIN), ('ts', TS)]:
        snapshot(root, work / ('source-' + label), manifests[label])
    candidate = work / 'candidate'
    shutil.copytree(work / 'source-main', candidate)
    reports = []
    for relative in sorted(manifests['ts']):
        ts_data = (work / 'source-ts' / relative).read_bytes()
        path = candidate / relative
        if relative not in manifests['main']:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ts_data)
            reports.append({'path': relative, 'action': 'preserve_ts_only'})
            continue
        if manifests['main'][relative]['sha256'] == manifests['ts'][relative]['sha256']:
            continue
        base = original_ts_file(relative)
        if base is None:
            reports.append({'path': relative, 'action': 'manual_no_base'})
            continue
        if ts_data == base:
            reports.append({'path': relative, 'action': 'upstream_ts_unchanged'})
            continue
        main_data = path.read_bytes()
        if main_data == base:
            path.write_bytes(ts_data)
            reports.append({'path': relative, 'action': 'preserve_ts_delta'})
            continue
        if path.suffix.lower() not in {'.php', '.vue', '.js', '.json', '.css', '.scss', '.sass', '.xsd'}:
            reports.append({'path': relative, 'action': 'manual_binary_or_config'})
            continue
        base_file = work / 'merge-base' / relative
        base_file.parent.mkdir(parents=True, exist_ok=True)
        base_file.write_bytes(base)
        merged = subprocess.run(['git', 'merge-file', '--stdout', '--diff3',
                                 '-L', 'upstream', '-L', 'ts-git-head', '-L', 'live-ts',
                                 str(path), str(base_file), str(work / 'source-ts' / relative)],
                                capture_output=True, check=False)
        if merged.returncode == 0:
            path.write_bytes(merged.stdout)
            reports.append({'path': relative, 'action': 'auto_merge_review_required'})
        else:
            conflict = work / 'conflicts' / relative
            conflict.parent.mkdir(parents=True, exist_ok=True)
            conflict.write_bytes(merged.stdout)
            reports.append({'path': relative, 'action': 'manual_conflict',
                            'conflict_count': max(0, merged.returncode)})
    for label, root in [('main', MAIN), ('ts', TS)]:
        if inventory(root) != manifests[label]:
            raise RuntimeError('Live source changed during preparation')
    summary = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'mode': 'private_source_candidate_only', 'workspace': str(work),
               'live_files_changed': False, 'database_accessed': False,
               'source_manifests': manifests, 'merge_actions': reports,
               'deployable': False,
               'pending': ['review all merges', 'resolve conflicts', 'migration adaptations',
                           'secret literal review', 'isolated vendor/build', 'backup and restore rehearsal']}
    (work / 'preparation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({'workspace': str(work), 'source_file_counts': {k: len(v) for k, v in manifests.items()},
                      'action_counts': {action: sum(r['action'] == action for r in reports)
                                        for action in sorted({r['action'] for r in reports})},
                      'manual_paths': [r['path'] for r in reports if r['action'].startswith('manual')],
                      'deployable': False, 'live_files_changed': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-name', default='20261106-baseline-01')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.work_name):
        raise RuntimeError('Invalid workspace name')
    os.umask(0o077)
    prepare(WORK_PARENT / args.work_name)
