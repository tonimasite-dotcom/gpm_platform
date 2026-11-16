"""Remove only the cancelled November 15 archive explicitly approved by the owner.

Default: read-only preflight. No directory, backup, database or application cleanup.
The retained compact GitHub checkpoint does not reference this archive.
"""
import argparse
import datetime
import hashlib
import json
import os
import stat
from pathlib import Path

ROOT = Path('/root/gpm-ts-update/session-snapshot-20261115-01')
NAME = 'GPM_SERVER_PRIVATE_20261115.tar.gz.age'
SIZE = 5261013675
SHA = 'c467135fe8d948fdae0ba2ba3c743d4529764dca1b052a0ee50edd96cdb2dea2'
REPORT = ROOT / 'owner-approved-single-archive-removal-20261116.json'


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def siblings():
    result = {}
    for directory, dirs, files in os.walk(str(ROOT), followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path == ROOT / NAME or path == REPORT:
                continue
            info = path.lstat()
            result[str(path.relative_to(ROOT))] = identity(info) + (info.st_mode,)
    return result


def assert_unused(target_info):
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            descriptors = list((proc / 'fd').iterdir())
        except FileNotFoundError:
            continue
        for descriptor in descriptors:
            try:
                info = descriptor.stat()
            except FileNotFoundError:
                continue
            if (info.st_dev, info.st_ino) == (target_info.st_dev, target_info.st_ino):
                raise RuntimeError('ARCHIVE_IS_OPEN')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if ROOT.resolve() != ROOT or ROOT.is_symlink() or REPORT.exists():
        raise RuntimeError('EXACT_ORIGINAL_DIRECTORY_AND_NEW_REPORT_REQUIRED')
    target = ROOT / NAME
    if target.resolve() != target or target.is_symlink():
        raise RuntimeError('EXACT_REGULAR_ARCHIVE_REQUIRED')
    original = target.lstat()
    if not stat.S_ISREG(original.st_mode) or original.st_nlink != 1 or original.st_size != SIZE:
        raise RuntimeError('ARCHIVE_METADATA_MISMATCH')
    local_day = datetime.datetime.fromtimestamp(
        original.st_mtime, datetime.timezone(datetime.timedelta(hours=3))).date()
    if local_day != datetime.date(2026, 11, 15):
        raise RuntimeError('ARCHIVE_DATE_MISMATCH')
    sealed = json.loads((ROOT / 'server-sealed.json').read_text())
    if sealed['sha256'] != SHA or sealed['bytes'] != SIZE:
        raise RuntimeError('ORIGINAL_SEAL_MISMATCH')
    before_siblings = siblings()
    digest = hashlib.sha256()
    fd = os.open(str(target), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(original):
            raise RuntimeError('ARCHIVE_CHANGED_BEFORE_HASH')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        if identity(os.fstat(stream.fileno())) != identity(original):
            raise RuntimeError('ARCHIVE_CHANGED_DURING_HASH')
    if digest.hexdigest() != SHA or identity(target.lstat()) != identity(original):
        raise RuntimeError('ARCHIVE_HASH_OR_IDENTITY_MISMATCH')
    assert_unused(original)
    free_before = os.statvfs(str(ROOT)).f_bavail * os.statvfs(str(ROOT)).f_frsize
    result = {'archive': NAME, 'bytes': SIZE, 'sha256': SHA,
              'archive_date_moscow': str(local_day), 'owner_approved_single_file_only': True,
              'open_file_check_passed': True, 'applied': False,
              'retained_checkpoint': 'snapshots/2026-11-16-app-changes',
              'retained_ts_backup': 'backup-preparation-20261115',
              'original_seal_preserved_as_historical': True,
              'free_bytes_before': free_before}
    if args.apply:
        if identity(target.lstat()) != identity(original) or siblings() != before_siblings:
            raise RuntimeError('DIRECTORY_DRIFT_BEFORE_UNLINK')
        assert_unused(original)
        os.unlink(str(target))
        directory_fd = os.open(str(ROOT), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if target.exists() or siblings() != before_siblings:
            raise RuntimeError('UNEXPECTED_DIRECTORY_CHANGE_AFTER_UNLINK')
        result.update(applied=True, other_entries_unchanged=True,
                      free_bytes_after=os.statvfs(str(ROOT)).f_bavail * os.statvfs(str(ROOT)).f_frsize,
                      completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        result['recovery_note'] = ('Cancelled full-server ciphertext intentionally discarded; '
                                   'original source directories and separate TS backup retained. '
                                   'Compact continuation archive is independent. '
                                   'Do not resume old full-server upload using historical seal.')
        with REPORT.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
