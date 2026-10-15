#!/usr/bin/env python3
"""Add a worker-rate-only editor to the inspected ts installation. Plan by default."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
BUILD = ROOT / 'storage/app/gpm-worker-rate-build-20261015'
BACKUP = Path('/root/gpm-snapshots/20261015-worker-rate-ui')
BUNDLE = Path(__file__).resolve().parent
MANIFEST_SHA = '10b4a84c3e64bdce844157071aca53fb56782d144837ac83ba801761284ef8a9'
FORM = 'resources/js/pages/app/orders/logist_orders/LogistOrderForm.vue'
EXPECTED = {
    'routes/api.php': '4a9402713e826b7f8884433b7154e12336bef882f4e88bbd3361de92282261b4',
    FORM: 'd05ded31f48c05e6bad41450e924d39dcef2f98c95122e82b213eca04fa4c103',
    'app/Providers/AppServiceProvider.php': 'd0d371f424b205fab2d99267bfd50dcb92628b476be501a206703fd90b4d6a01',
}
NEW = [
    'app/Services/Order/GpmWorkerRateRules.php',
    'app/Services/Order/GpmLogistOrderGuard.php',
    'app/Http/Controllers/Order/GpmWorkerRateController.php',
    'resources/js/pages/app/orders/logist_orders/GpmWorkerRateEditor.vue',
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, **kwargs):
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def checked(path):
    if path.is_symlink() or ROOT not in path.resolve().parents:
        raise RuntimeError('Unexpected path outside ts')
    return path


def replacement(path, data, uid, gid, mode):
    checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.gpm-rate-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def patches():
    route = (ROOT / 'routes/api.php').read_text()
    anchor = "    Route::resource('logist_orders', LogistOrderController::class);"
    if route.count(anchor) != 1:
        raise RuntimeError('Unexpected route structure')
    addition = "    Route::patch('logist_orders/{order}/gpm_worker_rate', [\\App\\Http\\Controllers\\Order\\GpmWorkerRateController::class, 'update'])->where('order', '[0-9]+')->name('logist_orders.gpm_worker_rate');\n"
    route = route.replace(anchor, addition + anchor)
    form = (ROOT / FORM).read_text()
    anchor = '    <v-form v-if="tabs === \'main_info\'"'
    if form.count(anchor) != 1:
        raise RuntimeError('Unexpected form structure')
    panel = ('    <gpm-worker-rate-editor v-if="modelId && orderInfo && tabs === \'main_info\' && !readonly && ![3, 4, 5].includes(Number(orderInfo.status_id))"\n'
             '      :order-id="modelId" :initial-rate="orderInfo.workers_cost" @saved="init" />\n')
    form = form.replace(anchor, panel + anchor)
    form = form.replace('export default {', "import GpmWorkerRateEditor from './GpmWorkerRateEditor'\n\nexport default {", 1)
    form = form.replace('  components: {', '  components: {\n    GpmWorkerRateEditor,', 1)
    if ':readonly="!readonly"' not in form:
        raise RuntimeError('Existing readonly form changed')
    provider = (ROOT / 'app/Providers/AppServiceProvider.php').read_text()
    anchor = '        Relation::morphMap(['
    if provider.count(anchor) != 1:
        raise RuntimeError('Unexpected ts service provider structure')
    guard = '''        // GPM ts-only: CRM logists cannot edit address/client pricing.
        if (realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'
            && rtrim(config('app.url'), '/') === 'https://ts.workstaffcrm.ru') {
            \\App\\Models\\Order::updating(function ($order) {
                $actor = auth()->user();
                $roles = $actor ? $actor->roles->pluck('name')->all() : [];
                $forbidden = \\App\\Services\\Order\\GpmLogistOrderGuard::forbiddenFields(
                    array_keys($order->getDirty()), $roles
                );
                abort_if(count($forbidden) > 0, 403, 'Only a manager can change the address or client price');
            });
        }

'''
    provider = provider.replace(anchor, guard + anchor, 1)
    with tempfile.TemporaryDirectory(prefix='gpm-ts-rate-lint-') as temporary:
        for name, text in [('routes.php', route), ('provider.php', provider)]:
            candidate = Path(temporary) / name
            candidate.write_text(text)
            run(['php', '-l', str(candidate)])
    return {'routes/api.php': route.encode(), FORM: form.encode(),
            'app/Providers/AppServiceProvider.php': provider.encode()}


def preflight():
    if os.geteuid() != 0 or ROOT.resolve() != ROOT or BACKUP.resolve() != BACKUP:
        raise RuntimeError('Unexpected user/scope')
    for name, expected in EXPECTED.items():
        if digest(checked(ROOT / name)) != expected:
            raise RuntimeError('Inspected ts sources changed; review first')
    for name in NEW:
        if checked(ROOT / name).exists():
            raise RuntimeError('Worker-rate editor already exists; do not overwrite')
    if digest(checked(ROOT / 'public/mix-manifest.json')) != MANIFEST_SHA:
        raise RuntimeError('Live ts frontend changed during preparation; review first')
    php = ('require "' + str(ROOT) + '/vendor/autoload.php"; '
           '$app=require "' + str(ROOT) + '/bootstrap/app.php"; '
           '$app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); '
           'echo json_encode(["url"=>config("app.url"),"config_cached"=>$app->configurationIsCached(),'
           '"routes_cached"=>$app->routesAreCached()]);')
    value = json.loads(run(['runuser', '-u', 'gruzpiter', '--', 'php', '-r', php], cwd=ROOT))
    if value != {'url': 'https://ts.workstaffcrm.ru', 'config_cached': False, 'routes_cached': False}:
        raise RuntimeError('Unexpected ts runtime/cache')
    for name in NEW:
        if name.endswith('.php'):
            run(['php', '-l', str(BUNDLE / name)])
    run(['php', str(BUNDLE.parent / 'tests/worker_rate_test.php')])


def prepare(changes):
    if BUILD.exists() or BACKUP.exists():
        raise RuntimeError('Prior preparation exists; inspect instead of overwriting')
    BACKUP.mkdir(mode=0o700, parents=True)
    raw = BACKUP / 'before-ui.tar.gz'
    with tarfile.open(raw, 'w:gz') as archive:
        for name in list(EXPECTED) + ['public/mix-manifest.json', 'public/dist']:
            archive.add(checked(ROOT / name), arcname=name)
    seal = Path('/root/gpm-snapshots/20261015-before-sync')
    encrypted = BACKUP / 'before-ui.tar.gz.age'
    try:
        run([str(seal / 'age'), '--encrypt', '--recipient', (seal / 'age-recipient.txt').read_text().strip(),
             '--output', str(encrypted), str(raw)])
    finally:
        if encrypted.exists():
            raw.unlink()
    (BACKUP / 'encrypted-manifest.json').write_text(json.dumps({
        'scope': str(ROOT), 'sha256': digest(encrypted), 'bytes': encrypted.stat().st_size,
        'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2) + '\n')
    checked(BUILD).mkdir(mode=0o700)
    resources = ROOT / 'resources'
    for source in resources.rglob('*'):
        checked(source)
    shutil.copytree(resources, BUILD / 'resources')
    for name in ['package.json', 'package-lock.json', 'webpack.mix.js', '.babelrc', '.eslintrc.js']:
        source = ROOT / name
        if source.exists():
            shutil.copy2(checked(source), BUILD / name)
    checked(ROOT / 'node_modules')
    (BUILD / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
    (BUILD / 'public').mkdir()
    # Resolve only public MIX_* values used by frontend source, never copy backend .env.
    import re
    names = set()
    for source in (BUILD / 'resources/js').rglob('*.js'):
        names.update(re.findall(r'process\.env\.(MIX_[A-Z0-9_]+)', source.read_text()))
    php = ('require "' + str(ROOT) + '/vendor/autoload.php"; $app=require "' + str(ROOT) + '/bootstrap/app.php"; '
           '$app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); $v=[]; '
           'foreach (json_decode($argv[1],true) as $key) {$v[$key]=env($key,"");} echo json_encode($v);')
    public = json.loads(run(['php', '-r', php, json.dumps(sorted(names))], cwd=ROOT))
    (BUILD / '.env').write_text(''.join(key + '=' + json.dumps(str(value or '')) + '\n' for key, value in public.items()))
    for name, data in changes.items():
        if name.startswith('resources/'):
            (BUILD / name).write_bytes(data)
    for name in NEW:
        if name.startswith('resources/'):
            target = BUILD / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BUNDLE / name, target)
    build(changes)


def build(changes):
    if not BUILD.is_dir() or not (BACKUP / 'encrypted-manifest.json').is_file():
        raise RuntimeError('Prepare a verified backup/build first')
    # Outside the Laravel root, Mix otherwise defaults to /mix-manifest.json.
    config = BUILD / 'webpack.mix.js'
    text = config.read_text()
    if ".setPublicPath('public')" not in text:
        anchor = "mix\n  .js"
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected staged Mix configuration')
        config.write_text(text.replace(anchor, "mix\n  .setPublicPath('public')\n  .js", 1))
    (BUILD / FORM).write_bytes(changes[FORM])
    for name in NEW:
        if name.startswith('resources/'):
            (BUILD / name).write_bytes((BUNDLE / name).read_bytes())
    environment = os.environ.copy()
    environment['NODE_OPTIONS'] = '--max-old-space-size=2048'
    with (BUILD / 'build.log').open('wb') as log:
        subprocess.run(['npm', 'run', 'production'], cwd=BUILD, env=environment, check=True, stdout=log, stderr=log, timeout=1200)
    manifest = json.loads((BUILD / 'public/mix-manifest.json').read_text())
    if not manifest or not (BUILD / 'public/dist').is_dir():
        raise RuntimeError('Build has no versioned assets')
    for destination in manifest.values():
        if not (BUILD / 'public' / destination.lstrip('/')).is_file():
            raise RuntimeError('Manifest entry is absent')
    print(json.dumps({'built': True, 'private_build': str(BUILD), 'backup': str(BACKUP / 'before-ui.tar.gz.age'), 'runtime_changed': False}))


def apply(changes):
    recorded = json.loads((BACKUP / 'encrypted-manifest.json').read_text())
    if digest(BACKUP / 'before-ui.tar.gz.age') != recorded['sha256']:
        raise RuntimeError('Backup no longer matches')
    # The provider guard was added after the UI backup was prepared. Preserve
    # its exact original separately before changing it; never rewrite old backups.
    provider_backup = BACKUP / 'app-provider-before-guard.php.age'
    if not provider_backup.exists():
        seal = Path('/root/gpm-snapshots/20261015-before-sync')
        run([str(seal / 'age'), '--encrypt', '--recipient', (seal / 'age-recipient.txt').read_text().strip(),
             '--output', str(provider_backup), str(ROOT / 'app/Providers/AppServiceProvider.php')])
        (BACKUP / 'provider-backup.json').write_text(json.dumps({
            'sha256': digest(provider_backup), 'bytes': provider_backup.stat().st_size,
            'source_sha256': EXPECTED['app/Providers/AppServiceProvider.php'],
        }, indent=2) + '\n')
    provider_manifest = json.loads((BACKUP / 'provider-backup.json').read_text())
    if digest(provider_backup) != provider_manifest['sha256']:
        raise RuntimeError('Provider backup no longer matches')
    manifest = checked(BUILD / 'public/mix-manifest.json')
    json.loads(manifest.read_text())
    assets = []
    for source in (BUILD / 'public/dist').rglob('*'):
        if source.is_file():
            if source.is_symlink():
                raise RuntimeError('Unexpected build symlink')
            target = checked(ROOT / 'public/dist' / source.relative_to(BUILD / 'public/dist'))
            if target.exists() and digest(target) != digest(source):
                raise RuntimeError('Build would overwrite an existing versioned asset')
            assets.append((source, target))
    user = pwd.getpwnam('gruzpiter')
    old = {name: ((ROOT / name).read_bytes(), (ROOT / name).stat()) for name in list(changes) + ['public/mix-manifest.json']}
    new = {**changes, **{name: (BUNDLE / name).read_bytes() for name in NEW}}
    written = []
    try:
        # Install classes before the provider starts referencing the new guard.
        names = NEW + list(changes)
        for name in names:
            data = new[name]
            info = old[name][1] if name in old else None
            replacement(ROOT / name, data, info.st_uid if info else user.pw_uid,
                        info.st_gid if info else user.pw_gid, stat.S_IMODE(info.st_mode) if info else 0o644)
            written.append(name)
        run(['runuser', '-u', 'gruzpiter', '--', 'php', str(ROOT / 'artisan'), 'route:list', '--path=gpm_worker_rate'], cwd=ROOT)
        for source, target in assets:
            if not target.exists():
                missing = []
                parent = target.parent
                while not parent.exists():
                    checked(parent)
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    os.chown(parent, user.pw_uid, user.pw_gid)
                    os.chmod(parent, 0o755)
                replacement(target, source.read_bytes(), user.pw_uid, user.pw_gid, 0o644)
        info = old['public/mix-manifest.json'][1]
        if digest(ROOT / 'public/mix-manifest.json') != MANIFEST_SHA:
            raise RuntimeError('Concurrent ts frontend update; refusing manifest replacement')
        replacement(ROOT / 'public/mix-manifest.json', manifest.read_bytes(), info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
        written.append('public/mix-manifest.json')
        print(json.dumps({'applied': True, 'only_worker_rate_editable': True, 'old_assets_retained': True,
                          'crm_logist_address_client_price_guard': True,
                          'orders_changed': 0, 'other_crm_touched': False}))
    except BaseException:
        for name in reversed(written):
            if name in old:
                data, info = old[name]
                replacement(ROOT / name, data, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
            elif (ROOT / name).read_bytes() == new[name]:
                (ROOT / name).unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--apply', action='store_true')
    group.add_argument('--build', action='store_true', help='Resume only the private build after inspecting an error')
    arguments = parser.parse_args()
    os.umask(0o077)
    preflight()
    changes = patches()
    print(json.dumps({'scope': str(ROOT), 'existing_files': list(changes), 'new_files': NEW,
                      'orders_changed': 0, 'prepare': arguments.prepare, 'apply': arguments.apply}))
    if arguments.prepare:
        prepare(changes)
    elif arguments.apply:
        apply(changes)
    elif arguments.build:
        build(changes)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Worker-rate installation stopped (' + type(error).__name__ + '); credentials not printed.')
        raise SystemExit(1)
