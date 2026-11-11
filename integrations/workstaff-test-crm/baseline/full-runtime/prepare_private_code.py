"""Prepare an inert private code copy. Never bootstrap the source application.

The caller supplies reviewed credential locations and a prior source manifest.
No source env, application data, caches, symlinks or cron definitions are copied.
The result requires independent data/runtime/egress checks before any release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

PREFIXES = ('app', 'bootstrap', 'config', 'database', 'resources', 'routes', 'public', 'vendor')
ROOT_FILES = ('artisan', 'composer.json', 'composer.lock', 'package.json', 'package-lock.json', 'webpack.mix.js', 'vite.config.js', '.babelrc')
QUOTED = rb"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
CREDENTIAL = re.compile(
    rb'(?:withToken\(\s*|[\w-]*(?:password|passwd|secret|token|api[_-]?key|client[_-]?(?:secret|id)|access[_-]?key|private[_-]?key|login|username|sender)[\w-]*[\x27\x22]?\s*(?:=>|=|:)\s*)('
    + QUOTED + rb')', re.I)
ENV_SECRET = re.compile(rb'PASSWORD|PASSWD|SECRET|TOKEN|(?:^|_)KEY(?:$|_)', re.I)
PHP_LEXEME = re.compile(rb'//[^\r\n]*|/\*[\s\S]*?\*/|\#[^\r\n]*|' + QUOTED)


def php_literal_spans(raw):
    spans = set()
    for lexeme in PHP_LEXEME.finditer(raw):
        if lexeme.group().startswith((b'//', b'/*', b'#')):
            # Commented credentials must also be removed from private copies.
            for literal in re.finditer(QUOTED, lexeme.group()):
                spans.add((lexeme.start() + literal.start(), lexeme.start() + literal.end()))
        else:
            spans.add(lexeme.span())
    return spans


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(source):
    files = {}
    for prefix in PREFIXES:
        for here, dirs, names in os.walk(source / prefix, followlinks=False):
            base = Path(here)
            dirs[:] = [d for d in dirs if not (base / d).is_symlink()
                       and (base / d).relative_to(source).as_posix() != 'bootstrap/cache']
            for name in names:
                path = base / name
                if path.is_symlink() or not path.is_file() or name.startswith('.env') or name == 'auth.json':
                    continue
                if path.suffix.lower() in ('.pem', '.key', '.p12', '.pfx', '.sql', '.age'):
                    raise RuntimeError('SENSITIVE_FILE_REQUIRES_REVIEW')
                files[path.relative_to(source).as_posix()] = path.read_bytes()
    for name in ROOT_FILES:
        path = source / name
        if path.is_file() and not path.is_symlink():
            files[name] = path.read_bytes()
    return files


def variants(value):
    decoded = value.replace(b"\\'", b"'").replace(b'\\"', b'"').replace(b'\\\\', b'\\')
    result = {value, decoded}
    for item in tuple(result):
        result.add(item.replace(b'/', b'\\/'))
        result.add(item.replace(b'\\', b'\\\\').replace(b'"', b'\\"'))
    return {v for v in result if len(v) >= 6}


def collect_secrets(files, reviewed, env_bytes):
    values = set()
    for name, expected in reviewed.items():
        raw = files[name]
        matches = {}
        spans = php_literal_spans(raw) if name.endswith('.php') else None
        for match in CREDENTIAL.finditer(raw):
            # An URL query such as client_id=' . $id . ' is not an assignment.
            if spans is not None and match.span(1) not in spans:
                continue
            line = raw.count(b'\n', 0, match.start()) + 1
            literal = match.group(1)[1:-1]
            matches.setdefault(line, []).append(literal)
        for line, size in expected:
            found = [v for v in matches.get(line, []) if len(v) == size]
            if len(found) != 1:
                raise RuntimeError('REVIEWED_CREDENTIAL_LOCATION_CHANGED')
            values.update(variants(found[0]))
    env_count = 0
    for line in env_bytes.splitlines():
        if not line.strip() or line.lstrip().startswith(b'#') or b'=' not in line:
            continue
        name, value = line.split(b'=', 1)
        value = value.strip().strip(b'\x27\x22')
        # dotenv references contain variable names, not resolved credentials.
        if re.fullmatch(rb'\$\{[A-Za-z_][A-Za-z_0-9]*\}', value):
            continue
        if ENV_SECRET.search(name) and len(value) >= 8:
            values.update(variants(value))
            if value.startswith(b'base64:'):
                values.update(variants(value[7:]))
            env_count += 1
    return values, env_count


def sanitize(raw, values):
    count = 0
    for value in sorted(values, key=lambda item: (-len(item), item)):
        hits = raw.count(value)
        if hits:
            raw = raw.replace(value, b'0' * len(value))
            count += hits
    if any(value in raw for value in values):
        raise RuntimeError('CREDENTIAL_REMAINS_AFTER_SANITIZATION')
    return raw, count


def prepare(source, target, baseline, reviewed, write=False):
    source = source.resolve(strict=True)
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise RuntimeError('TARGET_MUST_BE_NEW_ABSOLUTE_PATH')
    resolved = target.resolve()
    if resolved.is_relative_to(source) or source.is_relative_to(resolved):
        raise RuntimeError('TARGET_OVERLAPS_SOURCE')
    if resolved.parent != Path('/root') or not re.fullmatch(r'gpm-ts-full-\d{8}-\d{2}', resolved.name):
        raise RuntimeError('TARGET_OUTSIDE_PRIVATE_REHEARSAL_ROOT')
    files = inventory(source)
    actual = {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in files.items()}
    if actual != baseline:
        raise RuntimeError('SOURCE_DIFFERS_FROM_REVIEWED_MANIFEST')
    values, env_count = collect_secrets(files, reviewed, (source / '.env').read_bytes())
    output, changed, manifest = {}, [], {}
    for name, raw in files.items():
        safe, count = sanitize(raw, values)
        output[name] = safe
        manifest[name] = {'bytes': len(safe), 'sha256': digest(safe)}
        if count:
            changed.append({'file': name, 'replacements': count})
    report = {'source_files': len(files), 'source_bytes': sum(map(len, files.values())),
              'sanitized_files': changed, 'env_secret_fields_checked': env_count,
              'remaining_reviewed_secret_matches': 0,
              'source_manifest_verified': True, 'source_changed': False,
              'application_bootstrapped': False, 'database_connected': False,
              'env_copied': False, 'storage_copied': False, 'ready_for_release': False,
              'written': write}
    if write:
        target.mkdir(mode=0o700)
        candidate = target / 'candidate'
        candidate.mkdir(mode=0o700)
        # Leave the marker present even if an interrupted copy is incomplete.
        (target / 'NOT_DEPLOYABLE_SOURCE_ONLY').write_text('No runtime or data acceptance performed.\n')
        for name, raw in output.items():
            dest = candidate / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        for directory in ['bootstrap/cache', 'storage/app/public', 'storage/framework/cache/data',
                          'storage/framework/sessions', 'storage/framework/views', 'storage/logs']:
            (candidate / directory).mkdir(parents=True, exist_ok=True)
        (candidate / 'public/storage').symlink_to('../storage/app/public', target_is_directory=True)
        for name, expected in manifest.items():
            if digest((candidate / name).read_bytes()) != expected['sha256']:
                raise RuntimeError('WRITTEN_COPY_HASH_MISMATCH')
        (target / 'code-manifest.json').write_text(json.dumps(manifest, sort_keys=True))
        (target / 'preparation-report.json').write_text(json.dumps(report, sort_keys=True))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--reviewed-locations', required=True, type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.target, json.loads(args.manifest.read_text()),
                             json.loads(args.reviewed_locations.read_text()), args.write)))
