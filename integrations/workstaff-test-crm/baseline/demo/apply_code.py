#!/usr/bin/env python3
"""TS-only code installation; failure holds maintenance, never restores SMTP.

Default is dry-run. Live apply requires an explicitly reviewed manifest SHA.
The same installation engine is exercised only on new private fixture roots.
No SQL, migrations, env edits, cron edits, shared cache reset or service reload.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import pwd
import subprocess
import tempfile
import time

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PRIVATE = Path('/root/gpm-ts-update/20261110-demo-04')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def write_state(path, state):
    encoded = (json.dumps(state, indent=2) + '\n').encode()
    with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix='.demo-state-', delete=False) as out:
        temp = Path(out.name)
        out.write(encoded)
        out.flush()
        os.fsync(out.fileno())
    os.replace(str(temp), str(path))


def ordered(rows):
    def key(row):
        name = row['file']
        if name.startswith('app/Services/Release/'):
            return 0, name
        if name == 'app/Providers/AppServiceProvider.php':
            return 1, name
        if name.startswith('app/Console/Commands/'):
            return 2, name
        return 3, name
    return sorted(rows, key=key)


def install(target, source, rows, state_path, invalidate, probe, *, resume=False, fail_after=None, post_probe=None):
    """Caller must establish exact private/live identity and backup first."""
    if target.resolve() != target or source.resolve() != source:
        raise RuntimeError('CANONICAL_INSTALL_ROOT_REQUIRED')
    owner = pwd.getpwnam('gruzpiter') if target == TS else None
    down = target / 'storage/framework/down'
    if down.parent.resolve() != down.parent or not down.parent.is_dir():
        raise RuntimeError('EXACT_MAINTENANCE_DIRECTORY_REQUIRED')
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    if resume:
        state = json.loads(state_path.read_text())
        if state['fingerprint'] != fingerprint or state['target'] != str(target) or down.is_symlink() or sha(down) != state['maintenance_sha256']:
            raise RuntimeError('EXACT_OWN_MAINTENANCE_STATE_REQUIRED')
    else:
        if state_path.exists() or down.exists() or down.is_symlink():
            raise RuntimeError('NEW_INSTALL_AND_NO_EXISTING_MAINTENANCE_REQUIRED')
        state = {'fingerprint': fingerprint, 'target': str(target), 'complete': False, 'installed': []}
    # All disk checks precede changes. No unknown concurrent changes are accepted.
    for row in rows:
        path = target / row['file']
        staged = source / row['file']
        if path.resolve() != path or staged.resolve() != staged or sha(staged) != row['after_sha256']:
            raise RuntimeError('SOURCE_OR_TARGET_MISMATCH')
        allowed = [row['before_sha256'], row['after_sha256']] if resume else [row['before_sha256']]
        if sha(path) not in allowed:
            raise RuntimeError('LIVE_FILE_CHANGED_REVIEW_REQUIRED')
    if not resume:
        body = json.dumps({'time': int(time.time()), 'retry': 60, 'status': 503}).encode()
        with down.open('xb') as out:
            out.write(body)
        if target == TS:
            os.chown(down, owner.pw_uid, owner.pw_gid)
            down.chmod(0o640)
        state['maintenance_sha256'] = sha(down)
        state['maintenance_body'] = body.decode()
        write_state(state_path, state)
    staged_files = []
    try:
        # Reserve and fsync every replacement before the first original changes.
        for row in ordered(rows):
            path = target / row['file']
            if sha(path) == row['after_sha256']:
                continue
            if not path.parent.exists():
                if row['file'] not in ['app/Services/Release/GpmTsDemoPolicy.php', 'app/Services/Release/GpmTsDemoTransport.php', 'app/Services/Release/GpmTsDemoLoginInbox.php']:
                    raise RuntimeError('UNEXPECTED_NEW_DIRECTORY')
                path.parent.mkdir(mode=0o755)
                if target == TS:
                    os.chown(path.parent, owner.pw_uid, owner.pw_gid)
            old = path.stat() if path.exists() else None
            with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix='.gpm-ts-demo-', delete=False) as out:
                temp = Path(out.name)
                staged_files.append((temp, path, row))
                out.write((source / row['file']).read_bytes())
                out.flush()
                os.fsync(out.fileno())
                os.fchmod(out.fileno(), old.st_mode & 0o777 if old else 0o644)
                if target == TS:
                    os.fchown(out.fileno(), old.st_uid if old else owner.pw_uid,
                              old.st_gid if old else owner.pw_gid)
            if sha(temp) != row['after_sha256']:
                raise RuntimeError('STAGED_REPLACEMENT_HASH_MISMATCH')
        if fail_after == 0:
            raise RuntimeError('INJECTED_INSTALL_FAILURE')
        count = 0
        for temp, path, row in staged_files:
            observed = sha(path)
            if path.resolve() != path or observed not in [row['before_sha256'], row['after_sha256']]:
                raise RuntimeError('CONCURRENT_FILE_CHANGE')
            os.replace(str(temp), str(path))
            state['installed'].append(row['file'])
            write_state(state_path, state)
            count += 1
            if fail_after == count:
                raise RuntimeError('INJECTED_INSTALL_FAILURE')
        if any(sha(target / row['file']) != row['after_sha256'] for row in rows):
            raise RuntimeError('POST_INSTALL_HASH_MISMATCH')
        state['fpm'] = invalidate(rows)
        if not state['fpm'].get('passed'):
            raise RuntimeError('FPM_INVALIDATION_NOT_VERIFIED')
        # Internal socket request while public TS is still in maintenance.
        state['runtime_probe'] = probe()
        if not state['runtime_probe'].get('passed'):
            raise RuntimeError('GUARDED_RUNTIME_NOT_VERIFIED')
        if down.is_symlink() or sha(down) != state['maintenance_sha256']:
            raise RuntimeError('MAINTENANCE_MARKER_CHANGED')
        # Only this install's marker is removed. Prior maintenance is refused.
        down.unlink()
        if post_probe is not None:
            state['http_acceptance'] = post_probe()
            if not state['http_acceptance'].get('passed'):
                raise RuntimeError('POST_RELEASE_HTTP_NOT_VERIFIED')
        state['complete'] = True
        state['maintenance_held'] = False
        write_state(state_path, state)
        return state
    except Exception:
        if not down.exists() and not down.is_symlink():
            with down.open('xb') as out:
                out.write(state['maintenance_body'].encode())
            if target == TS:
                os.chown(down, owner.pw_uid, owner.pw_gid)
                down.chmod(0o640)
        state['maintenance_held'] = down.exists()
        state['complete'] = False
        state['failure_details_withheld'] = True
        write_state(state_path, state)
        raise
    finally:
        # Remove only our unused temporary replacement files, never old code.
        for temp, path, row in staged_files:
            if temp.exists() and temp.parent == path.parent and not temp.is_symlink():
                temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--approved-manifest')
    args = parser.parse_args()
    if not args.apply:
        return subprocess.call(['python3', str(Path(__file__).parent / 'release_plan.py')])
    manifest_path = PRIVATE / 'manifest.json'
    if args.approved_manifest != sha(manifest_path):
        raise RuntimeError('EXACT_OWNER_REVIEWED_MANIFEST_REQUIRED')
    manifest = json.loads(manifest_path.read_text())
    auth_reports = sorted(PRIVATE.glob('login-acceptance-*.json'))
    if not auth_reports or not json.loads(auth_reports[-1].read_text()).get('passed'):
        raise RuntimeError('PRIVATE_AUTH_ACCEPTANCE_REQUIRED')
    rehearsal = json.loads((PRIVATE / 'install-rehearsal.json').read_text())
    transport = json.loads((PRIVATE / 'transport-acceptance.json').read_text())
    if not rehearsal.get('passed') or not transport.get('passed'):
        raise RuntimeError('PRIVATE_RELEASE_ACCEPTANCE_REQUIRED')
    if not args.resume:
        check = subprocess.run(['python3', str(Path(__file__).parent / 'release_plan.py')],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check.returncode or not json.loads(check.stdout).get('dry_run_passed'):
            raise RuntimeError('FRESH_RELEASE_PREFLIGHT_REQUIRED')
    from fpm_probe import run_probe, request
    def invalidate(rows):
        return run_probe('fpm_invalidate.php', rows)
    def probe():
        return run_probe('fpm_runtime_probe.php')
    def http_probe():
        result = {}
        for uri, expected in [('/api/user', 401), ('/', 200)]:
            response = request(TS / 'public/index.php', '', {
                'SCRIPT_NAME': '/index.php', 'REQUEST_URI': uri, 'HTTP_ACCEPT': 'application/json' if uri.startswith('/api/') else 'text/html',
                'HTTPS': 'on', 'SERVER_PORT': '443', 'REQUEST_SCHEME': 'https'}, metadata_only=True)
            result[uri] = response
            if response['status'] != expected or response['demo_marker'] != 'ts-demo-20261110-04':
                return {'passed': False, 'responses': result}
        return {'passed': True, 'responses': result}
    state = install(TS, PRIVATE / 'runtime', manifest['files'], PRIVATE / 'live-install-state.json',
                    invalidate, probe, resume=args.resume, post_probe=http_probe)
    print(json.dumps({'passed': state['complete'], 'manifest_sha256': sha(manifest_path),
                      'maintenance_held': state['maintenance_held'], 'http_acceptance': state['http_acceptance'],
                      'shared_services_reloaded': False, 'database_migrations_executed': False}))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'TS_INSTALL_REFUSED_OR_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)
