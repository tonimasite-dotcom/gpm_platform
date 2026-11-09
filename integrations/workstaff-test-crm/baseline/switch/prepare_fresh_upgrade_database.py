#!/usr/bin/env python3
"""Preserve the failed private DB and restore a NEW empty one from the frozen old DB."""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time

WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    os.umask(0o077)
    assert WORK.resolve()==WORK and (WORK/'runtime/.gpm-switch-version').read_text().strip()=='old'
    assert (WORK/'continuation-private-error.log').exists() and not (WORK/'fresh-upgrade-database.json').exists()
    assert shutil.disk_usage(str(WORK)).free>2*1024**3
    failed=WORK/'mysql-new-failed-after-timeout';assert not failed.exists()
    stopped=module('stop_failed_private',TOOLS/'stop_private_mysql.py').stop(WORK/'mysql-new')
    (WORK/'mysql-new').rename(failed)
    init=module('init_fresh_private',TOOLS/'init_rehearsal.py')
    init.WORK=WORK;init.MYSQL=WORK/'mysql-new';init.DATABASE='gpm_ts_switch_new';init.ACCOUNT='gpm_ts_switch_new'
    init.main()
    prep=module('private_prep_helpers',TOOLS/'prepare_switch.py')
    assert prep.client(WORK/'mysql-new',"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='gpm_ts_switch_new'")=='0'
    started=time.monotonic()
    with (WORK/'fresh-restore-dump-private.log').open('xb') as de,(WORK/'fresh-restore-import-private.log').open('xb') as ie:
        dump=subprocess.Popen(['mysqldump','--no-defaults','--protocol=SOCKET',
            '--socket='+str(WORK/'mysql-old/mysql.sock'),'--user=root','--single-transaction',
            '--skip-lock-tables','--skip-add-drop-table','--skip-add-locks','--no-tablespaces',
            '--set-gtid-purged=OFF','--hex-blob','gpm_ts_backup_20261109'],stdout=subprocess.PIPE,stderr=de)
        target=subprocess.Popen(['mysql','--no-defaults','--protocol=SOCKET',
            '--socket='+str(WORK/'mysql-new/mysql.sock'),'--user=root','gpm_ts_switch_new'],
            stdin=dump.stdout,stdout=subprocess.DEVNULL,stderr=ie)
        dump.stdout.close();tc=target.wait();dc=dump.wait()
    assert tc==0 and dc==0
    identity=json.loads((WORK/'mysql-new/identity.json').read_text())
    env=WORK/'next/.env'
    backup=WORK/'preserved/new-env-before-fresh-database'
    with backup.open('xb') as out:out.write(env.read_bytes())
    source=env.read_text()
    for key,value in {'DB_SOCKET':identity['socket'],'DB_DATABASE':identity['database'],
        'DB_USERNAME':identity['username'],'DB_PASSWORD':identity['password']}.items():
        source,count=re.subn(r'^'+key+r'=.*$',lambda match:key+'='+json.dumps(value),source,flags=re.M)
        assert count==1
    env.write_text(source)
    assert not (WORK/'next/storage/app/worker-calculation-activation.json').exists()
    assert not (WORK/'next/storage/app/planning-day-activation.json').exists()
    source=(TOOLS/'old_data_check.php').read_text().replace("assertRuntime()!=='old'","assertRuntime()!=='new'")
    source=source.replace('private_old_database_only','private_new_checkpoint_only')
    with (TOOLS/'new_pristine_data_check.php').open('x') as out:out.write(source)
    result={'fresh_private_upgrade_database_created':True,'failed_database_directory_preserved':True,
        'failed_database_shutdown':stopped,'logical_restore_seconds':round(time.monotonic()-started,3),
        'old_database_unchanged':True,'manual_history_repair_performed':False,'tables_dropped':False,
        'live_mysql_accessed':False,'release_ready':False}
    with (WORK/'fresh-upgrade-database.json').open('x') as out:out.write(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as error:
        (WORK/'fresh-prepare-private-error.log').write_text(repr(error))
        print(json.dumps({'success':False,'safe_code':'FRESH_PRIVATE_RESTORE_FAILED_DETAILS_WITHHELD','live_mysql_accessed':False}));raise SystemExit(1)
