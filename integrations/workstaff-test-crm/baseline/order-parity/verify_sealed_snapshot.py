"""Verify encrypted checksum and every sealed tar entry without extraction."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--age', required=True)
    parser.add_argument('--identity', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    archive = Path(args.archive)
    h = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    if h.hexdigest() != args.sha256:
        raise RuntimeError('ENCRYPTED_SNAPSHOT_HASH_MISMATCH')
    process = subprocess.Popen([args.age, '--decrypt', '--identity', args.identity, str(archive)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    observed, manifest = {}, None
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|gz') as source:
            for member in source:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or member.name in observed:
                    raise RuntimeError('UNSAFE_OR_DUPLICATE_SNAPSHOT_MEMBER')
                if member.name == 'SNAPSHOT_FILE_MANIFEST.json':
                    if manifest is not None or member.size > 128 * 1024 * 1024:
                        raise RuntimeError('BOUNDED_SINGLE_MANIFEST_REQUIRED')
                    manifest = json.loads(source.extractfile(member).read())
                elif member.isfile():
                    value = hashlib.sha256()
                    stream = source.extractfile(member)
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        value.update(block)
                    observed[member.name] = {'file': member.name, 'kind': 'file', 'bytes': member.size, 'sha256': value.hexdigest()}
                elif member.issym():
                    observed[member.name] = {'file': member.name, 'kind': 'symlink', 'target': member.linkname}
                else:
                    raise RuntimeError('SPECIAL_SNAPSHOT_MEMBER_REJECTED')
        error = process.stderr.read()
        if process.wait() or manifest is None:
            raise RuntimeError('SNAPSHOT_DECRYPTION_OR_MANIFEST_FAILED')
        expected = {row['file']: row for row in manifest['files']}
        if len(expected) != len(manifest['files']) or observed != expected:
            raise RuntimeError('SEALED_MEMBER_INVENTORY_MISMATCH')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    report = {'verified': True, 'encrypted_sha256': args.sha256, 'encrypted_bytes': archive.stat().st_size,
              'all_member_hashes_verified': True, 'entries': len(observed),
              'decryption_verified': True, 'plaintext_files_extracted': False, 'symlinks_activated': False,
              'private_identity_copied': False}
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
