"""Receive a validated CAS manifest and objects in a NEW private directory.

Default trial restores every path sequentially, checks content/metadata, then
removes only its newly restored regular files. Full mode retains the whole tree.
Neither mode starts a database or modifies originals. Input is private: no logs.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath

SOURCE = Path('/root/gpm-ts-update/20261109-switch-01')
PARENT = Path('/root/gpm-ts-update')
NAMES = ['accepted-new-first-run', 'next', 'runtime',
         'mysql-new-failed-after-timeout', 'mysql-new-timeout-evidence']
RESERVE = 3 * 1024**3


def validate_manifest(manifest):
    if manifest.get('format') != 'gpm-cold-rehearsal-cas-v2':
        raise RuntimeError('FORMAT')
    if manifest['roots'] != {name: (SOURCE / name).as_posix() for name in NAMES}:
        raise RuntimeError('ROOTS')
    objects = manifest['objects']
    for sha, size in objects.items():
        if not re.fullmatch('[0-9a-f]{64}', sha) or type(size) is not int or size < 0:
            raise RuntimeError('OBJECT')
    rows = {}
    used = set()
    for row in manifest['files']:
        name = row['path']
        path = PurePosixPath(name)
        if (not isinstance(name, str) or path.is_absolute() or '..' in path.parts
                or not path.parts or path.parts[0] not in NAMES or str(path) != name
                or '\\' in name or '\x00' in name or name in rows):
            raise RuntimeError('PATH')
        if row['kind'] not in {'file', 'directory', 'symlink'}:
            raise RuntimeError('KIND')
        for field in ['mode', 'uid', 'gid', 'mtime_ns', 'atime_ns']:
            if type(row[field]) is not int:
                raise RuntimeError('METADATA_TYPE')
        if not 0 <= row['mode'] <= 0o7777 or min(row['uid'], row['gid']) < 0:
            raise RuntimeError('METADATA_RANGE')
        for key, value in row['xattrs'].items():
            if '\x00' in key:
                raise RuntimeError('XATTR')
            base64.b64decode(value, validate=True)
        if row['kind'] == 'file':
            if (row['sha256'] not in objects or row['bytes'] != objects[row['sha256']]
                    or row['source_nlink'] != 1):
                raise RuntimeError('FILE_OBJECT')
            used.add(row['sha256'])
        if row['kind'] == 'symlink' and ('\x00' in row['target'] or not row['target']):
            raise RuntimeError('LINK')
        rows[name] = row
    for name, row in rows.items():
        path = PurePosixPath(name)
        if len(path.parts) == 1 and row['kind'] != 'directory':
            raise RuntimeError('ROOT_DIRECTORY')
        for parent in path.parents:
            if str(parent) != '.' and rows.get(str(parent), {}).get('kind') != 'directory':
                raise RuntimeError('NON_DIRECTORY_PARENT')
    if any(name not in rows for name in NAMES) or used != set(objects):
        raise RuntimeError('INVENTORY')
    return rows


def digest_file(path):
    digest = hashlib.sha256()
    # O_NOFOLLOW prevents the trial or original-file comparison following links.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RuntimeError('REGULAR_FILE_REQUIRED')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def apply_metadata(path, row):
    os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
    if row['kind'] != 'symlink':
        # Debian's Python 3.7 lacks chmod(follow_symlinks=False). An opened
        # O_NOFOLLOW descriptor provides the same boundary on this host.
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fchmod(descriptor, row['mode'])
        finally:
            os.close(descriptor)
    for key, value in row['xattrs'].items():
        os.setxattr(path, key, base64.b64decode(value), follow_symlinks=False)
    os.utime(path, ns=(row['atime_ns'], row['mtime_ns']), follow_symlinks=False)
    info = path.lstat()
    if (info.st_uid, info.st_gid, info.st_mtime_ns, info.st_atime_ns) != (
            row['uid'], row['gid'], row['mtime_ns'], row['atime_ns']):
        raise RuntimeError('METADATA_READBACK')
    if stat.S_IMODE(info.st_mode) != row['mode']:
        raise RuntimeError('MODE_READBACK')
    attrs = {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
             for key in os.listxattr(path, follow_symlinks=False)}
    if attrs != row['xattrs']:
        raise RuntimeError('XATTR_READBACK')


def restore(destination, manifest, source, full=False):
    rows = validate_manifest(manifest)
    if (destination.parent != PARENT or destination.resolve() != destination
            or not re.fullmatch(r'cold-restore-20261117-[a-z0-9-]+', destination.name)
            or destination.exists() or PARENT.resolve() != PARENT):
        raise RuntimeError('NEW_EXACT_RESTORE_DIRECTORY_REQUIRED')
    largest = max(manifest['objects'].values())
    required = RESERVE + largest
    if full:
        required += sum((row['bytes'] + 4095) // 4096 * 4096
                        for row in rows.values() if row['kind'] == 'file')
        required += sum(8192 for row in rows.values() if row['kind'] == 'directory')
    if shutil.disk_usage(PARENT).free < required:
        raise RuntimeError('RESTORE_AND_RESERVE_SPACE_REQUIRED')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    scratch = destination / '.object'
    directories = sorted((row for row in rows.values() if row['kind'] == 'directory'),
                         key=lambda row: len(PurePosixPath(row['path']).parts))
    for row in directories:
        (destination / row['path']).mkdir(mode=0o700)
    by_sha = {}
    for row in rows.values():
        if row['kind'] == 'file':
            by_sha.setdefault(row['sha256'], []).append(row)
    seen = set()
    restored = 0
    compared = 0
    while True:
        header = source.readline(4096)
        if not header:
            raise RuntimeError('PREMATURE_INPUT_END')
        header = json.loads(header)
        if header == {'end': True}:
            break
        sha = header['sha256']
        if (sha in seen or sha not in by_sha or header['bytes'] != manifest['objects'][sha]):
            raise RuntimeError('UNEXPECTED_OBJECT')
        if shutil.disk_usage(PARENT).free < RESERVE + header['bytes']:
            raise RuntimeError('RESERVE_REQUIRED')
        digest = hashlib.sha256()
        remaining = header['bytes']
        with scratch.open('xb') as stream:
            while remaining:
                block = source.read(min(remaining, 1024 * 1024))
                if not block:
                    raise RuntimeError('OBJECT_TRUNCATED')
                stream.write(block)
                digest.update(block)
                remaining -= len(block)
            stream.flush()
            os.fsync(stream.fileno())
        if digest.hexdigest() != sha:
            raise RuntimeError('OBJECT_HASH')
        current = scratch
        for row in by_sha[sha]:
            target = destination / row['path']
            if full:
                # New paths only; no overwrite, hardlink or symlink traversal.
                if shutil.disk_usage(PARENT).free < RESERVE + row['bytes'] + 8192:
                    raise RuntimeError('FULL_RESTORE_RESERVE_REQUIRED')
                with scratch.open('rb') as inp, target.open('xb') as out:
                    shutil.copyfileobj(inp, out, 1024 * 1024)
                    out.flush()
                    os.fsync(out.fileno())
            else:
                os.rename(current, target)
                current = target
            if target.stat().st_size != row['bytes'] or digest_file(target) != sha:
                raise RuntimeError('RESTORED_CONTENT')
            apply_metadata(target, row)
            if not full:
                original = SOURCE / row['path']
                if original.resolve() != original or digest_file(original) != sha:
                    raise RuntimeError('ORIGINAL_CHANGED_OR_LINKED')
                compared += 1
            restored += 1
        # Remove only the newly restored transient object/file in this new root.
        if current.parent != destination and destination not in current.parents:
            raise RuntimeError('TRIAL_UNLINK_BOUNDARY')
        current.unlink()
        seen.add(sha)
        if len(seen) % 3000 == 0:
            print(json.dumps({'stage': 'restore_progress', 'objects': len(seen),
                              'restored_files': restored}), flush=True)
    if seen != set(manifest['objects']):
        raise RuntimeError('OBJECTS_MISSING')
    links = 0
    for row in rows.values():
        if row['kind'] == 'symlink':
            target = destination / row['path']
            os.symlink(row['target'], target)
            if os.readlink(target) != row['target']:
                raise RuntimeError('LINK_READBACK')
            apply_metadata(target, row)
            if not full:
                original = SOURCE / row['path']
                if not original.is_symlink() or os.readlink(original) != row['target']:
                    raise RuntimeError('ORIGINAL_LINK_CHANGED')
            links += 1
    for row in reversed(directories):
        apply_metadata(destination / row['path'], row)
    if not full:
        for row in rows.values():
            if row['kind'] == 'symlink':
                (destination / row['path']).unlink()
        for row in reversed(directories):
            (destination / row['path']).rmdir()
    result = {'status': 'PASS', 'mode': 'full' if full else 'bounded_sequential_trial',
              'restored_files': restored, 'original_file_hashes_compared': compared,
              'objects': len(seen), 'directories': len(directories), 'symlinks': links,
              'all_content_and_metadata_checked': True, 'complete_tree_retained': full,
              'trial_scaffold_removed': not full,
              'original_directories_retained': True, 'database_started': False,
              'destination': str(destination), 'free_bytes_after': shutil.disk_usage(PARENT).free}
    (destination / 'restore-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    stream = sys.stdin.buffer
    body = stream.readline(128 * 1024**2)
    restore(args.destination, json.loads(body), stream, args.full)
