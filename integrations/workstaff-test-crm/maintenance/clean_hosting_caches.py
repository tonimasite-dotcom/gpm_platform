"""Remove only rebuildable TS webpack/Babel and APT caches on the old host.

No CRM data, dependencies, backups, logs or infrastructure are removed.
"""
import json
import os
import shutil
import stat
from pathlib import Path

TS_CACHE = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/node_modules/.cache')
APT_FILES = [Path('/var/cache/apt/pkgcache.bin'), Path('/var/cache/apt/srcpkgcache.bin')]


def main():
    if TS_CACHE.resolve() != TS_CACHE or not TS_CACHE.is_dir():
        raise RuntimeError('EXACT_TS_CACHE_REQUIRED')
    files = []
    directories = []
    for directory, subdirs, names in os.walk(TS_CACHE, followlinks=False):
        parent = Path(directory)
        directories.append(parent)
        for name in subdirs + names:
            path = parent / name
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise RuntimeError('CACHE_SPECIAL_FILE_OR_LINK')
            if stat.S_ISREG(info.st_mode):
                files.append((path, info))
    for path in APT_FILES:
        info = path.lstat()
        if path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError('EXACT_APT_CACHE_FILE_REQUIRED')
        files.append((path, info))
    # Refuse active builds/package management or an open cache file.
    exact_files = {str(path) for path, _ in files}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'comm').read_text().strip()
            if command in {'node', 'npm', 'yarn', 'webpack', 'apt', 'apt-get', 'dpkg'}:
                raise RuntimeError('BUILD_OR_PACKAGE_MANAGER_ACTIVE')
            for descriptor in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(descriptor)
                except OSError:
                    continue
                if target in exact_files or target.startswith(str(TS_CACHE) + '/'):
                    raise RuntimeError('CACHE_IN_USE')
        except FileNotFoundError:
            continue
    before = shutil.disk_usage('/').free
    removed = 0
    allocated = 0
    for path, original in files:
        current = path.lstat()
        if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
            original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns
        ):
            raise RuntimeError('CACHE_CHANGED')
        path.unlink()
        removed += current.st_size
        allocated += current.st_blocks * 512
    for path in reversed(directories):
        path.rmdir()
    print(json.dumps({
        'status': 'PASS', 'removed_files': len(files), 'removed_logical_bytes': removed,
        'removed_allocated_bytes': allocated, 'free_bytes_before': before,
        'free_bytes_after': shutil.disk_usage('/').free,
        'targets': [str(TS_CACHE)] + [str(path) for path in APT_FILES],
        'crm_data_removed': False, 'backups_removed': False,
        'main_crm_changed': False, 'services_restarted': False,
    }), flush=True)


if __name__ == '__main__':
    main()
