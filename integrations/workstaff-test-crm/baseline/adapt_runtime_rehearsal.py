#!/usr/bin/env python3
"""Add an explicit private runtime context; never change either live CRM."""
from pathlib import Path
import hashlib
import json
import os

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK / 'candidate'


def main():
    os.umask(0o077)
    if ROOT.resolve() != ROOT or not (ROOT / 'storage/framework/down').is_file():
        raise RuntimeError('PRIVATE_CANDIDATE_REQUIRED')
    report = {}
    patches = {
        'app/Http/Controllers/Order/GpmWorkerRateController.php': (
            "realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'\n"
            "            && rtrim(config('app.url'), '/') === 'https://ts.workstaffcrm.ru'",
            '\\App\\Services\\Release\\GpmTsRuntimeContext::isTsOrPrivateRehearsal()'),
        'app/Http/Controllers/Auth/LoginController.php': (
            "realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'\n"
            "                && rtrim((string)config('app.url'), '/') === 'https://ts.workstaffcrm.ru'",
            '\\App\\Services\\Release\\GpmTsRuntimeContext::isTsOrPrivateRehearsal()'),
        'app/Providers/AppServiceProvider.php': (
            "realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'\n"
            "            && rtrim(config('app.url'), '/') === 'https://ts.workstaffcrm.ru'",
            '\\App\\Services\\Release\\GpmTsRuntimeContext::isTsOrPrivateRehearsal()'),
    }
    planned = []
    for name, (old, new) in patches.items():
        path = ROOT / name
        text = path.read_text()
        if text.count(old) != 1:
            raise RuntimeError('UNEXPECTED_RUNTIME_GUARD_ANCHOR')
        updated = text.replace(old, new, 1)
        if name.endswith('/LoginController.php'):
            login_anchor = "$token = $this->guard()->attempt($this->credentials($request), $request->filled('remember'));"
            login_fixed = '''$guard = $this->guard();
        // JWTGuard's second argument means "perform login", not "remember me".
        $token = $guard instanceof \\Tymon\\JWTAuth\\JWTGuard
            ? $guard->attempt($this->credentials($request))
            : $guard->attempt($this->credentials($request), $request->filled('remember'));'''
            if updated.count(login_anchor) != 1:
                raise RuntimeError('UNEXPECTED_JWT_ATTEMPT_ANCHOR')
            updated = updated.replace(login_anchor, login_fixed, 1)
        if name.endswith('/GpmWorkerRateController.php'):
            history_anchor = '''app(HistoryOrderService::class)->addUpdatedHistory($current, [
                    'work_type_id' => $current->work_type_id, 'workers_cost' => $rate,
                ]);'''
            history_fixed = '''app(HistoryOrderService::class)->addUpdatedHistory($current, array_replace($current->toArray(), [
                    'work_type_id' => $current->work_type_id, 'workers_cost' => $rate,
                ]), ['workers_cost' => 'Ставка рабочего']);'''
            if updated.count(history_anchor) != 1:
                raise RuntimeError('UNEXPECTED_RATE_HISTORY_ANCHOR')
            updated = updated.replace(history_anchor, history_fixed, 1)
        report[name] = {'before_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'after_sha256': hashlib.sha256(updated.encode()).hexdigest()}
        planned.append((path, updated))
    helper = ROOT / 'app/Services/Release/GpmTsRuntimeContext.php'
    if helper.exists():
        raise RuntimeError('RUNTIME_HELPER_ALREADY_EXISTS')
    source = Path(__file__).parent / 'payload/GpmTsRuntimeContext.php'
    if not source.is_file():
        raise RuntimeError('RUNTIME_HELPER_SOURCE_REQUIRED')
    # Preserve pre-adaptation evidence; never rerun merge_candidate over this tree.
    saved = WORK / 'runtime-rehearsal-before-20261109'
    saved.mkdir(mode=0o700, exist_ok=False)
    for path, updated in planned:
        target = saved / path.relative_to(ROOT)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    helper.write_bytes(source.read_bytes())
    for path, updated in planned:
        path.write_text(updated)
    result = {'private_runtime_support_added': True, 'live_files_changed': False,
        'production_path_or_app_url_spoofed': False, 'files': report}
    (WORK / 'runtime-adaptations-20261109.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
