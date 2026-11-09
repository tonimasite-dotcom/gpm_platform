#!/usr/bin/env python3
"""Read TS configuration METADATA only. No Laravel bootstrap, DB connection or live writes."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

TS=Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
WORK=Path('/root/gpm-ts-update/20261109-switch-01')


def main():
    os.umask(0o077)
    if TS.resolve()!=TS or (TS/'.env').resolve()!=TS/'.env' or not (TS/'.env').is_file():
        raise RuntimeError('EXACT_TS_ROOT_AND_ENV_REQUIRED')
    allowed=['APP_URL','APP_ENV','DB_CONNECTION','DB_HOST','DB_PORT','DB_SOCKET','DB_DATABASE','DB_USERNAME',
        'CACHE_DRIVER','SESSION_DRIVER','QUEUE_CONNECTION','GPM_APP_ORDER_SYNC_ENABLED']
    code="<?php require '"+str(TS)+"/vendor/autoload.php'; $e=Dotenv\\Dotenv::parse(file_get_contents('"+str(TS)+"/.env')); echo json_encode(array_intersect_key($e,array_flip("+"json_decode('"+json.dumps(allowed)+"',true)"+")));"
    result=subprocess.run(['php'],input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise RuntimeError('TS_METADATA_PARSE_FAILED_DETAILS_WITHHELD')
    metadata=json.loads(result.stdout)
    if metadata.get('APP_URL','').rstrip('/')!='https://ts.workstaffcrm.ru':
        raise RuntimeError('TS_URL_MISMATCH')
    vhosts=[]
    for folder in ['/etc/nginx','/etc/apache2','/etc/httpd']:
        parent=Path(folder)
        if not parent.is_dir():continue
        for path in parent.rglob('ts.workstaffcrm.ru.conf'):
            if not path.is_file():continue
            directives=[]
            for line in path.read_text(errors='replace').splitlines():
                if re.match(r'^\s*(fastcgi_pass|proxy_pass|root|set\s+\$root_path|SetHandler)\s',line):
                    directives.append(line.strip())
            vhosts.append({'configuration_path':str(path),'routing_directives':directives})
    cron=Path('/etc/cron.d/gpm-test-crm-sync')
    cron_info={'present':cron.is_file()}
    if cron.is_file():
        content=cron.read_bytes();info=cron.stat()
        cron_info.update({'sha256':hashlib.sha256(content).hexdigest(),'mode':info.st_mode&0o777,
            'uid':info.st_uid,'gid':info.st_gid,'gpm_sync_command_present':b'gpm:sync-orders' in content,
            'minute_schedule_present':bool(re.search(rb'^\*\s+\*\s+\*\s+\*\s+\*\s',content,re.M))})
    link=TS/'public/storage'
    report={'read_only_ts_metadata_audit':True,'ts_environment_metadata':metadata,'ts_vhost_configuration':vhosts,
        'existing_ts_cron_metadata':cron_info,'public_storage_is_symlink':link.is_symlink(),
        'public_storage_link_target':os.readlink(str(link)) if link.is_symlink() else None,
        'external_storage_target_followed':False,'secret_fields_read_into_report':False,
        'laravel_bootstrapped':False,'database_connected':False,'main_crm_accessed':False,'live_files_changed':False,
        'effective_ts_fpm_opcache_verified':False,'release_ready':False}
    with (WORK/'ts-live-readonly-metadata.json').open('x') as target:target.write(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error) if type(error) is RuntimeError else 'TS_METADATA_AUDIT_FAILED_DETAILS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'live_files_changed':False}));raise SystemExit(1)
