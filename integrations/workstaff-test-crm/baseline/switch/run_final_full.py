#!/usr/bin/env python3
"""One uninterrupted private checkpoint restore -> upgrade -> acceptance -> rollback."""
from pathlib import Path
import importlib.util
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import time

SAVED=Path('/root/gpm-ts-update/20261106-baseline-01')
WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def operations():
    spec=importlib.util.spec_from_file_location('final_private_switch_operations',str(TOOLS/'run_switch.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def sql(statement):
    r=subprocess.run(['mysql','--no-defaults','--protocol=SOCKET','--socket='+str(WORK/'mysql-new/mysql.sock'),
        '--user=root','--batch','--skip-column-names'],input=statement.encode(),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    if r.returncode:raise RuntimeError('PRIVATE_FINAL_SQL_FAILED_DETAILS_WITHHELD')
    return r.stdout.decode().strip()


def merge_vendor(source,dest):
    for directory,subdirs,files in os.walk(str(source),followlinks=False):
        target=dest/Path(directory).relative_to(source);target.mkdir(parents=True,exist_ok=True)
        for name in subdirs+files:
            path=Path(directory)/name;out=target/name
            if path.is_symlink():
                if source not in path.resolve().parents or out.exists() or out.is_symlink():
                    raise RuntimeError('UNEXPECTED_VENDOR_LINK')
                out.symlink_to(os.readlink(str(path)))
            elif path.is_file():
                if out.is_symlink():raise RuntimeError('VENDOR_OVERWRITE_LINK_REFUSED')
                shutil.copy2(str(path),str(out))


def main():
    os.umask(0o077);m=operations()
    m.require(WORK.resolve()==WORK and m.version(WORK/'runtime')=='old' and m.version(WORK/'next')=='new','CLOSED_OLD_AND_ACCEPTED_NEW_REQUIRED')
    first=json.loads((WORK/'upgrade-completed.json').read_text())
    m.require(first['success'] and first['applied_this_pass']==37,'COMPLETED_FIRST_UPGRADE_PROOF_REQUIRED')
    m.require(not (WORK/'switch-rehearsal-result.json').exists(),'FINAL_REPORT_ALREADY_EXISTS')
    m.require(shutil.disk_usage(str(WORK)).free>4*1024**3,'FULL_PRESERVED_COPY_SPACE_REQUIRED')
    with (WORK/'final-full-started.json').open('x') as out:out.write(json.dumps({'upgrade_timeout_seconds':1800}))
    # Preserve the fully upgraded first run, including its identity-bound markers.
    accepted=WORK/'accepted-new-first-run'
    m.require(not accepted.exists(),'NEW_ACCEPTED_ARCHIVE_REQUIRED')
    (WORK/'next').rename(accepted)
    copied=time.monotonic()
    shutil.copytree(str(WORK/'runtime'),str(WORK/'next'),symlinks=True)
    manifest=json.loads((SAVED/'candidate-manifest-order-forms-20261109.json').read_text())
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    m.require(digest=='dce57370efff2615fafde248addfb7808f13a0560254f2fb4e3982fd7a661b5d','PINNED_CANDIDATE_REQUIRED')
    for relative,expected in manifest.items():
        source=SAVED/'candidate'/relative
        m.require(source.resolve()==source and hashlib.sha256(source.read_bytes()).hexdigest()==expected,'CANDIDATE_SOURCE_CHANGED')
        dest=WORK/'next'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(source),str(dest))
    merge_vendor(SAVED/'candidate/vendor',WORK/'next/vendor')
    for name in ['GpmTsSwitchContext.php','GpmTsRehearsal.php','GpmTsRuntimeContext.php']:
        shutil.copy2(str(TOOLS/name),str(WORK/'next/app/Services/Release'/name))
    shutil.copy2(str(accepted/'app/Console/Commands/PlanningDayBoundary.php'),str(WORK/'next/app/Console/Commands/PlanningDayBoundary.php'))
    cache=WORK/'next/bootstrap/cache'
    if cache.exists():cache.rename(WORK/'preserved/final-next-bootstrap-cache')
    cache.mkdir(parents=True,exist_ok=True)
    (WORK/'next/.gpm-switch-version').write_text('new\n')
    (WORK/'next/.gpm-switch-generation').write_text('final\n')
    for name in ['worker-calculation-activation.json','planning-day-activation.json']:
        m.require(not (WORK/'next/storage/app'/name).exists(),'FINAL_MARKERS_MUST_BE_CREATED_LOCALLY')
    artifact_seconds=round(time.monotonic()-copied,3)
    m.require(shutil.disk_usage(str(WORK)).free>1600*1024**2,'FINAL_DATABASE_SPACE_REQUIRED')
    identity=sql('SELECT @@datadir,@@skip_networking,@@innodb_buffer_pool_size').split('\t')
    m.require(identity[:2]==[str(WORK/'mysql-new/data')+'/','1'] and int(identity[2])>=536870912,'VERIFIED_NEW_PRIVATE_SERVER_REQUIRED')
    password=secrets.token_hex(24)
    sql("CREATE DATABASE `gpm_ts_switch_final` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        "CREATE USER 'gpm_ts_switch_final'@'localhost' IDENTIFIED BY '"+password+"';"
        "GRANT ALL PRIVILEGES ON `gpm_ts_switch_final`.* TO 'gpm_ts_switch_final'@'localhost';")
    private={'datadir':str(WORK/'mysql-new/data'),'socket':str(WORK/'mysql-new/mysql.sock'),
        'database':'gpm_ts_switch_final','username':'gpm_ts_switch_final','password':password}
    with (WORK/'final-database-identity.json').open('x') as out:out.write(json.dumps(private))
    env=WORK/'next/.env';raw=env.read_text()
    for key,value in {'DB_SOCKET':private['socket'],'DB_DATABASE':private['database'],
        'DB_USERNAME':private['username'],'DB_PASSWORD':private['password']}.items():
        raw,count=re.subn(r'^'+key+r'=.*$',lambda match:key+'='+json.dumps(value),raw,flags=re.M)
        m.require(count==1,'PRIVATE_ENV_FIELD_MISMATCH')
    env.write_text(raw)
    # These are copies, not edits of accepted or historical checkers.
    for source,target in [('new_data_check.php','final_new_data_check.php'),('new_pristine_data_check.php','final_pristine_data_check.php')]:
        code=(TOOLS/source).read_text().replace('gpm_ts_switch_new','gpm_ts_switch_final')
        with (TOOLS/target).open('x') as out:out.write(code)
    code=(TOOLS/'run_upgrade.php').read_text().replace('upgrade-completed.json','final-upgrade-completed.json')
    code=code.replace('upgrade-private-error.log','final-upgrade-private-error.log').replace('upgrade-step-progress.jsonl','final-upgrade-step-progress.jsonl')
    with (TOOLS/'run_final_upgrade.php').open('x') as out:out.write(code)
    r={'live_crm_accessed':False,'failed_attempts_and_databases_preserved':True,'phases':{},'release_ready':False,
        'public_http_or_fpm_switch_tested':False,'production_downtime_measured':False,
        'earlier_mid_migration_failure_rollback_passed':True,'earlier_timeout_and_schema_failure_disclosed':True,
        'first_completed_upgrade_preserved':True,'artifact_copy_outside_closed_window_seconds':artifact_seconds,
        'private_buffer_pool_bytes':int(identity[2])}
    r['phases']['old_data']=m.php('old_data_check.php',phase='final-old-data')
    r['phases']['old_smoke']=m.php('runtime_smoke.php',phase='final-old-smoke')
    frozen=m.tree_state(WORK/'runtime')
    with (WORK/'final-closed-tree-manifest.json').open('x') as out:out.write(json.dumps(frozen,indent=2))
    r['original_runtime_objects_preserved']=len(frozen)
    m.require(sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='gpm_ts_switch_final'")=='0','FINAL_RESTORE_TARGET_NOT_EMPTY')
    window=time.monotonic();restore=time.monotonic()
    with (WORK/'final-restore-dump-private.log').open('xb') as de,(WORK/'final-restore-import-private.log').open('xb') as ie:
        dump=subprocess.Popen(['mysqldump','--no-defaults','--protocol=SOCKET','--socket='+str(WORK/'mysql-old/mysql.sock'),
            '--user=root','--single-transaction','--skip-lock-tables','--skip-add-drop-table','--skip-add-locks',
            '--no-tablespaces','--set-gtid-purged=OFF','--hex-blob','gpm_ts_backup_20261109'],stdout=subprocess.PIPE,stderr=de)
        target=subprocess.Popen(['mysql','--no-defaults','--protocol=SOCKET','--socket='+private['socket'],
            '--user=root',private['database']],stdin=dump.stdout,stdout=subprocess.DEVNULL,stderr=ie)
        dump.stdout.close();tc=target.wait();dc=dump.wait()
    m.require(tc==0 and dc==0,'FINAL_STREAM_RESTORE_FAILED')
    r['phases']['logical_checkpoint_restore_seconds']=round(time.monotonic()-restore,3)
    r['phases']['switch_seconds']=m.exchange('old')
    r['phases']['pristine_new_data']=m.php('final_pristine_data_check.php',phase='final-pristine-new-data')
    r['phases']['completed_upgrade']=m.php('run_final_upgrade.php',['complete'],phase='final-upgrade-complete',timeout=1800)
    r['phases']['new_data']=m.php('final_new_data_check.php',phase='final-new-data')
    r['phases']['new_smoke']=m.php('runtime_smoke.php',phase='final-new-smoke')
    r['phases']['new_forms']=m.php('order_form_acceptance.php',phase='final-new-forms')
    r['phases']['new_functional']=m.php('functional_acceptance.php',phase='final-new-functional')
    r['phases']['new_context_negative']=m.php('context_negative.php',phase='final-new-negative')
    r['phases']['new_data_after_tests']=m.php('final_new_data_check.php',phase='final-new-data-after-tests')
    state_names=['.env','storage/app/worker-calculation-activation.json','storage/app/planning-day-activation.json',
        '.gpm-switch-version','.gpm-switch-generation']
    state={name:hashlib.sha256((WORK/'runtime'/name).read_bytes()).hexdigest() for name in state_names}
    r['post_activation_failure_injected']=True
    rollback=time.monotonic()
    r['phases']['rollback_atomic_exchange_seconds']=m.exchange('new')
    m.require(m.tree_state(WORK/'runtime')==frozen,'FINAL_ROLLBACK_FILE_STATE_MISMATCH')
    m.require(all(hashlib.sha256((WORK/'next'/name).read_bytes()).hexdigest()==h for name,h in state.items()),'ACCEPTED_NEW_STATE_NOT_PRESERVED')
    r['phases']['rollback_data']=m.php('old_data_check.php',phase='final-rollback-data')
    r['phases']['rollback_smoke']=m.php('runtime_smoke.php',phase='final-rollback-smoke')
    r.update({'private_full_restore_upgrade_acceptance_and_rollback_passed':True,
        'old_files_configs_modes_owners_and_state_restored':True,'accepted_new_identity_state_preserved':True,
        'original_rows_preserved_after_rollback':True,'private_rollback_with_verification_seconds':round(time.monotonic()-rollback,3),
        'private_closed_window_seconds':round(time.monotonic()-window,3)})
    with (WORK/'switch-rehearsal-result.json').open('x') as out:out.write(json.dumps(r,indent=2))
    print(json.dumps({'private_full_restore_upgrade_acceptance_and_rollback_passed':True,
        'private_closed_window_seconds':r['private_closed_window_seconds'],
        'private_rollback_with_verification_seconds':r['private_rollback_with_verification_seconds'],
        'new_forms_scenarios':r['phases']['new_forms']['result']['accepted_scenarios'],
        'new_functional_scenarios':r['phases']['new_functional']['result']['scenarios_passed'],
        'production_downtime_measured':False,'live_crm_accessed':False,'release_ready':False}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        m=operations();restored=False
        try:
            if m.version(WORK/'runtime')=='new':m.exchange('new');restored=True
        except Exception:pass
        (WORK/'final-full-private-error.log').write_text(repr(error))
        code=str(error) if type(error) is RuntimeError else 'FINAL_FULL_PRIVATE_RUN_FAILED_DETAILS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'automatic_private_slot_rollback':restored,'live_crm_accessed':False}));raise SystemExit(1)
