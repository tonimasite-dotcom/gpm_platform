"""Conservative static dependencies and pending migration effects; no execution."""
from pathlib import Path
import hashlib
import json
import re

MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
OUT = Path('/root/gpm-ts-update/order-parity-audit-20261110-01')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def class_index(root):
    index = {}
    for p in (root / 'app').rglob('*.php'):
        if p.is_symlink() or p.resolve() != p:
            continue
        text = p.read_text(errors='replace')
        namespace = re.search(r'^\s*namespace\s+([^;]+);', text, re.M)
        cls = re.search(r'^\s*(?:(?:final|abstract)\s+)?(?:class|trait|interface)\s+(\w+)', text, re.M)
        if namespace and cls:
            index[namespace.group(1) + '\\' + cls.group(1)] = p
    return index


def main():
    target = OUT / 'dependencies.json'
    if target.exists():
        raise RuntimeError('NEW_DEPENDENCY_REPORT_REQUIRED')
    audit = json.loads((OUT / 'audit.json').read_text())
    index = class_index(MAIN)
    queue = [MAIN / name for name in audit['main'] if name.startswith('app/')]
    seen = set()
    edges = {}
    unresolved = set()
    while queue:
        p = queue.pop()
        name = p.relative_to(MAIN).as_posix()
        if name in seen:
            continue
        seen.add(name)
        text = p.read_text(errors='replace')
        classes = set(re.findall(r'(?<![\w])\\?(App\\[\w\\]+)', text))
        dependencies = set()
        for cls in classes:
            if cls in index:
                dependency = index[cls]
                dependencies.add(dependency.relative_to(MAIN).as_posix())
                queue.append(dependency)
            else:
                unresolved.add(cls)
        edges[name] = sorted(dependencies)
    rows = []
    for name in sorted(seen):
        p = MAIN / name
        text = p.read_text(errors='replace')
        rows.append({'file': name, 'main_sha256': sha(p), 'ts_sha256': sha(TS / name),
                     'differs': sha(p) != sha(TS / name),
                     'literal_tables': sorted(set(re.findall(r'(?:Schema|DB)::(?:hasTable|table|create)\s*\(\s*[\'"]([\w]+)[\'"]', text))),
                     'dependencies': edges[name]})
    schema = {}
    for label in ['main', 'ts']:
        # Query through the strictly read-only schema tool; no business rows.
        import subprocess
        result = subprocess.run(['/opt/php74/bin/php', str(OUT / 'read_schema.php'), str(MAIN if label == 'main' else TS)], capture_output=True)
        if result.returncode:
            raise RuntimeError('SCHEMA_METADATA_REQUIRED')
        schema[label] = json.loads(result.stdout)
    pending = sorted(set(schema['main']['migrations']) - set(schema['ts']['migrations']))
    migrations = []
    for name in pending:
        p = MAIN / 'database/migrations' / (name + '.php')
        text = p.read_text()
        up = re.split(r'\bfunction\s+down\s*\(', text)[0]
        tables = sorted(set(re.findall(r'(?:Schema|DB)::(?:hasTable|table|create)\s*\(\s*[\'"]([\w]+)[\'"]', up)))
        creates = sorted(set(re.findall(r'Schema::create\s*\(\s*[\'"]([\w]+)[\'"]', up)))
        fields = sorted(set(re.findall(r'\$table->\w+\s*\(\s*[\'"]([\w]+)[\'"]', up)))
        consumers = [r['file'] for r in rows if set(tables) & set(r['literal_tables'])]
        migrations.append({'migration': name, 'sha256': sha(p), 'tables': tables, 'creates_tables': creates,
                           'field_literals': fields, 'data_write_markers': sorted(set(re.findall(
                               r'->(update|insert|delete|insertOrIgnore|upsert|save|forceDelete)\s*\(', up))),
                           'site_guard_present': 'workstaffcrm.ru' in up,
                           'order_dependency_consumers': consumers})
    report = {'passed': True, 'kind': 'conservative_static_closure_not_deploy_allowlist',
              'backend': rows, 'unresolved_class_tokens': sorted(unresolved), 'pending_migrations': migrations,
              'missing_tables': sorted({r['table_name'] for r in schema['main']['columns']} - {r['table_name'] for r in schema['ts']['columns']}),
              'live_files_changed': False, 'migrations_executed': False, 'main_crm_read_only': True,
              'business_rows_read': False}
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'passed': True, 'backend_closure_files': len(rows), 'different_backend_dependencies': sum(r['differs'] for r in rows),
                      'pending_migrations': len(migrations), 'data_writing_migrations': [r['migration'] for r in migrations if r['data_write_markers']],
                      'live_files_changed': False, 'main_crm_read_only': True}))


if __name__ == '__main__':
    main()
