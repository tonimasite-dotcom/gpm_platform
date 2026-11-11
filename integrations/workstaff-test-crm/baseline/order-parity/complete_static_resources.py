"""Copy a reviewed code resource into a NEW, stopped private candidate only.

No application bootstrap, database access, customer data or live writes.
The failed runtime is evidence and must never be passed as the destination.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
RESOURCE = 'app/Services/Order/approvedWorkerNameMarkers.json'
CONSUMER = 'app/Services/Order/ClientWorkerName.php'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    options = parser.parse_args()
    root = Path(options.root)
    if root.parent != Path('/root/gpm-ts-update') or not root.name.startswith('order-parity-') \
            or root.resolve() != root:
        raise RuntimeError('CANONICAL_PRIVATE_ROOT_REQUIRED')
    candidate = root / 'candidate'
    receipt = root / 'static-resource-completion.json'
    if receipt.exists() or (root / 'matched-job-pid.json').exists():
        raise RuntimeError('NEW_UNSTARTED_PRIVATE_RUNTIME_REQUIRED')
    preparation = json.loads((root / 'matched-preparation.json').read_text())
    if not preparation['fresh_activation_state_empty'] \
            or (candidate / 'storage/app/worker-calculation-activation.json').exists() \
            or (root / 'rehearsal-mysql/mysql.sock').exists():
        raise RuntimeError('UNSTARTED_MATCHED_COPY_REQUIRED')
    source = MAIN / RESOURCE
    target = candidate / RESOURCE
    for path in [MAIN, source, MAIN / CONSUMER, candidate, candidate / CONSUMER, target.parent]:
        if path.resolve() != path:
            raise RuntimeError('SYMLINK_REJECTED')
    if sha(MAIN / CONSUMER) != sha(candidate / CONSUMER):
        raise RuntimeError('CONSUMER_SOURCE_DRIFT')
    markers = json.loads(source.read_text())
    if not isinstance(markers, list) or not markers \
            or any(not isinstance(value, str) or len(value) > 1024 for value in markers):
        raise RuntimeError('EXPECTED_STATIC_MARKER_LIST_REQUIRED')
    if target.exists() or target.is_symlink():
        raise RuntimeError('NEW_RESOURCE_DESTINATION_REQUIRED')
    raw = source.read_bytes()
    if b'PRIVATE KEY' in raw or b'AGE-SECRET-KEY' in raw:
        raise RuntimeError('SECRET_RESOURCE_REJECTED')
    with target.open('xb') as stream:
        stream.write(raw)
    if sha(target) != sha(source):
        raise RuntimeError('RESOURCE_COPY_MISMATCH')
    report = {'completed': True, 'resource': RESOURCE, 'sha256': sha(target),
              'consumer_sha256': sha(candidate / CONSUMER),
              'main_read_only': True, 'live_changed': False, 'database_accessed': False}
    with receipt.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
