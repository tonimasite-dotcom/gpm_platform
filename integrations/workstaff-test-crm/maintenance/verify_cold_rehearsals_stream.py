"""Verify the encrypted CAS archive locally in memory, optionally trial restore.

The age identity stays local; archives/manifests/objects are not saved on the PC.
Only aggregate receipts may be saved in Git. Private work stays on the old host.
"""
import argparse
import base64
import gzip
import hashlib
import json
import re
import shlex
import subprocess
import tarfile
import threading
from pathlib import Path

from restore_cold_rehearsals import validate_manifest
from verify_ts_backup_stream import AGE, KEY, SSH

# Options must precede the destination already present in the shared SSH list.
SSH = SSH[:-1] + ['-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=6'] + SSH[-1:]

DIRECTORY = '/root/gpm-ts-update/cold-rehearsals-20261116-01'
ARTIFACT = 'TS_REHEARSALS_20261109.cas-v2.tar.gz.age'
DESTINATION = '/root/gpm-ts-update/cold-restore-20261117-trial-03'
PRIVATE_MANIFEST = '/root/gpm-ts-update/cold-manifest-verified-20261117-01/MANIFEST.json'


class Stream:
    def __init__(self, receipt):
        self.receipt = receipt
        self.hash = hashlib.sha256()
        self.bytes = 0
        self.error = None
        self.source = subprocess.Popen(SSH + ['cat ' + DIRECTORY + '/' + ARTIFACT],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.decrypt = subprocess.Popen([str(AGE), '--decrypt', '--identity', str(KEY)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        self.thread = threading.Thread(target=self.pump, daemon=True)
        self.thread.start()

    def pump(self):
        try:
            for block in iter(lambda: self.source.stdout.read(1024 * 1024), b''):
                self.hash.update(block)
                self.bytes += len(block)
                self.decrypt.stdin.write(block)
        except Exception as error:
            self.error = type(error).__name__
        finally:
            try:
                self.decrypt.stdin.close()
            except OSError:
                pass

    def finish(self):
        for _ in iter(lambda: self.decrypt.stdout.read(1024 * 1024), b''):
            pass
        self.thread.join(timeout=60)
        if self.thread.is_alive():
            raise RuntimeError('STREAM_THREAD_TIMEOUT')
        self.source.stderr.read()
        self.decrypt.stderr.read()
        if self.source.wait() or self.decrypt.wait() or self.error:
            raise RuntimeError('DECRYPT_OR_SSH_FAILED')
        if self.bytes != self.receipt['bytes'] or self.hash.hexdigest() != self.receipt['sha256']:
            raise RuntimeError('CIPHER_HASH_OR_SIZE')

    def abort(self):
        for process in [self.source, self.decrypt]:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)


def consume(receipt, manifest_expected=None, sink=None):
    encrypted = Stream(receipt)
    objects = {}
    manifest = None
    try:
        with gzip.GzipFile(fileobj=encrypted.decrypt.stdout) as zipped:
            with tarfile.open(fileobj=zipped, mode='r|') as archive:
                for member in archive:
                    if not member.isfile() or member.linkname:
                        raise RuntimeError('TAR_MEMBER_TYPE')
                    content = archive.extractfile(member)
                    if member.name == 'MANIFEST.json':
                        if manifest is not None or member.size > 128 * 1024**2:
                            raise RuntimeError('MANIFEST_DUPLICATE_OR_SIZE')
                        body = content.read()
                        if hashlib.sha256(body).hexdigest() != receipt['manifest_sha256']:
                            raise RuntimeError('MANIFEST_HASH')
                        manifest = json.loads(body)
                        validate_manifest(manifest)
                        if manifest_expected is not None and manifest != manifest_expected:
                            raise RuntimeError('MANIFEST_CHANGED')
                    else:
                        sha = member.name.removeprefix('objects/')
                        if (member.name != 'objects/' + sha or len(sha) != 64
                                or sha in objects or manifest is not None):
                            raise RuntimeError('OBJECT_NAME_OR_ORDER')
                        if manifest_expected is not None and manifest_expected['objects'].get(sha) != member.size:
                            raise RuntimeError('OBJECT_SIZE')
                        digest = hashlib.sha256()
                        if sink:
                            sink.write((json.dumps({'sha256': sha, 'bytes': member.size}) + '\n').encode())
                        for block in iter(lambda: content.read(1024 * 1024), b''):
                            digest.update(block)
                            if sink:
                                sink.write(block)
                        if digest.hexdigest() != sha:
                            raise RuntimeError('OBJECT_CONTENT_HASH')
                        objects[sha] = member.size
                        if len(objects) % 3000 == 0:
                            print(json.dumps({'stage': 'stream_restore' if sink else 'stream_verify',
                                              'objects': len(objects)}), flush=True)
            # Consume gzip trailer too, so CRC/truncation are checked.
            for _ in iter(lambda: zipped.read(1024 * 1024), b''):
                pass
        encrypted.finish()
        if manifest is None or objects != manifest['objects']:
            raise RuntimeError('OBJECT_INVENTORY')
        if (len(objects) != receipt['unique_objects']
                or len(manifest['files']) != receipt['entries']
                or sum(objects.values()) != receipt['unique_content_bytes']):
            raise RuntimeError('PACK_RECEIPT_COUNTS')
        return manifest
    except Exception:
        encrypted.abort()
        raise


def save_manifest(manifest, receipt):
    # Pack used this exact JSON serialization. Private metadata stays on old TS.
    body = json.dumps(manifest, ensure_ascii=True).encode()
    if hashlib.sha256(body).hexdigest() != receipt['manifest_sha256']:
        raise RuntimeError('MANIFEST_SERIALIZATION')
    code = ("import os,sys,hashlib; from pathlib import Path; os.umask(0o077)\n"
            f"p=Path('{PRIVATE_MANIFEST}'); assert p.parent.resolve()==p.parent\n"
            "p.parent.mkdir(mode=0o700,exist_ok=True)\n"
            "body=sys.stdin.buffer.read(128*1024**2+1)\n"
            f"assert hashlib.sha256(body).hexdigest()=='{receipt['manifest_sha256']}'\n"
            "assert not p.is_symlink()\n"
            "if p.exists(): assert p.read_bytes()==body\n"
            "else:\n with p.open('xb') as out: out.write(body)\n")
    result = subprocess.run(SSH + ['python3 -B -c ' + shlex.quote(code)], input=body,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('PRIVATE_MANIFEST_SAVE_FAILED')


def read_manifest(receipt):
    result = subprocess.run(SSH + ['cat ' + PRIVATE_MANIFEST],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode or hashlib.sha256(result.stdout).hexdigest() != receipt['manifest_sha256']:
        raise RuntimeError('PRIVATE_MANIFEST_READ_OR_HASH')
    manifest = json.loads(result.stdout)
    validate_manifest(manifest)
    return manifest


def restore_remote(receipt, manifest, destination, full=False):
    if not re.fullmatch('/root/gpm-ts-update/cold-restore-20261117-[a-z0-9-]+', destination):
        raise RuntimeError('EXACT_NEW_PRIVATE_DESTINATION_REQUIRED')
    script = Path(__file__).with_name('restore_cold_rehearsals.py').read_bytes()
    sha = hashlib.sha256(script).hexdigest()
    remote_tools = '/root/gpm-ts-update/cold-restore-tools-20261117-' + sha[:16]
    encoded = base64.b64encode(script).decode()
    upload = ("import os,base64,hashlib; from pathlib import Path; os.umask(0o077)\n"
              f"p=Path('{remote_tools}')\n"
              "assert p.resolve()==p\n"
              "if not p.exists(): p.mkdir(mode=0o700)\n"
              "s=p/'restore_cold_rehearsals.py'\n"
              "assert not s.is_symlink()\n"
              f"if not s.exists():\n with s.open('xb') as out: out.write(base64.b64decode('{encoded}'))\n"
              f"assert hashlib.sha256(s.read_bytes()).hexdigest()=='{sha}'\n")
    result = subprocess.run(SSH + ['python3 -B -'], input=upload.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('NEW_REMOTE_RESTORE_TOOL_UPLOAD_FAILED')
    process = subprocess.Popen(SSH + ['python3 -B ' + remote_tools +
                                      '/restore_cold_rehearsals.py ' + destination + (' --full' if full else '')],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    remote_results = []
    errors = []

    def output():
        for line in process.stdout:
            try:
                value = json.loads(line)
                remote_results.append(value)
                print(json.dumps(value), flush=True)
            except Exception:
                errors.append('INVALID_RESTORE_RECEIPT')

    thread = threading.Thread(target=output, daemon=True)
    thread.start()
    try:
        process.stdin.write(json.dumps(manifest, separators=(',', ':')).encode() + b'\n')
        consume(receipt, manifest, process.stdin)
        process.stdin.write(b'{"end":true}\n')
        process.stdin.close()
        stderr = process.stderr.read()
        code = process.wait()
        thread.join(timeout=15)
        if code or errors or not remote_results or remote_results[-1].get('status') != 'PASS':
            # Report an error label only: paths and private manifest data stay private.
            labels = stderr.decode(errors='replace').splitlines()
            label = next((line for line in reversed(labels) if line.startswith('RuntimeError:')), '')
            raise RuntimeError('TRIAL_RESTORE_FAILED ' + label)
        return remote_results[-1]
    except Exception as error:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=15)
        diagnostics = process.stderr.read().decode(errors='replace').splitlines()
        label = next((line for line in reversed(diagnostics) if line.startswith('RuntimeError:')), '')
        if not label and diagnostics:
            label = diagnostics[-1].split(':', 1)[0]
        raise RuntimeError('TRIAL_STREAM_FAILED ' + label) from error


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--trial', action='store_true')
    modes.add_argument('--trial-destination')
    modes.add_argument('--full-destination')
    parser.add_argument('--use-verified-manifest', action='store_true')
    args = parser.parse_args()
    received = subprocess.run(SSH + ['cat ' + DIRECTORY + '/pack-result.json'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if received.returncode:
        raise RuntimeError('PACK_RECEIPT_READ_FAILED')
    receipt = json.loads(received.stdout)
    if receipt['artifact'] != ARTIFACT or receipt['files_removed'] or receipt['hardlinked_source_files']:
        raise RuntimeError('UNSUPPORTED_PACK_RECEIPT')
    if args.use_verified_manifest:
        if not (args.trial or args.trial_destination or args.full_destination):
            raise RuntimeError('RESTORE_REQUIRED_WITH_CACHED_MANIFEST')
        manifest = read_manifest(receipt)
    else:
        manifest = consume(receipt)
        save_manifest(manifest, receipt)
    result = {'status': 'PASS', 'cipher_sha256': receipt['sha256'], 'cipher_bytes': receipt['bytes'],
              'manifest_sha256': receipt['manifest_sha256'], 'objects': len(manifest['objects']),
              'entries': len(manifest['files']), 'largest_object_bytes': max(manifest['objects'].values()),
              'original_logical_bytes': receipt['source_logical_bytes'],
              'decryption_and_all_object_hashes_verified': not args.use_verified_manifest,
              'private_key_uploaded': False,
              'archive_saved_on_pc': False, 'originals_deleted': False}
    print(json.dumps(result), flush=True)
    Path('.tmp/cold-rehearsal-verification-20261117.json').write_text(json.dumps(result, indent=2) + '\n')
    if args.trial or args.trial_destination or args.full_destination:
        full = bool(args.full_destination)
        destination = args.full_destination or args.trial_destination or DESTINATION
        result['full_restore' if full else 'trial_restore'] = restore_remote(receipt, manifest, destination, full)
        result['decryption_and_all_object_hashes_verified'] = True
    Path('.tmp/cold-rehearsal-verification-20261117.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'stage': 'complete', **result}), flush=True)


if __name__ == '__main__':
    main()
