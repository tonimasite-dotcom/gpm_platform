#!/usr/bin/env python3
"""Verify new ciphertext and stream file recovery; the private age key stays local."""
import hashlib
import json
from pathlib import Path
import subprocess

# This script is run from the original workspace, whose ignored .tmp holds keys.
LOCAL = Path.cwd() / '.tmp/crm-recovery-20261109'
AGE = LOCAL / 'tools/age/age.exe'
KEY = LOCAL / 'age-identity.txt'
BACKUP = LOCAL / 'backup'


def main():
    public = json.loads((BACKUP / 'verification.json').read_text())
    for name, record in public['artifacts'].items():
        path = BACKUP / name
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(block)
        if path.stat().st_size != record['bytes'] or checksum.hexdigest() != record['sha256']:
            raise RuntimeError('Encrypted backup mismatch')
    decoded = subprocess.run([str(AGE), '--decrypt', '--identity', str(KEY),
        str(BACKUP / 'ts-manifest.json.age')], capture_output=True)
    if decoded.returncode:
        raise RuntimeError('Manifest decryption failed')
    manifest = json.loads(decoded.stdout)
    # A round-trip decryption check precedes any remote extraction.
    total_bytes = sum(entry.get('bytes', 0) for entry in manifest['files'].values())
    receiver = subprocess.Popen(['ssh', '-i', str(Path.cwd() / '.tmp/crm-access-20261109/id_ed25519'),
        '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
        'root@5.183.191.222', 'nice', '-n', '10', 'python3',
        '/root/gpm-ts-update/20261106-baseline-01/restore_files_receiver_20261109.py'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    decrypt = subprocess.Popen([str(AGE), '--decrypt', '--identity', str(KEY),
        str(BACKUP / 'ts-files.tar.gz.age')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        receiver.stdin.write(json.dumps(manifest).encode() + b'\n')
        for block in iter(lambda: decrypt.stdout.read(1024 * 1024), b''):
            receiver.stdin.write(block)
        receiver.stdin.close()
        response = receiver.stdout.read()
        receiver.stderr.read()
        decrypt.stderr.read()
        if receiver.wait() or decrypt.wait():
            raise RuntimeError('Private file restore failed; raw diagnostics withheld')
    except Exception:
        # Stop only the local transport/decryption children; preserve remote data.
        for process in (decrypt, receiver):
            if process.poll() is None:
                process.terminate()
        raise
    report = json.loads(response)
    if report.get('regular_file_bytes') != total_bytes:
        raise RuntimeError('Restored byte count mismatch')
    report['new_local_key_decryption_verified'] = True
    report['all_ciphertext_hashes_verified'] = True
    (LOCAL / 'file-restore-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
