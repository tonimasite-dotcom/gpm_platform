#!/usr/bin/env python3
"""Prepare only debt automation suppression, using the already verified backup."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time

TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
WORK = Path('/root/gpm-ts-update/20261110-debt-off-01')
BASE = Path('/root/gpm-ts-update/20261106-baseline-01/source-ts')
BACKUP = Path('/root/gpm-ts-update/20261110-demo-04/code-backup')
METHODS = {'app/Console/Commands/CheckDebit.php': {'handle': '0', 'sendMail': ''},
           'app/Console/Commands/CheckCustomerDebit.php': {'handle': '0'},
           'app/Services/WebKlexMailClient.php': {'sendDebitMessage': ''}}
PROTECTED = ['.env', 'config/auth.php', 'app/Console/Kernel.php', 'routes/api.php',
             'app/Http/Controllers/Auth/LoginController.php', 'app/Providers/AppServiceProvider.php',
             'app/Services/Order/GpmAppOrderSync.php', 'app/Services/Order/GpmAppOrderPublisher.php',
             'app/Services/Order/GpmWorkerRateRules.php', 'app/Services/Order/GpmLogistOrderGuard.php',
             'app/Http/Controllers/Order/GpmWorkerRateController.php']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    os.umask(0o077)
    if TS.resolve() != TS or WORK.exists() or WORK.is_symlink():
        raise RuntimeError('NEW_EXACT_DEBT_WORKSPACE_REQUIRED')
    backup = json.loads((BACKUP / 'verification.json').read_text())
    restored = json.loads((BACKUP.parent / 'code-backup-restore.json').read_text())
    if (sha(Path(backup['artifact'])) != backup['sha256'] or not restored['passed']
        or restored['encrypted_sha256'] != backup['sha256']
        or not 0 <= time.time() - (BACKUP / 'verification.json').stat().st_mtime < 86400):
        raise RuntimeError('FRESH_VERIFIED_CODE_BACKUP_REQUIRED')
    rows = []; planned = {}
    for name, methods in METHODS.items():
        live = TS / name
        if live.resolve() != live or sha(live) != sha(BASE / name):
            raise RuntimeError('TS_SOURCE_CHANGED_REVIEW_REQUIRED')
        old = live.read_bytes(); data = old
        if next(x for x in backup['files'] if x['file'] == name)['sha256'] != sha(live):
            raise RuntimeError('BACKUP_DOES_NOT_COVER_CURRENT_FILE')
        for method, value in methods.items():
            expression = rb'\bfunction\s+' + method.encode() + rb'\s*\([^{};]*?\)\s*(?::\s*[^{};]+)?\s*\{'
            matches = list(re.finditer(expression, data))
            if len(matches) != 1:
                raise RuntimeError('METHOD_ANCHOR_NOT_UNIQUE')
            guard = ("\n        // GPM_TS_DEBT_AUTOMATION_DISABLED_20261110: no calculation or debtor email.\n"
                     "        if (realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'\n"
                     "            || rtrim((string) config('app.url'), '/') === 'https://ts.workstaffcrm.ru') {\n"
                     "            return" + (' ' + value if value else '') + ";\n        }\n").encode()
            position = matches[0].end()
            data = data[:position] + guard + data[position:]
        planned[name] = data
        rows.append({'file': name, 'before_sha256': hashlib.sha256(old).hexdigest(),
                     'after_sha256': hashlib.sha256(data).hexdigest(), 'guarded_methods': list(methods)})
    WORK.mkdir(mode=0o700)
    for name, data in planned.items():
        path = WORK / 'runtime' / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(['/opt/php74/bin/php', '-l', str(path)], check=True, stdout=subprocess.DEVNULL)
    receipt = {'files': rows, 'protected_files': {name: sha(TS / name) for name in PROTECTED},
               'sync_cron_sha256': sha(Path('/etc/cron.d/gpm-test-crm-sync')),
               'backup_artifact': backup['artifact'], 'backup_sha256': backup['sha256'],
               'debt_calculation_and_email_disabled_in_overlay': True,
               'authorization_changes': False, 'schema_changes': False, 'live_files_changed': False}
    (WORK / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'prepared': True, 'files': len(rows), 'guarded_methods': 4,
                      'manifest_sha256': sha(WORK / 'manifest.json'), 'live_files_changed': False}))


if __name__ == '__main__':
    main()
