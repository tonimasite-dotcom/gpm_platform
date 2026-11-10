"""Complete static frontend dependencies in the NEW private candidate only."""
from pathlib import Path
import importlib.util
import json
import re

ROOT = Path('/root/gpm-ts-update/order-parity-20261110-02')
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')


def main():
    spec = importlib.util.spec_from_file_location('order_parity_prepare', ROOT / 'prepare_candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = ROOT / 'frontend-dependencies.json'
    if target.exists():
        raise RuntimeError('NEW_DEPENDENCY_PASS_REQUIRED')
    candidate = ROOT / 'candidate'
    queue = [p for p in (MAIN / module.UI).rglob('*') if p.is_file() and p.suffix in ['.vue', '.js']]
    seen, changed, missing, globals_review = set(), [], [], []
    while queue:
        path = queue.pop()
        name = path.relative_to(MAIN).as_posix()
        if name in seen:
            continue
        seen.add(name)
        for alias in re.findall(r'(?:from\s*|import\s*)[\'"]([^\'"]+)[\'"]', path.read_text(errors='replace')):
            dependency = module.resolve_import(MAIN, path, alias)
            if dependency is None:
                if alias.startswith(('./', '../', '~/', '@/')):
                    missing.append({'file': name, 'import': alias})
                continue
            relative = dependency.relative_to(MAIN).as_posix()
            if relative in ['resources/js/router/index.js', 'resources/js/store/index.js', 'resources/js/app.js']:
                if module.sha(dependency) != module.sha(module.TS / relative):
                    globals_review.append(relative)
                continue
            before = module.sha(candidate / relative)
            module.copy_source(dependency, candidate / relative, MAIN)
            if before != module.sha(candidate / relative):
                changed.append(relative)
            queue.append(dependency)
    api = (candidate / 'resources/js/services/api-url.js').read_text().strip()
    if api != "export const API_URL = '/api'":
        raise RuntimeError('SAME_ORIGIN_API_REQUIRED')
    report = {'passed': not missing, 'frontend_files_visited': len(seen),
              'additional_changed_files': sorted(set(changed)), 'unresolved_local_imports': missing,
              'global_frontend_review': sorted(set(globals_review)), 'api_same_origin': True,
              'live_files_changed': False, 'main_crm_read_only': True}
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'frontend_files_visited': len(seen),
                      'additional_changed_files': len(set(changed)), 'unresolved_local_imports': len(missing),
                      'global_frontend_review': len(set(globals_review)), 'live_files_changed': False}))


if __name__ == '__main__':
    main()
