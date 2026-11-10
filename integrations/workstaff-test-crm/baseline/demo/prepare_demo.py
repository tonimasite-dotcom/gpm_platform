#!/usr/bin/env python3
"""One-time new private overlay from saved TS. No live apply, SQL or bootstrap."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

SOURCE = Path('/root/gpm-ts-update/20261106-baseline-01/source-ts')
TARGET = Path('/root/gpm-ts-update/20261110-demo-05')
POLICY = r'\App\Services\Release\GpmTsDemoPolicy'


def guards():
    rows = {}

    def add(file, methods, channel, action='deny'):
        for method in methods.split():
            body = f"{POLICY}::{action}('{channel}');"
            if action == 'suppress':
                body += ' return 0;' if method == 'handle' else ' return;'
            rows.setdefault('app/' + file + '.php', {})[method] = body

    add('Console/Commands/CheckDebit', 'handle sendMail', 'daily_mail', 'suppress')
    for command in ['CheckCustomerDebit', 'ParseEmailLead', 'RefreshBankingToken',
                    'CheckWorkerIsActive', 'setStatementsAndGetTransactionsFromApi']:
        add('Console/Commands/' + command, 'handle', 'background', 'suppress')
    add('Services/WebKlexMailClient', 'sendDebitMessage', 'daily_mail', 'suppress')
    rows['app/Services/WebKlexMailClient.php']['sendVerifyMessage'] = r'return \App\Services\Release\GpmTsDemoLoginInbox::capture($user);'
    add('Services/WebKlexMailClient', 'connectClient', 'imap')
    for file in ['Services/Mail/MailService', 'Services/Mails/MailService']:
        add(file, 'connectImapServer deleteMessage moveMessage draft', 'imap')
        add(file, 'sendMessage', 'mail')
        rows['app/' + file + '.php']['setSmtpConfig'] = f'return {POLICY}::installNullMailer();'
    rows['app/Services/WebKlexMailClient.php']['setSmtpConfig'] = f'return {POLICY}::installNullMailer();'
    add('Services/Mail/MailService', 'getMessages getMessage getCountUnseenMessages', 'imap')
    add('Services/Mails/MailService', 'parseMessages getMessageOld send getCountUnseenMessages', 'imap')
    add('Services/Mails/ParsedMailService', 'parse parseFolder', 'imap')
    add('Services/Mail/ParseEmailService', 'parse configureAndTry', 'imap')
    add('Jobs/ParseMailBox', 'handle', 'imap', 'suppress')
    add('Traits/sendSmsTrait', 'sendSms', 'sms')
    add('Http/Controllers/QtsmsSms/Src/SmsClient', 'sendRequest', 'sms')
    add('Services/Dadata/ClientBase', 'get post', 'dadata')
    add('Services/MapDataService', 'getNearMetroId getLocation', 'geocode')
    add('Traits/getCoordinateTrait', 'getGeoResponse', 'geocode')
    # Address creation keeps its supplied fields without inventing coordinates.
    rows['app/Traits/getCoordinateTrait.php']['getGeoResponse'] = f"{POLICY}::suppress('geocode'); return false;"
    add('Services/Calls/CallService', 'makeCall', 'calls')
    add('Services/Banking/BankingService', 'getRedirectingUrl getJWTLink', 'bank')
    add('Services/Settings/BankingSettingsService', 'getRedirectingUrl getJWTLink saveCode refreshToken', 'bank')
    add('Services/Payment/ManagerPaymentService',
        'createStatementOOOOnApi createStatementIPOnApi addStatementFromApi getAllTochkaPayments getAllAlfaPayments getToken getAllTinkoffPayments', 'bank')
    add('Http/Controllers/Payment/TinkofWebhookController',
        'webhook alfaWebhook tochkaWebhook getAllTinkoffPayments getAllAlfaPayments getToken addStatementFromApi', 'bank')
    rows['app/Providers/AppServiceProvider.php'] = {'boot': f'{POLICY}::register($this->app);'}
    return rows


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inject(data, method, body):
    pattern = rb'\bfunction\s+' + method.encode() + rb'\s*\([^{};]*?\)\s*(?::\s*[^{};]+)?\s*\{'
    matches = list(re.finditer(pattern, data))
    if len(matches) != 1:
        raise RuntimeError('METHOD_NOT_UNIQUE:' + method)
    pos = matches[0].end()
    return data[:pos] + ('\n        ' + body + '\n').encode() + data[pos:]


def main():
    os.umask(0o077)
    if SOURCE.resolve() != SOURCE or TARGET.exists() or TARGET.is_symlink() or TARGET.parent.resolve() != TARGET.parent:
        raise RuntimeError('NEW_PRIVATE_TARGET_REQUIRED')
    rules = guards()
    # Validate every insertion before creating any directory.
    modified = {}
    for name, methods in rules.items():
        source = SOURCE / name
        if not source.is_file() or source.resolve() != source:
            raise RuntimeError('SOURCE_MISSING_OR_SYMLINK:' + name)
        data = source.read_bytes()
        for method, body in methods.items():
            data = inject(data, method, body)
        modified[name] = data
    login_name = 'app/Http/Controllers/Auth/LoginController.php'
    login = (SOURCE / login_name).read_bytes()
    attempt = b"$token = $this->guard()->attempt($this->credentials($request), $request->filled('remember'));"
    fixed = br'''$guard = $this->guard();
        // JWTGuard's second parameter means perform-login, not remember-me.
        $token = $guard instanceof \Tymon\JWTAuth\JWTGuard
            ? $guard->attempt($this->credentials($request))
            : $guard->attempt($this->credentials($request), $request->filled('remember'));'''
    unscoped = b"'max:255', 'exists:users,remember_token'"
    scoped = br"'max:255', \Illuminate\Validation\Rule::exists('users', 'remember_token')->where('email', (string) $request->input('email'))"
    if login.count(attempt) != 1 or login.count(unscoped) != 1:
        raise RuntimeError('LOGIN_FIX_ANCHORS_NOT_UNIQUE')
    login = login.replace(attempt, fixed, 1).replace(unscoped, scoped, 1)
    before_verify, separator, verify = login.partition(b'public function verify(Request $request)')
    challenge = b"$user->update(['remember_token' => Str::random(10)]);"
    if not separator or verify.count(challenge) != 1:
        raise RuntimeError('VERIFY_CHALLENGE_ROTATION_NOT_UNIQUE')
    verify = verify.replace(challenge, challenge + br'\n            \App\Services\Release\GpmTsDemoLoginInbox::consume($user);'.replace(br'\n', b'\n'), 1)
    modified[login_name] = before_verify + separator + verify
    TARGET.mkdir(mode=0o700)
    runtime = TARGET / 'runtime'
    shutil.copytree(SOURCE, runtime)
    (runtime / 'PRIVATE_DEMO_NO_DATABASE').write_text('Transport acceptance: no DB. Auth acceptance: only verified saved private recovery DB; no live DB, scheduler or external network.\n')
    for name, data in modified.items():
        (runtime / name).write_bytes(data)
    release = runtime / 'app/Services/Release'
    release.mkdir(parents=True, exist_ok=True)
    helpers = ['GpmTsDemoPolicy.php', 'GpmTsDemoTransport.php', 'GpmTsDemoLoginInbox.php']
    for name in helpers:
        shutil.copyfile(Path(__file__).parent / 'payload' / name, release / name)
    manifest = {'base': str(SOURCE), 'target': str(runtime), 'live_files_changed': False,
                'schema_changes': False, 'database_accessed': False, 'guards': rules, 'files': []}
    manifest['auth_changes'] = ['Keep password, captcha, enabled flag, roles and challenge checks',
                                'Fix JWT remember argument; scope challenge to requested email',
                                'Encrypt generated challenges for root-only SSH/local delivery',
                                'Mark captured challenge consumed after successful normal verify']
    changed = set(modified) | {'app/Services/Release/' + x for x in helpers}
    for name in sorted(changed):
        subprocess.run(['/opt/php74/bin/php', '-l', str(runtime / name)], check=True, stdout=subprocess.DEVNULL)
        manifest['files'].append({'file': name, 'before_sha256': sha(SOURCE / name) if (SOURCE / name).exists() else None,
                                  'after_sha256': sha(runtime / name)})
    for p in SOURCE.rglob('*'):
        if p.is_file() and p.relative_to(SOURCE).as_posix() not in changed:
            if sha(p) != sha(runtime / p.relative_to(SOURCE)):
                raise RuntimeError('UNEXPECTED_FILE_CHANGE')
    manifest['all_other_saved_ts_files_unchanged'] = True
    (TARGET / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'private_target': str(TARGET), 'changed_files': len(changed),
                      'guarded_methods': sum(map(len, rules.values())), 'lint_passed': True,
                      'all_other_saved_ts_files_unchanged': True, 'live_files_changed': False}))


if __name__ == '__main__':
    raise SystemExit('USE_REBASE_AFTER_DEBT_OFF_TO_PRESERVE_DEPLOYED_GUARDS')
