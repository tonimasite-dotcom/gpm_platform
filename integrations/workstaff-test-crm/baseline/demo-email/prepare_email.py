"""New overlay from verified demo-05; preserve email login and all debt guards."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
import re

def inject(data, method, body):
    pattern = rb"\bfunction\s+" + method.encode() + rb"\s*\([^{};]*?\)\s*(?::\s*[^{};]+)?\s*\{"
    matches = list(re.finditer(pattern, data))
    if len(matches) != 1:
        raise RuntimeError("METHOD_NOT_UNIQUE")
    pos = matches[0].end()
    return data[:pos] + ("\n        " + body + "\n").encode() + data[pos:]


OLD = Path('/root/gpm-ts-update/20261110-demo-05')
NEW = Path('/root/gpm-ts-update/20261110-demo-06')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    os.umask(0o077)
    if NEW.exists() or NEW.is_symlink() or TS.resolve() != TS:
        raise RuntimeError('NEW_EXACT_PACKAGE_REQUIRED')
    prior = json.loads((OLD / 'manifest.json').read_text())
    for row in prior['files']:
        if sha(TS / row['file']) != row['before_sha256'] or sha(OLD / 'runtime' / row['file']) != row['after_sha256']:
            raise RuntimeError('BASELINE_DRIFT')
    NEW.mkdir(mode=0o700)
    source = NEW / 'source-current'
    shutil.copytree(OLD / 'source-current', source)
    runtime = NEW / 'runtime'
    shutil.copytree(source, runtime)
    excluded = ['app/Http/Controllers/Auth/LoginController.php', 'app/Services/Release/GpmTsDemoLoginInbox.php']
    manifest = copy.deepcopy(prior)
    manifest['files'] = [r for r in manifest['files'] if r['file'] not in excluded]
    for row in manifest['files']:
        target = runtime / row['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OLD / 'runtime' / row['file'], target)
    guards = manifest['guards']['app/Services/WebKlexMailClient.php']
    del guards['sendVerifyMessage']
    name = 'app/Services/WebKlexMailClient.php'
    data = (source / name).read_bytes()
    for method, body in guards.items():
        data = inject(data, method, body)
    start = data.index(b'    public function sendVerifyMessage(')
    end = data.index(b'    /**', start)
    original = data[start:end]
    if original.count(b'Mail::send(') != 1:
        raise RuntimeError('EXACT_LOGIN_MAIL_CALL_REQUIRED')
    adapted = original.replace(b'Mail::send(', b'\\App\\Services\\Release\\GpmTsDemoPolicy::loginMailer($this->config)->send(', 1)
    data = data[:start] + adapted + data[end:]
    (runtime / name).write_bytes(data)
    policy = Path(__file__).parent / 'payload/GpmTsDemoPolicy.php'
    (runtime / 'app/Services/Release/GpmTsDemoPolicy.php').write_bytes(policy.read_bytes())
    (runtime / 'PRIVATE_DEMO_NO_DATABASE').write_text('Isolated transport tests only; no live DB or sync.\n')
    controller = excluded[0]
    if sha(TS / controller) != sha(source / controller) or sha(runtime / controller) != sha(source / controller):
        raise RuntimeError('LOGIN_CONTROLLER_MUST_REMAIN_UNCHANGED')
    debt = ['app/Console/Commands/CheckDebit.php', 'app/Console/Commands/CheckCustomerDebit.php', name]
    if sum((runtime / f).read_bytes().count(b'GPM_TS_DEBT_AUTOMATION_DISABLED_20261110') for f in debt) != 4:
        raise RuntimeError('ALL_DEBT_GUARDS_REQUIRED')
    for row in manifest['files']:
        row['before_sha256'] = sha(TS / row['file'])
        row['after_sha256'] = sha(runtime / row['file'])
        subprocess.run(['/opt/php74/bin/php', '-l', str(runtime / row['file'])], check=True, stdout=subprocess.DEVNULL)
    manifest.update(base=str(source), target=str(runtime), auth_changes=[], login_delivery='original email view and branch SMTP via isolated mailer; no controller changes',
                    local_inbox_installed=False, rebased_from_manifest_sha256=sha(OLD / 'manifest.json'))
    (NEW / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    preserved = {'passed': True, 'controller': controller, 'controller_sha256': sha(TS / controller),
                 'login_view': 'resources/views/mail/mail/verify.blade.php',
                 'login_view_sha256': sha(TS / 'resources/views/mail/mail/verify.blade.php'),
                 'controller_jwt_code_validation_unchanged': True, 'login_mail_diff_only_dedicated_mailer_call': True,
                 'local_inbox_installed': False, 'live_files_changed': False}
    if preserved['login_view_sha256'] != sha(runtime / preserved['login_view']):
        raise RuntimeError('LOGIN_VIEW_CHANGED')
    (NEW / 'auth-preserved.json').write_text(json.dumps(preserved, indent=2) + '\n')
    old_gpm = json.loads((OLD / 'gpm-equivalence.json').read_text())
    for row in old_gpm['byte_identical_files']:
        if sha(runtime / row['file']) != row['sha256'] or sha(TS / row['file']) != row['sha256']:
            raise RuntimeError('GPM_LOGIC_CHANGED')
    (NEW / 'gpm-equivalence.json').write_text(json.dumps(old_gpm, indent=2) + '\n')
    print(json.dumps({'passed': True, 'files': len(manifest['files']), 'manifest_sha256': sha(NEW / 'manifest.json'),
                      'debt_guards_retained': 4, 'login_controller_unchanged': True, 'live_files_changed': False}))


if __name__ == '__main__':
    main()
