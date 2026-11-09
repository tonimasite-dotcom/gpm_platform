#!/usr/bin/env python3
"""Build explicitly bound checks for the new private switch experiment."""
from pathlib import Path
import hashlib
import json
import shutil

SAVED=Path('/root/gpm-ts-update/20261106-baseline-01')
WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def main():
    assert WORK.resolve()==WORK and (WORK/'context-adaptations.json').exists()
    original=(SAVED/'rehearse_migrations.php').read_bytes()
    assert hashlib.sha256(original).hexdigest()=='0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259'
    source=original.decode()
    function=source[source.index('function originalSnapshot('):source.index('\ntry {')]
    old_check='''<?php
$app=require __DIR__.'/private_runtime_bootstrap.php';
if (App\\Services\\Release\\GpmTsSwitchContext::assertRuntime()!=='old') throw new RuntimeException('OLD_CONTEXT_REQUIRED');
'''+function+'''
$before=json_decode(file_get_contents('/root/gpm-ts-update/20261109-switch-01/original-data-checks.json'),true,512,JSON_THROW_ON_ERROR);
Illuminate\\Support\\Facades\\DB::statement('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY');
Illuminate\\Support\\Facades\\DB::beginTransaction();
try { $after=originalSnapshot($before); }
finally { Illuminate\\Support\\Facades\\DB::rollBack(); }
$changed=[];
foreach ($before as $table=>$state) if ($state['rows']!==$after[$table]['rows'] || $state['sha256']!==$after[$table]['sha256']) $changed[]=$table;
echo json_encode(['success'=>count($changed)===0,'original_tables_checked'=>count($before),'all_original_rows_preserved'=>count($changed)===0,
 'changed_tables'=>$changed,'private_old_database_only'=>true]).PHP_EOL;
if ($changed) exit(1);
'''
    with (TOOLS/'old_data_check.php').open('x') as out:out.write(old_check)
    diagnosis=(SAVED/'acceptance-20261109/payload/diagnose_original_data.php').read_text()
    diagnosis=diagnosis.replace("$root = $work . '/candidate';", "$root = $work . '/runtime';")
    diagnosis=diagnosis.replace(str(SAVED/'candidate'),str(WORK/'runtime')).replace(str(SAVED),str(WORK))
    diagnosis=diagnosis.replace('/rehearsal-mysql/','/mysql-new/')
    diagnosis=diagnosis.replace('gpm_ts_rehearsal_20261106','gpm_ts_switch_new').replace('gpm_ts_rehearsal','gpm_ts_switch_new')
    with (TOOLS/'new_data_check.php').open('x') as out:out.write(diagnosis)
    shutil.copy2(str(SAVED/'acceptance-20261109/payload/OriginalDataAcceptance.php'),str(TOOLS/'OriginalDataAcceptance.php'))
    for name in ['order_form_acceptance.php','functional_acceptance.php']:
        source=(SAVED/'acceptance-20261109/payload'/name).read_text().replace(str(SAVED),str(WORK))
        with (TOOLS/name).open('x') as out:out.write(source)
    print(json.dumps({'private_check_scripts_created':5,'original_checker_unchanged':True,'live_crm_accessed':False}))


if __name__=='__main__':main()
