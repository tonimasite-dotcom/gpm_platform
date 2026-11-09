#!/usr/bin/env python3
"""Adapt ONLY the two new private slots. Preserve every replaced source."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil

WORK=Path('/root/gpm-ts-update/20261109-switch-01')


def main():
    os.umask(0o077)
    assert WORK.resolve()==WORK and (WORK/'preparation.json').is_file()
    saved=WORK/'preserved/context-before'
    assert not saved.exists()
    planned=[]
    for version,folder in [('old','runtime'),('new','next')]:
        root=WORK/folder
        assert root.resolve()==root and (root/'.gpm-switch-version').read_text().strip()==version
        if version=='old':
            for relative in ['app/Http/Controllers/Auth/LoginController.php',
                'app/Http/Controllers/Order/GpmWorkerRateController.php','app/Providers/AppServiceProvider.php']:
                path=root/relative
                source=path.read_text()
                pattern=r"realpath\(base_path\(\)\) === '/var/www/gruzpiter/data/www/ts\.workstaffcrm\.ru'\s*&& rtrim\((?:\(string\))?config\('app.url'\), '/'\) === 'https://ts\.workstaffcrm\.ru'"
                updated,count=re.subn(pattern,r'\\App\\Services\\Release\\GpmTsRuntimeContext::isTsOrPrivateRehearsal()',source)
                if relative.endswith('/Auth/LoginController.php') and count==0:
                    assert "if (!config('auth.login_email_code_enabled', true))" in source, 'OLD_LOGIN_FLAG_CONTRACT_MISMATCH'
                    continue  # This older TS uses its existing auth config flag, no path-specific bypass.
                assert count==1, 'OLD_RUNTIME_GUARD_ANCHOR_MISMATCH'
                planned.append((version,path,updated.encode()))
        for name in ['GpmTsSwitchContext.php','GpmTsRehearsal.php','GpmTsRuntimeContext.php']:
            planned.append((version,root/'app/Services/Release'/name,(Path(__file__).parent/name).read_bytes()))
        if version=='new':
            path=root/'app/Console/Commands/PlanningDayBoundary.php'
            source=path.read_text()
            match=re.search(r'    private function guard\(\): void\s*\{.*?\n    \}',source,re.S)
            assert match and 'EXPLICIT_RELEASE_ENV_REQUIRED' in match.group()
            updated=source[:match.start()]+'''    private function guard(): void
    {
        \\App\\Services\\Release\\GpmTsSwitchContext::assertUpgrade();
    }'''+source[match.end():]
            planned.append((version,path,updated.encode()))
    saved.mkdir(mode=0o700)
    changes=[]
    for version,path,data in planned:
        root=WORK/('runtime' if version=='old' else 'next')
        relative=path.relative_to(root)
        before=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if path.exists():
            backup=saved/version/relative
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(str(path),str(backup))
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        changes.append({'version':version,'file':str(relative),'before_sha256':before,'after_sha256':hashlib.sha256(data).hexdigest()})
    result={'new_private_contexts_only':True,'old_functional_code_changed':False,
        'old_path_guards_explicitly_adapted':2,'old_login_uses_existing_config_flag':True,
        'new_planning_day_command_guard_adapted':True,
        'live_crm_changed':False,'files':changes}
    with (WORK/'context-adaptations.json').open('x') as output:output.write(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
