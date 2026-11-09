#!/usr/bin/env python3
"""Create NEW private switch slots. No live filesystem/database is accessed."""
from pathlib import Path
import base64
import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import time

SAVED = Path('/root/gpm-ts-update/20261106-baseline-01')
WORK = Path('/root/gpm-ts-update/20261109-switch-01')
SOURCE_DB = SAVED/'sql-recovery-20261109/rehearsal-mysql'
DATABASE_OLD = 'gpm_ts_backup_20261109'
DATABASE_NEW = 'gpm_ts_switch_new'
CODE_HASH = 'dce57370efff2615fafde248addfb7808f13a0560254f2fb4e3982fd7a661b5d'


def fail(condition, code):
    if not condition:
        raise RuntimeError(code)


def source_stopped():
    fail(not (SOURCE_DB/'mysql.sock').exists() and not (SOURCE_DB/'mysql.pid').exists(), 'SOURCE_MUST_BE_STOPPED')
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:
                args = (proc/'cmdline').read_bytes().split(b'\0')
            except OSError:
                continue
            fail(('--datadir='+str(SOURCE_DB/'data')).encode() not in args, 'SOURCE_PROCESS_STILL_PRESENT')


def client(directory, sql):
    result = subprocess.run(['mysql','--no-defaults','--protocol=SOCKET',
        '--socket='+str(directory/'mysql.sock'),'--user=root','--batch','--skip-column-names'],
        input=sql.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fail(result.returncode == 0, 'PRIVATE_SQL_FAILED_DIAGNOSTICS_WITHHELD')
    return result.stdout.decode().strip()


def start_old(directory):
    data = directory/'data'
    socket = directory/'mysql.sock'
    fail(directory.resolve() == directory and data.resolve() == data and (data/'ibdata1').is_file(), 'PRIVATE_COLD_COPY_REQUIRED')
    fail(not socket.exists() and not (directory/'mysql.pid').exists(), 'NEW_INSTANCE_ALREADY_RUNNING')
    command = ['unshare','--net','nice','-n','10','/usr/sbin/mysqld','--no-defaults','--user=root',
        '--datadir='+str(data),'--socket='+str(socket),'--pid-file='+str(directory/'mysql.pid'),
        '--log-error='+str(directory/'mysql-error.log'),'--skip-networking','--skip-log-bin',
        '--performance-schema=OFF','--innodb-buffer-pool-size=67108864','--innodb-log-file-size=16777216',
        '--max-connections=12','--innodb-flush-log-at-trx-commit=2',
        '--character-set-server=utf8mb4','--collation-server=utf8mb4_unicode_ci']
    with (directory/'daemon.log').open('ab') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)
    for _ in range(120):
        fail(process.poll() is None, 'NEW_PRIVATE_MYSQL_START_FAILED')
        if socket.exists():
            check = subprocess.run(['mysql','--no-defaults','--protocol=SOCKET','--socket='+str(socket),
                '--user=root','--batch','--skip-column-names','-e','SELECT @@datadir,@@skip_networking'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if check.returncode == 0:
                fail(check.stdout.decode().strip().split('\t') == [str(data)+'/', '1'], 'NEW_MYSQL_IDENTITY_MISMATCH')
                fail(os.readlink('/proc/'+str(process.pid)+'/ns/net') != os.readlink('/proc/1/ns/net'), 'NETWORK_ISOLATION_REQUIRED')
                password = secrets.token_hex(24)
                client(directory, "CREATE USER 'gpm_ts_switch_old'@'localhost' IDENTIFIED BY '"+password+"';"
                    "GRANT ALL PRIVILEGES ON `"+DATABASE_OLD+"`.* TO 'gpm_ts_switch_old'@'localhost';")
                identity = {'datadir':str(data),'socket':str(socket),'database':DATABASE_OLD,
                    'username':'gpm_ts_switch_old','password':password,'pid':process.pid}
                (directory/'identity.json').write_text(json.dumps(identity))
                return identity
        time.sleep(.25)
    raise RuntimeError('NEW_MYSQL_TIMEOUT')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-after-vendor-copy',action='store_true')
    options=parser.parse_args()
    fail(SAVED.resolve()==SAVED and WORK.parent.resolve()==WORK.parent, 'PRIVATE_PARENT_REQUIRED')
    if options.resume_after_vendor_copy:
        fail(WORK.resolve()==WORK and (WORK/'runtime').is_dir() and (WORK/'next').is_dir()
            and not (WORK/'mysql-old').exists() and not (WORK/'mysql-new').exists()
            and not (WORK/'preparation.json').exists(), 'EXACT_PRE_DATABASE_RESUME_STATE_REQUIRED')
    else:
        fail(not WORK.exists(), 'NEW_SWITCH_ROOT_REQUIRED')
    source_stopped()
    fail(shutil.disk_usage(str(SAVED)).free > 8*1024**3, 'INSUFFICIENT_FREE_SPACE')
    manifest = json.loads((SAVED/'candidate-manifest-order-forms-20261109.json').read_text())
    fail(hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()==CODE_HASH, 'CANDIDATE_MANIFEST_MISMATCH')
    for relative, expected in manifest.items():
        path=SAVED/'candidate'/relative
        fail(path.resolve()==path and hashlib.sha256(path.read_bytes()).hexdigest()==expected, 'CANDIDATE_FILE_CHANGED')
    if not options.resume_after_vendor_copy:
        WORK.mkdir(mode=0o700)
        (WORK/'preserved').mkdir(mode=0o700)
    timings = {}
    started=time.monotonic()
    source = SAVED/'file-recovery-20261109/tree'
    fail(source.resolve()==source, 'RESTORED_SOURCE_REQUIRED')
    for directory, subdirs, files in os.walk(str(source),followlinks=False):
        fail(not any((Path(directory)/n).is_symlink() for n in subdirs+files), 'RESTORED_SOURCE_LINK_REQUIRES_REVIEW')
    if not options.resume_after_vendor_copy:
        shutil.copytree(str(source),str(WORK/'runtime'),symlinks=True)
        timings['original_runtime_copy_seconds']=round(time.monotonic()-started,3)
    started=time.monotonic()
    if not options.resume_after_vendor_copy:
        shutil.copytree(str(WORK/'runtime'),str(WORK/'next'),symlinks=True)
        for relative in manifest:
            target=WORK/'next'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(str(SAVED/'candidate'/relative),str(target))
    else:
        # Confirm the interrupted operation completed the entire code overlay.
        for relative,expected in manifest.items():
            path=WORK/'next'/relative
            fail(path.resolve()==path and hashlib.sha256(path.read_bytes()).hexdigest()==expected, 'RESUME_PACKAGE_HASH_MISMATCH')
        for directory,subdirs,files in os.walk(str(source),followlinks=False):
            for name in files:
                before=Path(directory)/name;copied=WORK/'runtime'/before.relative_to(source)
                fail(copied.resolve()==copied and copied.is_file() and before.stat().st_size==copied.stat().st_size
                    and hashlib.sha256(before.read_bytes()).digest()==hashlib.sha256(copied.read_bytes()).digest(), 'RESUME_ORIGINAL_COPY_MISMATCH')
    # Python 3.7 has no copytree(dirs_exist_ok). Preserve links only within vendor.
    vendor=SAVED/'candidate/vendor'
    for directory,subdirs,files in os.walk(str(vendor),followlinks=False):
        target=WORK/'next/vendor'/Path(directory).relative_to(vendor)
        target.mkdir(parents=True,exist_ok=True)
        for name in subdirs+files:
            path=Path(directory)/name;destination=target/name
            if path.is_symlink():
                fail(vendor in path.resolve().parents, 'EXTERNAL_VENDOR_LINK_REFUSED')
                fail(not destination.exists() and not destination.is_symlink(), 'VENDOR_LINK_DESTINATION_EXISTS')
                destination.symlink_to(os.readlink(str(path)))
            elif path.is_file():
                fail(not destination.is_symlink(),'VENDOR_FILE_DESTINATION_IS_LINK')
                shutil.copy2(str(path),str(destination))
    timings['new_runtime_package_copy_seconds']=round(time.monotonic()-started,3)
    # Only clone an offline datadir. Do not start or edit the saved source instance.
    started=time.monotonic()
    olddir=WORK/'mysql-old';olddir.mkdir(mode=0o700)
    source_stopped()
    shutil.copytree(str(SOURCE_DB/'data'),str(olddir/'data'),symlinks=False)
    source_stopped()
    timings['offline_original_datadir_copy_seconds']=round(time.monotonic()-started,3)
    old=start_old(olddir)
    init=load_module(Path(__file__).parent/'init_rehearsal.py','private_switch_init')
    init.WORK=WORK;init.MYSQL=WORK/'mysql-new';init.DATABASE=DATABASE_NEW;init.ACCOUNT='gpm_ts_switch_new'
    init.main()
    new=json.loads((WORK/'mysql-new/identity.json').read_text())
    fail(client(WORK/'mysql-new',"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='"+DATABASE_NEW+"'")=='0', 'RESTORE_TARGET_NOT_EMPTY')
    started=time.monotonic()
    with (WORK/'restore-dump-private.log').open('wb') as dump_error, (WORK/'restore-import-private.log').open('wb') as import_error:
        dump=subprocess.Popen(['mysqldump','--no-defaults','--protocol=SOCKET','--socket='+old['socket'],
            '--user=root','--single-transaction','--skip-lock-tables','--skip-add-drop-table',
            '--skip-add-locks','--no-tablespaces','--set-gtid-purged=OFF','--hex-blob',DATABASE_OLD],
            stdout=subprocess.PIPE,stderr=dump_error)
        restored=subprocess.Popen(['mysql','--no-defaults','--protocol=SOCKET','--socket='+new['socket'],
            '--user=root',DATABASE_NEW],stdin=dump.stdout,stdout=subprocess.DEVNULL,stderr=import_error)
        dump.stdout.close()
        restored_code=restored.wait();dump_code=dump.wait()
    fail(restored_code==0 and dump_code==0,'PRIVATE_STREAM_RESTORE_FAILED')
    timings['logical_checkpoint_restore_seconds']=round(time.monotonic()-started,3)
    fail(client(WORK/'mysql-new',"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='"+DATABASE_NEW+"'")=='72','RESTORE_TABLE_COUNT_MISMATCH')
    appkey='base64:'+base64.b64encode(secrets.token_bytes(32)).decode()
    jwt=secrets.token_hex(32)
    for phase,directory,identity in [('old',WORK/'runtime',old),('new',WORK/'next',new)]:
        if (directory/'.env').is_file():
            shutil.copy2(str(directory/'.env'),str(WORK/'preserved'/(phase+'-env-before-private')))
        cache=directory/'bootstrap/cache'
        if cache.exists(): cache.rename(WORK/'preserved'/(phase+'-bootstrap-cache'))
        cache.mkdir(parents=True,exist_ok=True)
        for folder in ['storage/app','storage/logs','storage/framework/views','storage/framework/sessions','storage/framework/cache/data']:
            (directory/folder).mkdir(parents=True,exist_ok=True)
        for name in ['worker-calculation-activation.json','planning-day-activation.json']:
            fail(not (directory/'storage/app'/name).exists(),'ORIGINAL_ACTIVATION_REQUIRES_SEPARATE_REVIEW')
        config={'APP_NAME':'Private TS Switch Rehearsal','APP_ENV':'testing','APP_DEBUG':'false',
            'APP_URL':'https://ts.workstaffcrm.ru','APP_KEY':appkey,'DB_CONNECTION':'mysql','DB_HOST':'localhost',
            'DB_SOCKET':identity['socket'],'DB_DATABASE':identity['database'],'DB_USERNAME':identity['username'],
            'DB_PASSWORD':identity['password'],'CACHE_DRIVER':'array','SESSION_DRIVER':'array','QUEUE_CONNECTION':'sync',
            'BROADCAST_DRIVER':'log','MAIL_MAILER':'log','MAIL_DRIVER':'log','LOG_CHANNEL':'single','JWT_SECRET':jwt,
            'GPM_APP_ORDER_SYNC_ENABLED':'false','GPM_APP_API_URL':'https://invalid.invalid','GPM_APP_API_TOKEN':'',
            'LOGIN_EMAIL_CODE_ENABLED':'false'}
        (directory/'.env').write_text('\n'.join(k+'='+json.dumps(v) for k,v in config.items())+'\n')
        (directory/'.gpm-switch-version').write_text(phase+'\n')
        (directory/'storage/framework/down').write_text('{}')
    shutil.copy2(str(SAVED/'original-data-checks.json'),str(WORK/'original-data-checks.json'))
    result={'new_private_switch_environment_created':True,'timings':timings,'logical_restore_tables':72,
        'resumed_after_python_compatibility_fix':options.resume_after_vendor_copy,
        'saved_sources_preserved':True,'live_crm_accessed':False,'runtime_bootstrapped':False,
        'switch_or_rollback_completed':False,'release_ready':False}
    (WORK/'preparation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    try: main()
    except Exception as error:
        if WORK.exists(): (WORK/'preparation-private-error.log').write_text(repr(error))
        code=str(error) if type(error) is RuntimeError else 'PRIVATE_PREPARATION_FAILED_DIAGNOSTICS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'live_crm_accessed':False}))
        raise SystemExit(1)
