#!/usr/bin/env python3
"""Restore a verified file stream into a NEW private tree; quarantine symlinks."""
import hashlib
import json
import os
import shutil
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
DEST = WORK / 'file-recovery-20261109'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    os.umask(0o077)
    if WORK.resolve() != WORK or DEST.exists() or DEST.is_symlink():
        raise RuntimeError('NEW_PRIVATE_RECOVERY_TREE_REQUIRED')
    manifest = json.loads(sys.stdin.buffer.readline())
    if manifest.get('ts_root') != '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru':
        raise RuntimeError('TS_MANIFEST_REQUIRED')
    expected = manifest['files']
    if not isinstance(expected, dict) or not expected:
        raise RuntimeError('FILE_MANIFEST_REQUIRED')
    required = sum(entry.get('bytes', 0) for entry in expected.values())
    if shutil.disk_usage(str(WORK)).free < required + 1024 * 1024 * 1024:
        raise RuntimeError('INSUFFICIENT_PRIVATE_RECOVERY_SPACE')
    DEST.mkdir(mode=0o700)
    tree = DEST / 'tree'
    tree.mkdir(mode=0o700)
    seen = set()
    links = {}
    count = 0
    byte_count = 0
    with tarfile.open(fileobj=sys.stdin.buffer, mode='r|gz') as source:
        for member in source:
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts or str(relative) != member.name \
                    or member.name in seen or member.name not in expected:
                raise RuntimeError('UNEXPECTED_ARCHIVE_PATH')
            seen.add(member.name)
            entry = expected[member.name]
            target = tree.joinpath(*relative.parts)
            if target.resolve() != target or tree not in target.parents:
                raise RuntimeError('UNSAFE_RECOVERY_PATH')
            if member.issym():
                if entry['kind'] != 'symlink' or member.linkname != entry['target']:
                    raise RuntimeError('SYMLINK_METADATA_MISMATCH')
                # Never create live links to test CRM or any outside tree.
                links[member.name] = {'target': member.linkname, 'mode': member.mode, 'mtime': member.mtime}
            elif member.isfile():
                if entry['kind'] != 'file' or member.size != entry['bytes']:
                    raise RuntimeError('FILE_METADATA_MISMATCH')
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                checksum = hashlib.sha256()
                actual = 0
                with target.open('xb') as output:
                    contents = source.extractfile(member)
                    for block in iter(lambda: contents.read(1024 * 1024), b''):
                        checksum.update(block)
                        actual += len(block)
                        output.write(block)
                if actual != entry['bytes'] or checksum.hexdigest() != entry['sha256']:
                    raise RuntimeError('RESTORED_CONTENT_MISMATCH')
                os.chmod(str(target), entry['mode'])
                os.utime(str(target), (member.mtime, member.mtime))
                count += 1
                byte_count += actual
            else:
                raise RuntimeError('UNSUPPORTED_ARCHIVE_MEMBER')
    if seen != set(expected):
        raise RuntimeError('INCOMPLETE_FILE_RESTORE')
    # Independent read-back verifies actual disk contents, not only the stream.
    for name, entry in expected.items():
        if entry['kind'] == 'file':
            path = tree / name
            if path.is_symlink() or path.stat().st_size != entry['bytes'] \
                    or stat.S_IMODE(path.stat().st_mode) != entry['mode'] or digest(path) != entry['sha256']:
                raise RuntimeError('DISK_READBACK_MISMATCH')
    (DEST / 'quarantined-symlinks.json').write_text(json.dumps(links, indent=2))
    report = {'regular_files_restored': count, 'regular_file_bytes': byte_count,
        'all_regular_file_hashes_and_modes_verified': True, 'archive_entries_checked': len(seen),
        'symlink_metadata_preserved': len(links), 'external_symlinks_activated': False,
        'live_crm_changed': False, 'runtime_bootstrapped': False,
        'full_production_restore_rehearsed': False, 'private_tree': str(tree)}
    (DEST / 'verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Exceptions can contain private filenames; never emit raw diagnostics.
        print(json.dumps({'success': False, 'error_code': 'PRIVATE_FILE_RESTORE_FAILED'}))
        raise SystemExit(1)
