"""Prepare demo/email isolation ONLY in the existing synthetic Laravel 13 candidate.

No live apply mode. Auth, JWT, permissions, schema and cron remain untouched.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

BASE = Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE = BASE / 'rootfs/work/crm-private-01'
PRIOR = Path('/root/gpm-ts-update/20261110-demo-06/manifest.json')
BACKUP = BASE / 'demo-adaptation-20261116-01'
PROTECTED = ['app/Http/Controllers/Auth/LoginController.php', 'config/auth.php',
             'app/Providers/AuthServiceProvider.php', 'app/Console/Kernel.php',
             'routes/api.php', '.env']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inject(data, method, body):
    matches = list(re.finditer(rb'\bfunction\s+' + method.encode() +
        rb'\s*\([^{};]*?\)\s*(?::\s*[^{};]+)?\s*\{', data))
    if len(matches) != 1:
        raise RuntimeError('METHOD_NOT_UNIQUE:' + method)
    position = matches[0].end()
    return data[:position] + ('\n        ' + body + '\n').encode() + data[position:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if CANDIDATE.resolve() != CANDIDATE or not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('EXISTING_SYNTHETIC_CANDIDATE_REQUIRED')
    env = (CANDIDATE/'.env').read_text()
    if not re.search(r'^APP_ENV=testing\s*$', env, re.M) or not re.search(r'^DB_DATABASE=bot_fixture\s*$', env, re.M):
        raise RuntimeError('SYNTHETIC_DATABASE_ONLY')
    if BACKUP.exists():
        raise RuntimeError('ADAPTATION_REPORT_ALREADY_EXISTS_DO_NOT_REAPPLY')
    protected = {name: sha((CANDIDATE/name).read_bytes()) for name in PROTECTED}
    guards = json.loads(PRIOR.read_text())['guards']
    # The current upstream CheckDebit no longer has its former SMTP method.
    del guards['app/Console/Commands/CheckDebit.php']['sendMail']
    for filename in ['DebitCalculate.php', 'DebitNotify.php', 'DebitRemindersDryRun.php']:
        guards['app/Console/Commands/' + filename] = {
            'handle': "\\App\\Services\\Release\\GpmTsDemoPolicy::suppress('daily_mail'); return 0;"}
    changes = {}
    missing = []
    for name, methods in guards.items():
        path = CANDIDATE/name
        if path.resolve() != path or path.is_symlink():
            raise RuntimeError('REGULAR_CANDIDATE_FILE_REQUIRED:' + name)
        data = path.read_bytes()
        if b'GpmTsDemoPolicy' in data:
            raise RuntimeError('DEMO_ALREADY_PRESENT_REVIEW_REQUIRED:' + name)
        for method, body in methods.items():
            if not re.search(rb'\bfunction\s+' + method.encode() + rb'\s*\(', data):
                missing.append(name + ':' + method)
                continue
            data = inject(data, method, body)
        changes[name] = data
    if missing:
        print(json.dumps({'status': 'METHOD_REVIEW_REQUIRED', 'missing_methods': missing}))
        return
    name = 'app/Services/WebKlexMailClient.php'
    data = changes[name]
    start = data.index(b'    public function sendVerifyMessage(')
    end = data.find(b'    /**', start)
    if end < 0:
        raise RuntimeError('LOGIN_MAIL_METHOD_BOUNDARY_REQUIRED')
    original = data[start:end]
    if original.count(b'Mail::send(') != 1:
        raise RuntimeError('EXACT_EXISTING_LOGIN_MAIL_CALL_REQUIRED')
    data = data[:start] + original.replace(b'Mail::send(',
        b'\\App\\Services\\Release\\GpmTsDemoPolicy::loginMailer($this->config)->send(', 1) + data[end:]
    # New upstream debtor mail paths must stop before reading attachments or mutating state.
    for method in ['sendVerifiedDebitMessage', 'sendPartialPaymentInquiry']:
        data = inject(data, method,
            "\\App\\Services\\Release\\GpmTsDemoPolicy::suppress('daily_mail'); return 'rejected';")
    changes[name] = data
    for filename in ['GpmTsDemoPolicy.php', 'GpmTsDemoTransport.php']:
        name = 'app/Services/Release/' + filename
        if (CANDIDATE/name).exists():
            raise RuntimeError('NEW_POLICY_FILE_ALREADY_EXISTS')
        changes[name] = (Path(__file__).parent/'payload'/filename).read_bytes()
    rows = [{'file': name, 'before_sha256': sha((CANDIDATE/name).read_bytes()) if (CANDIDATE/name).is_file() else None,
             'after_sha256': sha(data)} for name, data in changes.items()]
    receipt = {'private_synthetic_only': True, 'live_apply_supported': False,
               'files': rows, 'protected_hashes': protected, 'applied': False}
    if args.apply:
        BACKUP.mkdir(mode=0o700)
        for row in rows:
            path = CANDIDATE/row['file']
            if (sha(path.read_bytes()) if path.is_file() else None) != row['before_sha256']:
                raise RuntimeError('SOURCE_DRIFT')
        for name, data in changes.items():
            path = CANDIDATE/name
            if path.exists():
                backup = BACKUP/'before'/name
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(path.read_bytes())
            path.write_bytes(data)
        if protected != {name: sha((CANDIDATE/name).read_bytes()) for name in PROTECTED}:
            raise RuntimeError('PROTECTED_FILE_CHANGED')
        receipt['applied'] = True
        (BACKUP/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
