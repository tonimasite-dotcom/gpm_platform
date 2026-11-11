"""Resolve migration helper classes in the private candidate, including grouped imports."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path('/root/gpm-ts-update/order-parity-20261110-02')
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')


def references(text):
    result = set(re.findall(r'(?<![\w])\\?(App\\[\w\\]+)', text))
    for prefix, group in re.findall(r'\buse\s+(App\\[\w\\]+)\\\s*\{([^}]+)\}', text):
        for item in group.split(','):
            result.add(prefix + '\\' + item.strip().split()[0])
    namespace = re.search(r'^\s*namespace\s+([^;]+);', text, re.M)
    if namespace:
        # PHP resolves an unqualified static call/type to the current namespace
        # unless a use declaration supplies an alias. These helpers need not
        # have a use statement (for example PaymentReference::...).
        aliases = set()
        for imported, alias in re.findall(r'^\s*use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;', text, re.M):
            aliases.add(alias or imported.split('\\')[-1])
        for _, group in re.findall(r'\buse\s+([\w\\]+)\\\s*\{([^}]+)\}', text):
            for item in group.split(','):
                parts = re.split(r'\s+as\s+', item.strip())
                aliases.add(parts[-1].split('\\')[-1])
        symbols = set(re.findall(r'(?<![\w\\])([A-Z]\w*)\s*::', text))
        symbols.update(re.findall(r'\b(?:new|extends|implements|instanceof)\s+([A-Z]\w*)\b', text))
        symbols.update(re.findall(r'(?<![\w\\])([A-Z]\w*)\s+\$\w+', text))
        symbols.update(re.findall(r'\)\s*:\s*\??([A-Z]\w*)\b', text))
        result.update(namespace.group(1) + '\\' + symbol for symbol in symbols - aliases)
    return result


def main():
    candidate = ROOT / 'candidate'
    target = ROOT / 'migration-class-dependencies.json'
    if target.exists():
        raise RuntimeError('NEW_MIGRATION_DEPENDENCY_PASS_REQUIRED')
    index = {}
    for p in (MAIN / 'app').rglob('*.php'):
        text = p.read_text(errors='replace')
        ns = re.search(r'^\s*namespace\s+([^;]+);', text, re.M)
        cls = re.search(r'^\s*(?:(?:final|abstract)\s+)?(?:class|trait|interface)\s+(\w+)', text, re.M)
        if ns and cls:
            index[ns.group(1) + '\\' + cls.group(1)] = p
    prepared = json.loads((ROOT / 'private-runtime-preparation.json').read_text())
    queue = [candidate / 'database/migrations' / name for name in prepared['migration_recipes']]
    # Also recheck existing order dependencies for grouped use statements.
    queue += list((candidate / 'app/Services/Order').glob('*.php'))
    queue += list((candidate / 'app/Observers').glob('*Order*.php'))
    safety = json.loads(Path('/root/gpm-ts-update/20261110-demo-06/manifest.json').read_text())
    preserve = {r['file'] for r in safety['files']} | {'app/Http/Controllers/Auth/LoginController.php', 'app/Http/Controllers/BotController.php'}
    copied, seen, blocked = [], set(), []
    while queue:
        p = queue.pop()
        marker = str(p)
        if marker in seen:
            continue
        seen.add(marker)
        for cls in references(p.read_text(errors='replace')):
            if cls not in index:
                continue
            source = index[cls]
            name = source.relative_to(MAIN).as_posix()
            if name in preserve:
                continue
            data = source.read_bytes()
            literals = re.findall(rb'(?:password|secret|api_key|access_token)[\'"]?\s*(?:=>|=)\s*([\'"])([^\r\n]*?)\1', data, re.I)
            if any(len(v) >= 12 and b' ' not in v and b'|' not in v and b'required' not in v for _, v in literals):
                blocked.append(name)
                continue
            destination = candidate / name
            if not destination.is_file() or destination.read_bytes() != data:
                # The only existing order controller adaptation is the service
                # GPM publication method; it is not a migration dependency.
                if name == 'app/Http/Controllers/Order/ManagerOrderController.php':
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                copied.append(name)
            queue.append(source)
    for name in set(copied):
        r = subprocess.run(['/opt/php74/bin/php', '-l', str(candidate / name)], capture_output=True)
        if r.returncode:
            raise RuntimeError('MIGRATION_DEPENDENCY_LINT_FAILED')
    report = {'passed': not blocked, 'added_or_updated_classes': sorted(set(copied)),
              'credential_sources_not_copied': sorted(set(blocked)), 'grouped_imports_supported': True,
              'live_files_changed': False, 'main_crm_read_only': True, 'migrations_executed': False}
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'added_or_updated_classes': len(set(copied)),
                      'credential_sources_not_copied': len(set(blocked)), 'live_files_changed': False}))


if __name__ == '__main__':
    main()
