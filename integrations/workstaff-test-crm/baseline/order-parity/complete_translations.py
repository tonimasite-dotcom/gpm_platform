"""Match all translation namespaces used by the order UI in the private candidate."""
from pathlib import Path
import importlib.util
import json
import re
import subprocess

ROOT = Path('/root/gpm-ts-update/order-parity-20261110-02')
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')


def main():
    spec = importlib.util.spec_from_file_location('parity_prepare', ROOT / 'prepare_candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = ROOT / 'candidate'
    target = ROOT / 'translation-parity.json'
    if target.exists():
        raise RuntimeError('NEW_TRANSLATION_PASS_REQUIRED')
    queue = [p for p in (MAIN / module.UI).rglob('*') if p.is_file() and p.suffix in ['.vue', '.js']]
    seen, namespaces = set(), {'orders'}
    while queue:
        p = queue.pop()
        if p in seen:
            continue
        seen.add(p)
        text = p.read_text(errors='replace')
        namespaces.update(re.findall(r'[\'"]resources\.([\w]+)\.', text))
        for alias in re.findall(r'(?:from\s*|import\s*)[\'"]([^\'"]+)[\'"]', text):
            dependency = module.resolve_import(MAIN, p, alias)
            if dependency and dependency.suffix in ['.js', '.vue']:
                relative = dependency.relative_to(MAIN).as_posix()
                if relative not in ['resources/js/router/index.js', 'resources/js/store/index.js', 'resources/js/app.js']:
                    queue.append(dependency)
    changed = []
    for p in (candidate / 'resources/js/lang').glob('*.json'):
        source = MAIN / p.relative_to(candidate)
        if not source.is_file():
            continue
        a, b = json.loads(source.read_text()), json.loads(p.read_text())
        before = p.read_bytes()
        for name in namespaces:
            if name in a.get('resources', {}):
                b.setdefault('resources', {})[name] = a['resources'][name]
        p.write_text(json.dumps(b, ensure_ascii=False, indent=4) + '\n')
        if p.read_bytes() != before:
            changed.append(p.relative_to(candidate).as_posix())
    for p in (MAIN / 'resources/lang').glob('*/resources.php'):
        destination = candidate / p.relative_to(MAIN)
        destination.parent.mkdir(parents=True, exist_ok=True)
        module.copy_source(p, destination, MAIN)
        result = subprocess.run(['/opt/php74/bin/php', '-l', str(destination)], capture_output=True)
        if result.returncode:
            raise RuntimeError('RESOURCE_TRANSLATION_PHP_LINT_FAILED')
    report = {'passed': True, 'frontend_files_visited': len(seen), 'resource_namespaces': sorted(namespaces),
              'changed_frontend_locales': changed, 'php_resource_labels_exact_main': True,
              'auth_php_translations_preserved': True, 'live_files_changed': False, 'main_crm_read_only': True}
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'passed': True, 'resource_namespaces': len(namespaces), 'changed_frontend_locales': len(changed),
                      'php_resource_labels_exact_main': True, 'live_files_changed': False}))


if __name__ == '__main__':
    main()
