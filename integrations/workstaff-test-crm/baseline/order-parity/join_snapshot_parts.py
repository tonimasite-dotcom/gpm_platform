"""Reassemble encrypted snapshot parts, verify SHA, never decrypt or overwrite."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import uuid


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_file(directory, name):
    if Path(name).name != name or name in ['.', '..'] or '/' in name or '\\' in name:
        raise RuntimeError('SINGLE_FILENAME_REQUIRED')
    path = directory / name
    if path.is_symlink():
        raise RuntimeError('ARCHIVE_SYMLINK_REJECTED')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    directory = Path(args.directory).absolute()
    if directory.resolve() != directory or not directory.is_dir():
        raise RuntimeError('CANONICAL_EXISTING_PRIVATE_DIRECTORY_REQUIRED')
    metadata = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    assembled = []
    for artifact in metadata['artifacts']:
        parts = artifact.get('parts')
        if not parts:
            continue
        output = safe_file(directory, artifact['name'])
        if output.exists():
            if output.stat().st_size != artifact['bytes'] or digest(output) != artifact['sha256']:
                raise RuntimeError('EXISTING_ARCHIVE_MISMATCH_DO_NOT_OVERWRITE')
            assembled.append({'name': output.name, 'verified': True, 'already_present': True})
            continue
        for row in parts:
            path = safe_file(directory, row['name'])
            if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
                raise RuntimeError('MISSING_OR_DAMAGED_ENCRYPTED_PART')
        if sum(row['bytes'] for row in parts) != artifact['bytes']:
            raise RuntimeError('PART_SIZES_MISMATCH')
        if shutil.disk_usage(directory).free < artifact['bytes'] + 128 * 1024 * 1024:
            raise RuntimeError('INSUFFICIENT_ASSEMBLY_SPACE')
        temporary = directory / ('.snapshot-assembling-' + uuid.uuid4().hex)
        h = hashlib.sha256()
        with temporary.open('xb') as out:
            for row in parts:
                with safe_file(directory, row['name']).open('rb') as stream:
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        out.write(block)
                        h.update(block)
            out.flush()
            os.fsync(out.fileno())
        if temporary.stat().st_size != artifact['bytes'] or h.hexdigest() != artifact['sha256']:
            raise RuntimeError('REASSEMBLED_ENCRYPTED_SHA_MISMATCH')
        if output.exists():
            raise RuntimeError('CONCURRENT_ARCHIVE_APPEARED_DO_NOT_OVERWRITE')
        temporary.rename(output)
        assembled.append({'name': output.name, 'verified': True, 'already_present': False})
    print(json.dumps({'encrypted_archives_verified': assembled, 'plaintext_written': False, 'originals_deleted': False}))


if __name__ == '__main__':
    main()
