"""Complete the private candidate's order API and observer dependencies."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from php_routes import active_routes, route_prefix

ROOT = Path('/root/gpm-ts-update/order-parity-20261110-02')
MAIN = Path('/var/www/gruzpiter/data/www/workstaffcrm.ru')
TS = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    candidate = ROOT / 'candidate'
    receipt = ROOT / 'backend-dependencies.json'
    if receipt.exists() or candidate.resolve() != candidate:
        raise RuntimeError('NEW_PRIVATE_BACKEND_PASS_REQUIRED')
    safety = json.loads(Path('/root/gpm-ts-update/20261110-demo-06/manifest.json').read_text())
    preserve = {r['file'] for r in safety['files']} - {'app/Providers/AppServiceProvider.php'}
    preserve |= {'app/Http/Controllers/BotController.php', 'app/Http/Controllers/Auth/LoginController.php'}
    # All directly imported data services are an overestimate; their endpoints
    # are recorded privately, then exercised by the acceptance suite.
    prefixes = {'manager_orders', 'leader_orders', 'accountant_orders', 'loader_orders', 'logist_orders'}
    for p in (candidate / 'resources/js/services').glob('*.js'):
        if sha(p) != sha(TS / p.relative_to(candidate)) or 'Order' in p.name:
            text = p.read_text(errors='replace')
            prefixes.update(re.findall(r'\$\{API_URL\}/([\w-]+)', text))
            prefixes.update(re.findall(r'super\(\s*\{\s*name\s*:\s*[\'"]([\w-]+)', text))
    prefixes -= {'users', 'auth', 'roles', 'permissions', 'settings', 'main_settings', 'banking_settings'}
    index = {}
    for p in (MAIN / 'app').rglob('*.php'):
        text = p.read_text(errors='replace')
        ns = re.search(r'^\s*namespace\s+([^;]+);', text, re.M)
        cls = re.search(r'^\s*(?:(?:final|abstract)\s+)?(?:class|trait|interface)\s+(\w+)', text, re.M)
        if ns and cls:
            index[ns.group(1) + '\\' + cls.group(1)] = p
    upstream_routes = (MAIN / 'routes/api.php').read_text()
    imports = dict((alias or cls.split('\\')[-1], cls) for cls, alias in re.findall(
        r'^use\s+(App\\Http\\Controllers\\[\w\\]+)(?:\s+as\s+(\w+))?;', upstream_routes, re.M))
    statements = []
    queue = [MAIN / 'app/Models/User.php', MAIN / 'app/Http/Middleware/FinancialTransaction.php']
    for match in active_routes(upstream_routes):
        statement = match.group(0)
        prefix = route_prefix(statement)
        if prefix not in prefixes:
            continue
        classes = re.findall(r'(\\?[\w\\]+Controller)::class', statement)
        if not classes:
            continue
        qualified = [imports.get(cls, cls.lstrip('\\')) for cls in classes]
        if any('\\Auth\\' in cls or cls.endswith('BotController') for cls in qualified):
            continue
        statements.append(statement)
        queue += [index[cls] for cls in qualified if cls in index]
    # Only order/document/financial observers; no account deletion or identity
    # observer is transplanted into the authentication/account lifecycle.
    observers = ['OrderObserver', 'OrderPauseObserver', 'WorkerLastOrderObserver',
                 'DocumentPaymentAllocationObserver', 'PaymentObserver', 'CustomerDebtObserver', 'CustomerPauseObserver']
    queue += [MAIN / 'app/Observers' / (name + '.php') for name in observers]
    seen, changed, blocked = set(), [], []
    while queue:
        p = queue.pop()
        if not p.is_file():
            raise RuntimeError('MISSING_UPSTREAM_DEPENDENCY')
        name = p.relative_to(MAIN).as_posix()
        if name in seen or name in preserve:
            continue
        seen.add(name)
        if p.resolve() != p:
            raise RuntimeError('DEPENDENCY_SYMLINK_REJECTED')
        text = p.read_text(errors='replace')
        secret = re.findall(r'(?:password|secret|api_key|access_token)[\'"]?\s*(?:=>|=)\s*([\'"])([^\r\n]*?)\1', text, re.I)
        if any(len(value) >= 12 and ' ' not in value and '|' not in value and 'required' not in value for _, value in secret):
            blocked.append(name)
            continue
        for cls in set(re.findall(r'(?<![\w])\\?(App\\[\w\\]+)', text)):
            if cls in index:
                queue.append(index[cls])
        target = candidate / name
        if sha(target) != sha(p):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
            changed.append(name)
    # Keep both existing service-only GPM endpoints while ordinary forms exactly
    # match main. This adds no TS-only fields or publication dialog to the UI.
    manager = candidate / 'app/Http/Controllers/Order/ManagerOrderController.php'
    before = (ROOT / 'source-ts' / manager.relative_to(candidate)).read_text()
    start = before.index('    public function publishGpmApp(')
    end = before.index('    public function getHistory(', start)
    method = before[start:end].replace('publishGpmApp(Order $order, Request $request)',
        'publishGpmApp(\\App\\Models\\Order $order, \\Illuminate\\Http\\Request $request)').replace(
        'new GpmAppOrderPublisher()', 'new \\App\\Services\\Order\\GpmAppOrderPublisher()')
    text = manager.read_text()
    if 'function publishGpmApp(' in text:
        raise RuntimeError('UNEXPECTED_PUBLICATION_METHOD')
    manager.write_text(text[:text.rfind('}')] + method + text[text.rfind('}'):])
    routes = candidate / 'routes/api.php'
    original = routes.read_text()
    selected = []
    for match in active_routes(original):
        prefix = route_prefix(match.group(0))
        if prefix in prefixes and 'gpm_' not in match.group(0):
            selected.append((match.start(), match.end()))
    if not selected:
        raise RuntimeError('EXISTING_AUTHENTICATED_ROUTE_GROUP_REQUIRED')
    insert_at = selected[0][0]
    for start, end in reversed(selected):
        original = original[:start] + original[end:]
    block = '\n    '.join(s[:-1] + '->middleware(\\App\\Http\\Middleware\\FinancialTransaction::class);' for s in statements)
    original = original[:insert_at] + block + original[insert_at:]
    needed = []
    for alias, cls in imports.items():
        if any(re.search(r'(?<![\w\\])' + re.escape(alias) + r'::class', s) for s in statements):
            line = 'use ' + cls + (' as ' + alias if alias != cls.split('\\')[-1] else '') + ';'
            if line not in original:
                needed.append(line)
    original = original.replace('<?php', '<?php\n' + '\n'.join(needed), 1)
    routes.write_text(original)
    # Main provider removes the old TS-only order update restriction. The sole
    # additional boot call remains the required TS mail/transport safety policy.
    provider = (MAIN / 'app/Providers/AppServiceProvider.php').read_text()
    anchor = '    public function boot()\n    {'
    if provider.count(anchor) != 1:
        raise RuntimeError('APP_PROVIDER_ANCHOR_CHANGED')
    provider = provider.replace(anchor, anchor + '\n        \\App\\Services\\Release\\GpmTsDemoPolicy::register($this->app);\n', 1)
    (candidate / 'app/Providers/AppServiceProvider.php').write_text(provider)
    events = (ROOT / 'source-ts/app/Providers/EventServiceProvider.php').read_text()
    anchor = '        Payment::observe(PaymentObserver::class);'
    additions = '''
        Payment::observe(\\App\\Observers\\DocumentPaymentAllocationObserver::class);
        Order::observe(\\App\\Observers\\DocumentPaymentAllocationObserver::class);
        \\App\\Models\\Documents\\DocumentLink::observe(\\App\\Observers\\DocumentPaymentAllocationObserver::class);
        Order::observe(\\App\\Observers\\OrderPauseObserver::class);
        Order::observe(\\App\\Observers\\WorkerLastOrderObserver::class);
        \\App\\Models\\Customer::observe(\\App\\Observers\\CustomerPauseObserver::class);
'''
    if events.count(anchor) != 1:
        raise RuntimeError('EVENT_PROVIDER_ANCHOR_CHANGED')
    (candidate / 'app/Providers/EventServiceProvider.php').write_text(events.replace(anchor, anchor + additions, 1))
    linted = 0
    for name in set(changed + ['routes/api.php', 'app/Providers/AppServiceProvider.php',
                              'app/Providers/EventServiceProvider.php', manager.relative_to(candidate).as_posix()]):
        p = candidate / name
        if p.suffix == '.php':
            result = subprocess.run(['/opt/php74/bin/php', '-l', str(p)], capture_output=True)
            if result.returncode:
                raise RuntimeError('BACKEND_PHP74_LINT_FAILED')
            linted += 1
    assert sha(candidate / 'app/Http/Controllers/Auth/LoginController.php') == sha(TS / 'app/Http/Controllers/Auth/LoginController.php')
    report = {'prepared': True, 'deployable': False, 'additional_backend_files': sorted(set(changed)),
              'route_prefixes': sorted(prefixes), 'upstream_route_statements': len(statements),
              'credential_sources_not_copied': blocked, 'php74_linted': linted,
              'main_crm_read_only': True, 'live_files_changed': False, 'database_accessed': False,
              'login_controller_unchanged': True, 'new_auth_account_observers_installed': False,
              'pending': ['Private migration and old-data checks', 'Role permission equivalence',
                          'Transport inventory and guards for new outbound callers', 'HTTP/API and GPM acceptance']}
    receipt.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'prepared': True, 'deployable': False, 'additional_backend_files': len(set(changed)),
                      'route_statements': len(statements), 'credential_sources_not_copied': len(blocked),
                      'php74_linted': linted, 'live_files_changed': False}))


if __name__ == '__main__':
    main()
