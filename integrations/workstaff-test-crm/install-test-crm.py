"""Install only into the inspected test CRM. Dry run unless --apply is given.

Never enables synchronization, writes .env, schedules jobs, or changes a DB.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone


ROOT = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PUBLISHER = 'app/Services/Order/GpmAppOrderPublisher.php'
EXPECTED_PUBLISHER = '76843060b1599ad13ee8f21292825d051678cfc036280c9c5c41cdaa264422ba'
FILES = [PUBLISHER, 'app/Services/Order/GpmAppOrderSync.php',
         'app/Services/Order/GpmOrderSyncPlan.php', 'app/Console/Commands/SyncGpmAppOrders.php']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_path(relative):
    path = ROOT / relative
    if path.is_symlink() or ROOT not in path.resolve().parents:
        raise RuntimeError('Refusing a path outside the test CRM: ' + relative)
    return path


def atomic_copy(source, target, owner, mode):
    descriptor, temporary = tempfile.mkstemp(prefix='.gpm-sync-', dir=str(target.parent))
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, owner.st_uid, owner.st_gid)
        os.chmod(temporary, mode)
        os.replace(temporary, str(target))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
bundle = Path(__file__).resolve().parent
if ROOT.resolve() != ROOT or not ROOT.is_dir():
    raise RuntimeError('Unexpected test CRM directory')
for relative in FILES:
    subprocess.run(['php', '-l', str(bundle / relative)], check=True)
for test in ('sync_plan_test.php', 'sync_service_test.php'):
    subprocess.run(['php', str(bundle / 'tests' / test)], check=True)

# Bootstrap only the test installation, printing no configuration secrets.
subprocess.run(['php', '-r',
    "require '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/vendor/autoload.php'; "
    "$app = require '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/bootstrap/app.php'; "
    "$app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); "
    "if (rtrim(config('app.url'), '/') !== 'https://ts.workstaffcrm.ru') { exit(2); } "
    "if (filter_var(env('GPM_APP_ORDER_SYNC_ENABLED', false), FILTER_VALIDATE_BOOLEAN)) { exit(3); }"
], check=True)

plan = []
for relative in FILES:
    destination = target_path(relative)
    current = digest(destination) if destination.exists() else None
    desired = digest(bundle / relative)
    if current == desired:
        continue
    if relative == PUBLISHER:
        if current != EXPECTED_PUBLISHER:
            raise RuntimeError('Publisher changed since inspection; review its current version first')
    elif current is not None:
        raise RuntimeError('Existing sync file must be reviewed before replacement: ' + relative)
    plan.append({'path': relative, 'before': current, 'after': desired})
print(json.dumps({'test_crm_root': str(ROOT), 'changes': plan, 'apply': args.apply}, indent=2))
if not args.apply or not plan:
    raise SystemExit(0)

owner = (ROOT / 'storage/app').stat()
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup = target_path('storage/app/gpm-sync-backups/' + stamp)
backup.mkdir(mode=0o700, parents=True, exist_ok=False)
os.chown(str(backup), owner.st_uid, owner.st_gid)
applied = []
try:
    for change in plan:
        destination = target_path(change['path'])
        if change['before'] is not None:
            saved = backup / change['path']
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(destination), str(saved))
            os.chown(str(saved), owner.st_uid, owner.st_gid)
            os.chmod(str(saved), 0o600)
            if digest(saved) != change['before']:
                raise RuntimeError('Backup verification failed')
    (backup / 'manifest.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    for change in plan:
        destination = target_path(change['path'])
        current = digest(destination) if destination.exists() else None
        if current != change['before']:
            raise RuntimeError('CRM source changed during installation')
        mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
        atomic_copy(bundle / change['path'], destination, owner, mode)
        applied.append(change)
        if digest(destination) != change['after']:
            raise RuntimeError('Installed file verification failed')
except BaseException:
    for change in reversed(applied):
        destination = target_path(change['path'])
        if digest(destination) != change['after']:
            raise RuntimeError('Rollback stopped because installed source changed')
        if change['before'] is None:
            destination.unlink()
        else:
            atomic_copy(backup / change['path'], destination, owner, 0o644)
    raise
print('Installed; sync remains disabled. Verified source backup: ' + str(backup))
