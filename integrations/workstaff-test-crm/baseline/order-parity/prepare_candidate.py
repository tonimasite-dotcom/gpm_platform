"""New private order-parity candidate. Never replace files in a live CRM."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
OUT = Path('/root/gpm-ts-update/order-parity-20261110-02')
AUDIT = Path('/root/gpm-ts-update/order-parity-audit-20261110-01')
UI = 'resources/js/pages/app/orders'
ALLOWED = {'.php', '.vue', '.js', '.json', '.css', '.scss', '.sass', '.less', '.xsd', '.png', '.svg', '.jpg', '.woff', '.woff2', '.ttf'}
# Keep the already verified safety implementation and the current login model.
PRESERVE = {'app/Services/WebKlexMailClient.php', 'app/Services/MapDataService.php',
            'app/Traits/sendSmsTrait.php', 'app/Http/Controllers/QtsmsSms/Src/SmsClient.php',
            'app/Models/User.php'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def checked_bytes(path, root):
    if path.resolve() != path or root not in path.parents:
        raise RuntimeError('NONCANONICAL_CODE_PATH')
    content = path.read_bytes()
    if b'PRIVATE KEY-----' in content or b'AGE-SECRET-KEY-' in content:
        raise RuntimeError('SECRET_SOURCE_REJECTED')
    return content


def copy_source(source, destination, root):
    data = checked_bytes(source, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def resolve_import(root, file, module):
    if module.startswith(('@/', '~/')):
        base = root / 'resources/js' / module[2:]
    elif module.startswith('.'):
        base = file.parent / module
    else:
        return None
    base = Path(os.path.normpath(str(base)))
    if root / 'resources/js' not in base.parents:
        return None
    for suffix in ['', '.vue', '.js', '.json', '/index.js']:
        p = Path(str(base) + suffix)
        if p.is_file():
            return p
    return None


def main():
    os.umask(0o077)
    if OUT.exists() or OUT.is_symlink() or TS.resolve() != TS or MAIN.resolve() != MAIN:
        raise RuntimeError('NEW_EXACT_PRIVATE_ROOT_REQUIRED')
    audit = json.loads((AUDIT / 'audit.json').read_text())
    dependencies = json.loads((AUDIT / 'dependencies.json').read_text())
    for name, row in audit['main'].items():
        if sha(MAIN / name) != row['sha256']:
            raise RuntimeError('MAIN_CHANGED_SINCE_AUDIT')
    for name, row in audit['ts'].items():
        if sha(TS / name) != row['sha256']:
            raise RuntimeError('TS_CHANGED_SINCE_AUDIT')
    OUT.mkdir(mode=0o700)
    source = OUT / 'source-ts'
    candidate = OUT / 'candidate'
    source.mkdir(mode=0o700)
    for folder in ['app', 'config', 'routes', 'resources', 'database/migrations']:
        for p in (TS / folder).rglob('*'):
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in ALLOWED:
                copy_source(p, source / p.relative_to(TS), TS)
    for name in ['artisan', 'bootstrap/app.php', 'composer.json', 'composer.lock', 'package.json',
                 'package-lock.json', 'webpack.mix.js', '.babelrc', '.eslintrc.js', 'public/index.php']:
        if (TS / name).is_file():
            copy_source(TS / name, source / name, TS)
    def omit_ts_order_ui(directory, names):
        return names if Path(directory) == source / UI else []
    shutil.copytree(source, candidate, ignore=omit_ts_order_ui)
    imports = []
    for p in (MAIN / UI).rglob('*'):
        if p.is_file() and p.suffix in ['.vue', '.js']:
            copy_source(p, candidate / p.relative_to(MAIN), MAIN)
            imports.append(p)
    copied_frontend = set()
    global_frontend = []
    translation_keys = set()
    while imports:
        p = imports.pop()
        name = p.relative_to(MAIN).as_posix()
        if name in copied_frontend:
            continue
        copied_frontend.add(name)
        text = p.read_text(errors='replace')
        translation_keys.update(re.findall(r'\$t(?:c)?\(\s*[\'"]([\w.]+)[\'"]', text))
        for module in re.findall(r'(?:from\s*|import\s*)[\'"]([^\'"]+)[\'"]', text):
            dependency = resolve_import(MAIN, p, module)
            if dependency is None:
                continue
            relative = dependency.relative_to(MAIN).as_posix()
            if relative in ['resources/js/router/index.js', 'resources/js/store/index.js', 'resources/js/app.js']:
                if sha(dependency) != sha(TS / relative):
                    global_frontend.append(relative)
                continue
            copy_source(dependency, candidate / relative, MAIN)
            imports.append(dependency)
    preserved = []
    credential_review = []
    for row in dependencies['backend']:
        name = row['file']
        if not row['differs']:
            continue
        if name in PRESERVE:
            preserved.append(name)
            continue
        data = checked_bytes(MAIN / name, MAIN)
        # Do not move embedded credentials from main, even into a private copy.
        values = re.findall(rb'(?:password|secret|api_key|access_token)[\'"]?\s*(?:=>|=)\s*([\'"])([^\r\n]*?)\1', data, re.I)
        if any(len(value) >= 12 and b' ' not in value and b'|' not in value and b'required' not in value for _, value in values):
            credential_review.append(name)
            continue
        copy_source(MAIN / name, candidate / name, MAIN)
    pending = dependencies['pending_migrations']
    for row in pending:
        name = 'database/migrations/' + row['migration'] + '.php'
        # Source proposal only, outside Laravel's migration directory. Adaptation
        # and data preservation tests are mandatory before anything can execute.
        copy_source(MAIN / name, OUT / 'migration-proposals' / (row['migration'] + '.php'), MAIN)
    for p in (candidate / 'resources/js/lang').glob('*.json'):
        upstream = MAIN / p.relative_to(candidate)
        if not upstream.is_file():
            continue
        a, b = json.loads(upstream.read_text()), json.loads(p.read_text())
        for key in sorted(translation_keys | {'resources.orders'}):
            parts = key.split('.')
            cursor = a
            for part in parts:
                if not isinstance(cursor, dict) or part not in cursor:
                    break
                cursor = cursor[part]
            else:
                target = b
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = cursor
        p.write_text(json.dumps(b, ensure_ascii=False, indent=4) + '\n')
    changed = []
    for p in candidate.rglob('*'):
        if p.is_file():
            name = p.relative_to(candidate).as_posix()
            before, after = sha(source / name), sha(p)
            if before != after:
                changed.append({'file': name, 'before_sha256': before, 'after_sha256': after})
    old_ui = {p.relative_to(source).as_posix() for p in (source / UI).rglob('*') if p.is_file()}
    new_ui = {p.relative_to(candidate).as_posix() for p in (candidate / UI).rglob('*') if p.is_file()}
    for name in new_ui:
        if sha(candidate / name) != sha(MAIN / name):
            raise RuntimeError('ORDER_UI_NOT_EXACT_MAIN')
    for name in ['app/Http/Controllers/Auth/LoginController.php', 'config/auth.php', 'app/Console/Kernel.php',
                 'app/Services/Release/GpmTsDemoPolicy.php', 'app/Services/Release/GpmTsDemoTransport.php']:
        if sha(candidate / name) != sha(TS / name):
            raise RuntimeError('AUTH_OR_SAFETY_CHANGED')
    # Syntax only. Candidate has no .env, vendor or runnable DB configuration.
    linted = 0
    for p in candidate.rglob('*.php'):
        result = subprocess.run(['/opt/php74/bin/php', '-l', str(p)], capture_output=True)
        if result.returncode:
            raise RuntimeError('PHP74_CANDIDATE_LINT_FAILED')
        linted += 1
    report = {'prepared': True, 'deployable': False, 'candidate': str(candidate),
              'changed_files': changed, 'order_ui_files': len(new_ui), 'order_ui_exact_main': True,
              'ts_only_ui_files_not_in_candidate': sorted(old_ui - new_ui),
              'preserved_auth_and_transport_files': preserved,
              'credential_review_required': credential_review, 'global_frontend_review': global_frontend,
              'pending_before_execution': ['Review shared frontend/API changes', 'Adapt order routes and keep service GPM API without TS-only UI',
                  'Review preserved User model dependencies without auth replacement', 'Review permissions and observers',
                  'Select and adapt only necessary migrations; never release emails or transfer banking cards',
                  'Fresh encrypted TS backup and verified isolated restore', 'Build frontend and run role/financial/GPM/transport acceptance'],
              'migration_proposals_not_executed': len(pending), 'php74_files_linted': linted,
              'live_files_changed': False, 'database_accessed': False, 'main_crm_read_only': True}
    (OUT / 'candidate-proposal.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'prepared': True, 'deployable': False, 'changed_files': len(changed),
                      'order_ui_files': len(new_ui), 'order_ui_exact_main': True,
                      'ts_only_ui_files_not_in_candidate': len(old_ui - new_ui),
                      'credential_review_required': len(credential_review),
                      'php74_files_linted': linted, 'live_files_changed': False}))


if __name__ == '__main__':
    main()
