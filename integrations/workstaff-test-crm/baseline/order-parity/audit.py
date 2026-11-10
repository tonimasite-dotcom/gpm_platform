"""Read-only order code inventory; never bootstrap either CRM or connect to DB."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re

MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
SAVED = Path('/root/gpm-ts-update/20261106-baseline-01')
OUT = Path('/root/gpm-ts-update/order-parity-audit-20261110-01')
FORM = 'resources/js/pages/app/orders'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def selected(root):
    names = {p.relative_to(root).as_posix() for p in (root / FORM).rglob('*')
             if p.is_file() and p.suffix in ['.vue', '.js'] and not p.is_symlink()}
    for p in (root / 'app').rglob('*.php'):
        name = p.relative_to(root).as_posix()
        if 'order' in name.lower() and not p.is_symlink():
            names.add(name)
    for p in (root / 'database/migrations').glob('*.php'):
        if re.search(r'order|tarif|price|worker.*rate', p.name, re.I):
            names.add(p.relative_to(root).as_posix())
    names |= {x for x in ['routes/api.php', 'routes/web.php', 'package.json', 'webpack.mix.js', 'composer.lock',
                          'public/mix-manifest.json'] if (root / x).is_file()}
    return sorted(names)


def widgets(path):
    text = path.read_text(errors='replace')
    rows = []
    for match in re.finditer(r'<[a-zA-Z][^>]*?\bv-model(?:\.[\w]+)*\s*=\s*([\'"])(.*?)\1[^>]*>', text, re.S):
        tag = match.group(0)
        row = {'model': match.group(2), 'line': text.count('\n', 0, match.start()) + 1}
        for name in ['label', ':label', 'v-if', 'v-show', ':readonly', ':disabled', 'name', 'type']:
            attr = re.search(r'(?<![\w:-])' + re.escape(name) + r'\s*=\s*([\'"])(.*?)\1', tag, re.S)
            if attr:
                row[name] = ' '.join(attr.group(2).split())
        row['readonly_literal'] = bool(re.search(r'\sreadonly(?:\s|/?>)', tag))
        rows.append(row)
    return rows


def inventory(root):
    if root.resolve() != root:
        raise RuntimeError('CANONICAL_ROOT_REQUIRED')
    rows = {}
    for name in selected(root):
        path = root / name
        if path.resolve() != path:
            raise RuntimeError('CODE_SYMLINK_REJECTED')
        row = {'sha256': sha(path)}
        if name.startswith(FORM + '/'):
            row['widgets'] = widgets(path)
        rows[name] = row
    return rows


def main():
    os.umask(0o077)
    if OUT.exists() or OUT.is_symlink():
        raise RuntimeError('NEW_AUDIT_OUTPUT_REQUIRED')
    main = inventory(MAIN)
    ts = inventory(TS)
    saved_main = inventory(SAVED / 'source-main')
    candidate = inventory(SAVED / 'candidate')
    differences = []
    for name in sorted(set(main) | set(ts)):
        a, b = main.get(name, {}), ts.get(name, {})
        if a.get('sha256') == b.get('sha256'):
            continue
        row = {'file': name, 'main_sha256': a.get('sha256'), 'ts_sha256': b.get('sha256'),
               'candidate_sha256': candidate.get(name, {}).get('sha256')}
        if name.startswith(FORM + '/'):
            a_models = {r['model'] for r in a.get('widgets', [])}
            b_models = {r['model'] for r in b.get('widgets', [])}
            row.update(main_only_models=sorted(a_models - b_models), ts_only_models=sorted(b_models - a_models))
        differences.append(row)
    main_drift = [name for name in sorted(set(main) | set(saved_main))
                  if main.get(name, {}).get('sha256') != saved_main.get(name, {}).get('sha256')]
    # Check that every selected main file is still exactly the file read above.
    if any(sha(MAIN / name) != row['sha256'] for name, row in main.items()):
        raise RuntimeError('MAIN_CHANGED_DURING_READ')
    report = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'main': main, 'ts': ts, 'differences': differences, 'main_drift_since_saved_reference': main_drift,
              'main_crm_read_only': True, 'live_files_changed': False, 'laravel_bootstrapped': False,
              'database_accessed': False, 'candidate_applied': False}
    OUT.mkdir(mode=0o700)
    (OUT / 'audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    summary = {'passed': True, 'main_code_files': len(main), 'ts_code_files': len(ts),
               'different_files': len(differences), 'main_drift_since_saved_reference': main_drift,
               'form_field_differences': [r for r in differences if r.get('main_only_models') or r.get('ts_only_models')],
               'live_files_changed': False, 'main_crm_read_only': True}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()
