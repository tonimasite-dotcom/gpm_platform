"""Seal stopped private progress and client context; never write plaintext tar."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import os
import stat
import subprocess
import tarfile

BASE = Path('/root/gpm-ts-update')
CURRENT = BASE / 'order-parity-20261110-02'
DEST = BASE / 'session-snapshot-20261110-final-01'
W = BASE / '20261106-baseline-01'
SEAL = Path('/root/gpm-snapshots/20261015-before-sync')
EXCLUDED_NAMES = {'.git', '.cache', '.ssh', 'age-identity.txt', 'id_ed25519', 'id_rsa'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class Reader:
    def __init__(self, stream):
        self.stream, self.hash = stream, hashlib.sha256()

    def read(self, size=-1):
        value = self.stream.read(size)
        self.hash.update(value)
        return value


def main():
    os.umask(0o077)
    os.nice(10)
    output = DEST / 'GPM_SESSION_PRIVATE_20261110_FINAL.tar.gz.age'
    if DEST.resolve() != DEST or not (DEST / 'client-context/FULL_PRIVATE_HANDOFF.md').is_file() or output.exists():
        raise RuntimeError('NEW_PRIVATE_SEALED_SNAPSHOT_REQUIRED')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except OSError:
            continue
        if str(CURRENT) + '/' in cmd and any(value in cmd for value in ['mysqld', 'caretaker', 'rehearse_migrations', 'webpack']):
            raise RuntimeError('PRIVATE_WORK_MUST_BE_STOPPED')
    for folder in CURRENT.glob('rehearsal-mysql*'):
        if (folder / 'mysql.sock').exists() or (folder / 'mysql.pid').exists():
            raise RuntimeError('PRIVATE_MYSQL_NOT_STOPPED')
    if digest(W / 'original-data-checks.json') != 'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec':
        raise RuntimeError('IMMUTABLE_BASELINE_CHANGED')
    if digest(W / 'rehearse_migrations.php') != '0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259':
        raise RuntimeError('IMMUTABLE_CHECKER_CHANGED')
    roots = [CURRENT, BASE / 'order-parity-audit-20261110-01', BASE / '20261110-demo-04',
             BASE / '20261110-demo-05', BASE / '20261110-demo-06', BASE / 'demo-email-tools-20261110',
             BASE / '20261110-debt-off-01', BASE / 'debt-off-tools-20261110', BASE / 'demo-tools-20261110',
             W / 'source-main/database/migrations', W / 'candidate/database/migrations',
             W / 'candidate/app/Services/Release', W / 'acceptance-20261109', W / 'regression',
             W / 'original-data-checks.json', W / 'rehearse_migrations.php', W / 'preparation.json']
    paths = []
    skipped = []
    for root in roots + [DEST / 'client-context']:
        if not root.exists():
            skipped.append(str(root))
            continue
        prefix = 'client' if root == DEST / 'client-context' else 'server/gpm-ts-update/' + root.relative_to(BASE).as_posix()
        candidates = []
        if root.is_file():
            candidates = [(root, prefix)]
        else:
            for directory, dirs, files in os.walk(root, followlinks=False):
                directory = Path(directory)
                for name in list(dirs):
                    p = directory / name
                    if name in EXCLUDED_NAMES or p == CURRENT / 'backup-preparation-02':
                        dirs.remove(name)
                        continue
                    if p.is_symlink():
                        dirs.remove(name)
                        candidates.append((p, prefix + '/' + p.relative_to(root).as_posix()))
                candidates += [(directory / name, prefix + '/' + (directory / name).relative_to(root).as_posix())
                               for name in sorted(files) if name not in EXCLUDED_NAMES]
        paths.extend(candidates)
    paths.append((CURRENT / 'backup-preparation-02/verification.json',
                  'server/gpm-ts-update/order-parity-20261110-02/backup-preparation-02/verification.json'))
    paths.append((Path(__file__), 'tools/seal_server_snapshot.py'))
    names = [name for _, name in paths]
    if len(names) != len(set(names)):
        raise RuntimeError('DUPLICATE_SNAPSHOT_PATH')
    process = subprocess.Popen([str(SEAL / 'age'), '--encrypt', '--recipients-file', str(SEAL / 'age-recipient.txt'),
                                '--output', str(output)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    inventory = []
    try:
        with gzip.GzipFile(fileobj=process.stdin, mode='wb', compresslevel=1, mtime=0) as compressed, \
                tarfile.open(fileobj=compressed, mode='w|', dereference=True) as archive:
            for path, name in paths:
                before = path.lstat()
                if path.is_symlink():
                    info = tarfile.TarInfo(name)
                    info.type = tarfile.SYMTYPE
                    info.linkname = os.readlink(str(path))
                    info.mode = stat.S_IMODE(before.st_mode)
                    archive.addfile(info)
                    inventory.append({'file': name, 'kind': 'symlink', 'target': info.linkname})
                elif stat.S_ISREG(before.st_mode):
                    info = archive.gettarinfo(str(path), arcname=name)
                    with path.open('rb') as stream:
                        reader = Reader(stream)
                        archive.addfile(info, reader)
                    after = path.stat()
                    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                        raise RuntimeError('STOPPED_SOURCE_CHANGED_DURING_SNAPSHOT')
                    inventory.append({'file': name, 'kind': 'file', 'bytes': info.size, 'sha256': reader.hash.hexdigest()})
                else:
                    raise RuntimeError('SPECIAL_FILE_IN_STOPPED_SNAPSHOT')
            payload = json.dumps({'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'files': inventory, 'missing_optional_historical_sources': skipped,
                'recovery_private_keys_included': False, 'ts_large_encrypted_backups_are_separate_assets': True},
                ensure_ascii=True, indent=2).encode()
            import io
            info = tarfile.TarInfo('SNAPSHOT_FILE_MANIFEST.json')
            info.size, info.mode = len(payload), 0o600
            archive.addfile(info, io.BytesIO(payload))
        process.stdin.close()
        error = process.stderr.read()
        if process.wait():
            raise RuntimeError('SNAPSHOT_ENCRYPTION_FAILED')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    report = {'sealed': True, 'artifact': output.name, 'bytes': output.stat().st_size, 'sha256': digest(output),
              'entries': len(inventory), 'recovery_private_keys_included': False, 'plaintext_tar_written': False,
              'live_files_changed': False, 'private_processes_stopped_before_sealing': True,
              'decryption_verified': False}
    (DEST / 'sealed-snapshot.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
