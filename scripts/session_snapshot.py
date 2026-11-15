"""Seal or verify an encrypted, deduplicated session snapshot without extraction."""
import argparse
import gzip
import hashlib
import io
import json
import os
import pathlib
import stat
import subprocess
import tarfile
import time
import shutil
import types
import getpass


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def seal(args):
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError('Snapshot output must be new')
    roots = [part.split('=', 1) for part in args.root]
    if len({name for name, _ in roots}) != len(roots):
        raise RuntimeError('Duplicate root alias')
    external = json.loads(pathlib.Path(args.external).read_text()) if args.external else {}
    exclusions = set(args.exclude)
    inventory, objects, inode_cache, outside, specials = [], {}, {}, [], []
    process = subprocess.Popen([args.age, '--encrypt', '--recipient', args.recipient,
                                '--output', str(output)], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    started = time.monotonic()
    try:
        with gzip.GzipFile(fileobj=process.stdin, mode='wb', compresslevel=1, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w|') as archive:
                for alias, location in roots:
                    if not alias.replace('-', '').replace('_', '').isalnum():
                        raise RuntimeError('Unsafe root alias')
                    root = pathlib.Path(location).resolve(strict=True)
                    for directory, dirs, names in os.walk(str(root), followlinks=False):
                        parent = pathlib.Path(directory)
                        for name in list(dirs):
                            path = parent / name
                            relative = alias + '/' + path.relative_to(root).as_posix()
                            if name in exclusions:
                                dirs.remove(name)
                                outside.append({'path': relative, 'reason': 'rebuildable_directory'})
                            elif path.is_symlink():
                                dirs.remove(name)
                                inventory.append({'path': relative, 'kind': 'symlink', 'target': os.readlink(str(path))})
                            else:
                                inventory.append({'path': relative, 'kind': 'directory',
                                                  'mode': stat.S_IMODE(path.stat().st_mode)})
                        for name in sorted(names):
                            path = parent / name
                            relative = alias + '/' + path.relative_to(root).as_posix()
                            before = path.lstat()
                            if path.is_symlink():
                                inventory.append({'path': relative, 'kind': 'symlink', 'target': os.readlink(str(path))})
                                continue
                            if not stat.S_ISREG(before.st_mode):
                                if '/rootfs/dev/' not in relative:
                                    raise RuntimeError('Unexpected special file in stopped snapshot')
                                specials.append({'path': relative, 'mode': before.st_mode,
                                                 'device': before.st_rdev, 'reason': 'recreate_private_runtime_devices'})
                                continue
                            # A live output or a symlink into it must never enter its own input.
                            if path.resolve() == output.resolve():
                                raise RuntimeError('Snapshot cannot contain itself')
                            key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                            value = inode_cache.get(key)
                            if value is None:
                                value = digest(path)
                                inode_cache[key] = value
                            if value in external:
                                outside.append({'path': relative, 'reason': 'existing_verified_encrypted_asset',
                                                'sha256': value, 'bytes': before.st_size,
                                                'reference': external[value]})
                                continue
                            inventory.append({'path': relative, 'kind': 'file', 'bytes': before.st_size,
                                              'sha256': value, 'mode': stat.S_IMODE(before.st_mode),
                                              'mtime_ns': before.st_mtime_ns})
                            if value not in objects:
                                info = tarfile.TarInfo('objects/' + value)
                                info.size, info.mode = before.st_size, 0o600
                                with path.open('rb') as source:
                                    archive.addfile(info, source)
                                objects[value] = before.st_size
                            after = path.stat()
                            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                                raise RuntimeError('Stopped source changed during sealing')
                            if len(inventory) % 2000 == 0:
                                print(json.dumps({'progress_entries': len(inventory),
                                                  'unique_objects': len(objects)}), flush=True)
                manifest = {'format': 'gpm-session-cas-v1', 'files': inventory,
                            'external_or_rebuildable': outside, 'special_runtime_nodes': specials,
                            'roots': dict(roots), 'objects': objects,
                            'symlinks_activated': False, 'plaintext_archive_written': False}
                body = json.dumps(manifest, ensure_ascii=True).encode()
                info = tarfile.TarInfo('SNAPSHOT_MANIFEST.json')
                info.size, info.mode = len(body), 0o600
                archive.addfile(info, io.BytesIO(body))
        process.stdin.close()
        error = process.stderr.read()
        if process.wait():
            raise RuntimeError('Snapshot encryption failed; private diagnostic withheld')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    report = {'format': 'gpm-session-cas-v1', 'artifact': output.name,
              'bytes': output.stat().st_size, 'sha256': digest(output),
              'entries': len(inventory), 'unique_objects': len(objects),
              'external_or_rebuildable_entries': len(outside),
              'special_runtime_nodes': len(specials), 'elapsed_seconds': round(time.monotonic() - started, 2),
              'encrypted': True, 'decryption_verified': False}
    pathlib.Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


def verify(args):
    path = pathlib.Path(args.archive)
    actual = digest(path)
    if actual != args.sha256:
        raise RuntimeError('Encrypted file hash mismatch')
    process = subprocess.Popen([args.age, '--decrypt', '--identity', args.identity, str(path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seen, manifest = {}, None
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|gz') as archive:
            for member in archive:
                if not member.isfile():
                    raise RuntimeError('Unexpected archive member type')
                if member.name == 'SNAPSHOT_MANIFEST.json':
                    if manifest is not None or member.size > 256 * 1024 * 1024:
                        raise RuntimeError('Invalid manifest')
                    manifest = json.load(archive.extractfile(member))
                    continue
                if not member.name.startswith('objects/') or len(member.name) != 72:
                    raise RuntimeError('Unexpected archive member path')
                expected = member.name[8:]
                if expected in seen:
                    raise RuntimeError('Duplicate object')
                value = hashlib.sha256()
                stream = archive.extractfile(member)
                for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    value.update(block)
                if value.hexdigest() != expected:
                    raise RuntimeError('Object hash mismatch')
                seen[expected] = member.size
        error = process.stderr.read()
        if process.wait() or not manifest or manifest.get('format') != 'gpm-session-cas-v1':
            raise RuntimeError('Decryption or manifest validation failed')
        if seen != manifest['objects']:
            raise RuntimeError('Object inventory mismatch')
        paths = set()
        for entry in manifest['files']:
            relative = pathlib.PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or entry['path'] in paths:
                raise RuntimeError('Unsafe or duplicate restore path')
            paths.add(entry['path'])
            if entry['kind'] == 'file' and seen.get(entry['sha256']) != entry['bytes']:
                raise RuntimeError('Missing file object')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    report = {'artifact': path.name, 'bytes': path.stat().st_size, 'sha256': actual,
              'decryption_verified': True, 'all_object_hashes_verified': True,
              'entries': len(manifest['files']), 'unique_objects': len(seen),
              'plaintext_files_extracted': False, 'symlinks_activated': False}
    pathlib.Path(args.report).write_text(json.dumps(report, indent=2))
    if args.private_manifest:
        pathlib.Path(args.private_manifest).write_text(json.dumps(manifest, indent=2))
    print(json.dumps(report), flush=True)


def unpack(args):
    """Materialize regular files only into a new private directory; retain link metadata."""
    destination = pathlib.Path(args.directory).resolve()
    destination.mkdir(mode=0o700, exist_ok=False)
    if os.name == 'nt':
        subprocess.run(['icacls', str(destination), '/inheritance:r', '/grant:r',
                        getpass.getuser() + ':(OI)(CI)F'], check=True, capture_output=True)
    metadata = destination / '.snapshot-metadata'
    metadata.mkdir(mode=0o700)
    private_manifest = metadata / 'manifest.json'
    verify(types.SimpleNamespace(archive=args.archive, sha256=args.sha256,
                                 age=args.age, identity=args.identity,
                                 report=str(metadata / 'verification.json'),
                                 private_manifest=str(private_manifest)))
    manifest = json.loads(private_manifest.read_text())
    selected = [row for row in manifest['files']
                if not args.only_root or row['path'].split('/', 1)[0] in args.only_root]
    wanted = {row['sha256'] for row in selected if row['kind'] == 'file'}
    store = destination / '.snapshot-objects'
    store.mkdir(mode=0o700)
    process = subprocess.Popen([args.age, '--decrypt', '--identity', args.identity, args.archive],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|gz') as archive:
            for member in archive:
                value = member.name[8:] if member.name.startswith('objects/') else None
                if value not in wanted:
                    continue
                with (store / value).open('xb') as output:
                    shutil.copyfileobj(archive.extractfile(member), output, 1024 * 1024)
        error = process.stderr.read()
        if process.wait():
            raise RuntimeError('Second-pass decryption failed')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    links, count = [], 0
    for row in selected:
        parts = pathlib.PurePosixPath(row['path']).parts
        if os.name == 'nt' and any('\\' in p or ':' in p for p in parts):
            raise RuntimeError('Source path cannot be safely represented on Windows')
        target = destination.joinpath(*parts)
        if destination not in target.resolve().parents:
            raise RuntimeError('Restore path escaped new directory')
        if row['kind'] == 'symlink':
            links.append(row)
        elif row['kind'] == 'directory':
            target.mkdir(parents=True, exist_ok=True)
        elif row['kind'] == 'file':
            target.parent.mkdir(parents=True, exist_ok=True)
            with (store / row['sha256']).open('rb') as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            target.chmod(row['mode'] & 0o777)
            os.utime(str(target), ns=(row['mtime_ns'], row['mtime_ns']))
            count += 1
    (metadata / 'SYMLINKS_TO_REVIEW.json').write_text(json.dumps(links, indent=2))
    report = {'regular_files_restored': count, 'symlinks_activated': False,
              'symlinks_retained_as_metadata': len(links),
              'external_or_rebuildable_entries': len(manifest['external_or_rebuildable']),
              'existing_files_overwritten': False, 'database_or_application_started': False}
    (metadata / 'restore-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    create = sub.add_parser('seal')
    for option in ['output', 'age', 'recipient', 'report']:
        create.add_argument('--' + option, required=True)
    create.add_argument('--root', action='append', required=True)
    create.add_argument('--exclude', action='append', default=[])
    create.add_argument('--external')
    check = sub.add_parser('verify')
    for option in ['archive', 'sha256', 'age', 'identity', 'report']:
        check.add_argument('--' + option, required=True)
    check.add_argument('--private-manifest')
    restore = sub.add_parser('unpack')
    for option in ['archive', 'sha256', 'age', 'identity', 'directory']:
        restore.add_argument('--' + option, required=True)
    restore.add_argument('--only-root', action='append')
    args = parser.parse_args()
    if args.operation == 'seal':
        seal(args)
    elif args.operation == 'verify':
        verify(args)
    else:
        unpack(args)


if __name__ == '__main__':
    main()
