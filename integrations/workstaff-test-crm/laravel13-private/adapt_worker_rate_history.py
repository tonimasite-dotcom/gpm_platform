"""Adapt only a marked synthetic Laravel 13 candidate; default is read-only."""
import argparse
import hashlib
import json
import pathlib

BEFORE_SHA256 = '1add8b5bf830fc32f56a7ed2bc7689a32f07d2aebbb8d2607d10682c59069595'
AFTER_SHA256 = '5f2fff42688da13c3173fce6e43a212f9e6254b94ba70ce8cc882760530efe83'
RELATIVE_FILE = 'app/Http/Controllers/Order/GpmWorkerRateController.php'
OLD = """app(HistoryOrderService::class)->addUpdatedHistory($current, [
                    'work_type_id' => $current->work_type_id, 'workers_cost' => $rate,
                ]);"""
NEW = """app(HistoryOrderService::class)->addUpdatedHistory($current, array_merge($current->toArray(), [
                    'work_type_id' => $current->work_type_id, 'workers_cost' => $rate,
                ]), ['workers_cost' => 'Worker hourly rate']);"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=pathlib.Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.candidate.resolve(strict=True)
    if not (root / 'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('Synthetic candidate marker is required')
    env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines()
               if '=' in line and not line.lstrip().startswith('#'))
    if env.get('APP_ENV') != 'testing' or env.get('DB_DATABASE') != 'bot_fixture':
        raise RuntimeError('Only the synthetic testing database is supported')
    target = root / RELATIVE_FILE
    if target.is_symlink() or root not in target.resolve(strict=True).parents:
        raise RuntimeError('Controller must stay inside the private candidate')
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest == AFTER_SHA256:
        print(json.dumps({'status': 'already_adapted', 'sha256': digest, 'written': False}))
        return
    if digest != BEFORE_SHA256 or raw.decode().count(OLD) != 1:
        raise RuntimeError('Controller changed; review the new source before adapting')
    changed = raw.decode().replace(OLD, NEW, 1).encode()
    if hashlib.sha256(changed).hexdigest() != AFTER_SHA256:
        raise RuntimeError('Unexpected adaptation result')
    if args.apply:
        backup = root / 'private-worker-rate-controller-before-history.php'
        with backup.open('xb') as stream:
            stream.write(raw)
        backup.chmod(0o600)
        target.write_bytes(changed)
    print(json.dumps({'status': 'adapted' if args.apply else 'planned',
                      'before_sha256': digest, 'after_sha256': AFTER_SHA256,
                      'written': args.apply}))


if __name__ == '__main__':
    main()
