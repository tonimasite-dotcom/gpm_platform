"""Dry-run by default. Delete only five verified stopped rehearsals with --apply.

Use --apply only after the owner's approval of the five exact paths. Compare all
current paths, content and metadata against the verified private CAS manifest;
refuse active references, changes, links in parents, extra files or missing data.
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

ROOT = Path('/root/gpm-ts-update/20261109-switch-01')
NAMES = ['accepted-new-first-run', 'next', 'runtime',
         'mysql-new-failed-after-timeout', 'mysql-new-timeout-evidence']
ARCHIVE_ROOT = Path('/root/gpm-ts-update/cold-rehearsals-20261116-01')
PRIVATE_MANIFEST = Path('/root/gpm-ts-update/cold-manifest-verified-20261117-01/MANIFEST.json')
RESTORE_RESULT = Path('/root/gpm-ts-update/cold-restore-20261117-trial-03/restore-result.json')
CIPHER_SHA = '958e9b900f3036968af12bb7149b85cca5fe7c71c5c0a81d762b4d6a315daf3a'
MANIFEST_SHA = '660986d5b6d7004c724bcf23d3993abe221f83973b92bc785f7bfcbbc4d14f91'


def digest(path):
    value = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RuntimeError('REGULAR_FILE_REQUIRED')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def references(targets):
    targets = [str(path) for path in targets]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if any(path.encode() in (proc / 'cmdline').read_bytes() for path in targets):
                raise RuntimeError('REHEARSAL_COMMAND_REFERENCE')
            nodes = [proc / 'cwd', proc / 'root'] + list((proc / 'fd').iterdir())
            for node in nodes:
                try:
                    target = os.readlink(node)
                except OSError:
                    continue
                if any(target == path or target.startswith(path + '/') for path in targets):
                    raise RuntimeError('REHEARSAL_OPEN_REFERENCE')
        except FileNotFoundError:
            continue


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_uid,
            info.st_gid, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def configuration_references(targets):
    needles = [str(path).encode() for path in targets]
    roots = ['/etc/systemd/system', '/etc/init.d', '/etc/cron.d', '/etc/cron.daily',
             '/etc/cron.hourly', '/etc/cron.weekly', '/etc/cron.monthly', '/etc/nginx',
             '/etc/apache2', '/etc/php', '/etc/mysql', '/etc/supervisor',
             '/var/spool/cron/crontabs', '/etc/crontab']
    for name in roots:
        root = Path(name)
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob('*')
        for path in candidates:
            if not path.is_file():
                continue
            with path.open('rb') as stream:
                tail = b''
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    value = tail + block
                    if any(needle in value for needle in needles):
                        raise RuntimeError('SERVICE_OR_CRON_CONFIGURATION_REFERENCE')
                    tail = value[-1024:]


def check():
    if ROOT.resolve() != ROOT or ARCHIVE_ROOT.resolve() != ARCHIVE_ROOT:
        raise RuntimeError('EXACT_PARENTS_REQUIRED')
    targets = [ROOT / name for name in NAMES]
    if any(path.resolve() != path or not path.is_dir() for path in targets):
        raise RuntimeError('EXACT_ORIGINAL_DIRECTORIES_REQUIRED')
    references(targets)
    configuration_references(targets)
    pack = json.loads((ARCHIVE_ROOT / 'pack-result.json').read_text())
    if pack['sha256'] != CIPHER_SHA or pack['manifest_sha256'] != MANIFEST_SHA:
        raise RuntimeError('EXPECTED_PACK_RECEIPT')
    archive = ARCHIVE_ROOT / 'TS_REHEARSALS_20261109.cas-v2.tar.gz.age'
    if archive.stat().st_size != pack['bytes'] or digest(archive) != CIPHER_SHA:
        raise RuntimeError('CIPHER_CHANGED')
    if PRIVATE_MANIFEST.resolve() != PRIVATE_MANIFEST or digest(PRIVATE_MANIFEST) != MANIFEST_SHA:
        raise RuntimeError('VERIFIED_MANIFEST_REQUIRED')
    manifest = json.loads(PRIVATE_MANIFEST.read_bytes())
    if (manifest['format'] != 'gpm-cold-rehearsal-cas-v2'
            or manifest['roots'] != {name: str(ROOT / name) for name in NAMES}):
        raise RuntimeError('MANIFEST_ROOTS')
    restored = json.loads(RESTORE_RESULT.read_text())
    if (restored['status'] != 'PASS' or restored['mode'] != 'bounded_sequential_trial'
            or restored['restored_files'] != pack['regular_files']
            or restored['original_file_hashes_compared'] != pack['regular_files']
            or not restored['all_content_and_metadata_checked']
            or not restored['original_directories_retained'] or restored['database_started']):
        raise RuntimeError('COMPLETE_TRIAL_REQUIRED')
    expected = {row['path']: row for row in manifest['files']}
    actual = {}
    device = ROOT.stat().st_dev
    for root in targets:
        for directory, dirs, files in os.walk(root, followlinks=False):
            parent = Path(directory)
            actual[parent.relative_to(ROOT).as_posix()] = parent.lstat()
            for name in list(dirs):
                path = parent / name
                if path.is_symlink():
                    dirs.remove(name)
                    actual[path.relative_to(ROOT).as_posix()] = path.lstat()
            for name in files:
                path = parent / name
                actual[path.relative_to(ROOT).as_posix()] = path.lstat()
    if set(expected) != set(actual) or len(actual) != pack['entries']:
        raise RuntimeError('ORIGINAL_INVENTORY_CHANGED')
    allocated = 0
    regular = 0
    for name, info in actual.items():
        row = expected[name]
        path = ROOT / name
        if info.st_dev != device:
            raise RuntimeError('NESTED_FILESYSTEM')
        if (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid, info.st_mtime_ns) != (
                row['mode'], row['uid'], row['gid'], row['mtime_ns']):
            raise RuntimeError('ORIGINAL_METADATA_CHANGED')
        attrs = {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
                 for key in os.listxattr(path, follow_symlinks=False)}
        if attrs != row['xattrs']:
            raise RuntimeError('ORIGINAL_XATTRS_CHANGED')
        if row['kind'] == 'file':
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_size != row['bytes'] or digest(path) != row['sha256']):
                raise RuntimeError('ORIGINAL_CONTENT_CHANGED')
            regular += 1
        elif row['kind'] == 'directory':
            if not stat.S_ISDIR(info.st_mode) or path.resolve() != path:
                raise RuntimeError('ORIGINAL_DIRECTORY_CHANGED')
        elif row['kind'] == 'symlink':
            if not stat.S_ISLNK(info.st_mode) or os.readlink(path) != row['target']:
                raise RuntimeError('ORIGINAL_SYMLINK_CHANGED')
        else:
            raise RuntimeError('SPECIAL_FILE')
        if stamp(path.lstat()) != stamp(info):
            raise RuntimeError('SOURCE_CHANGED_DURING_CHECK')
        allocated += info.st_blocks * 512
    if regular != pack['regular_files']:
        raise RuntimeError('REGULAR_COUNT_CHANGED')
    references(targets)
    for name, info in actual.items():
        if stamp((ROOT / name).lstat()) != stamp(info):
            raise RuntimeError('SOURCE_CHANGED_AFTER_CHECK')
    return targets, allocated, len(actual)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Only after exact owner approval')
    args = parser.parse_args()
    targets, allocated, entries = check()
    before = shutil.disk_usage('/').free
    if args.apply:
        if not shutil.rmtree.avoids_symlink_attacks:
            raise RuntimeError('SAFE_RMTREE_REQUIRED')
        for target in targets:
            if target.parent != ROOT or target.name not in NAMES or target.resolve() != target:
                raise RuntimeError('DELETE_BOUNDARY')
            shutil.rmtree(target)
    result = dict(status='PASS', mode='apply' if args.apply else 'dry_run',
                  exact_targets=[str(path) for path in targets], entries_verified=entries,
                  expected_allocated_bytes=allocated, source_content_and_metadata_match=True,
                  active_references=False, original_directories_deleted=args.apply,
                  archive_retained=True, cipher_sha256=CIPHER_SHA,
                  free_bytes_before=before, free_bytes_after=shutil.disk_usage('/').free,
                  main_crm_changed=False, backups_deleted=False, database_started=False)
    if args.apply:
        destination = ARCHIVE_ROOT / 'cleanup-result-20261117.json'
        with destination.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
