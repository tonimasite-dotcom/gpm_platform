"""Enable only the inspected ts CRM after a verified release/backup. Dry run by default."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile

ROOT=Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
BACKUP=Path('/root/gpm-snapshots/20261015-before-sync')
CRON=Path('/etc/cron.d/gpm-test-crm-sync')
EXPECTED={
    'app/Services/Order/GpmAppOrderPublisher.php':'906dacd8a5a1366ada2ad842878305c2d3c7916b9d6f9c05544996ac27668f95',
    'app/Services/Order/GpmAppOrderSync.php':'6a6737a913c51d1f1a2ca63f846a2492280cdf951737d77bec7ef5f13db2a080',
    'app/Services/Order/GpmOrderSyncPlan.php':'eec40e1c549b65d28a6a9b801c2f70aa41442b623cd96d5b4d5509ca499903a4',
    'app/Console/Commands/SyncGpmAppOrders.php':'320998e2b3d55a9c13984051ae887e31a18a5a16ff4ab9d8d001baf247856735',
}
LINE=('* * * * * gruzpiter /usr/bin/flock -n '+str(ROOT)+'/storage/app/gpm-app-sync/cron.lock '
      '/usr/bin/php '+str(ROOT)+'/artisan gpm:sync-orders >> '+str(ROOT)+'/storage/logs/gpm-order-sync.log 2>&1\n')
CRON_BYTES=('# GPM sync: only ts.workstaffcrm.ru; no Laravel scheduler.\nSHELL=/bin/sh\nPATH=/usr/bin:/bin\n'+LINE).encode()

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic(path,data,uid,gid,mode):
    descriptor,name=tempfile.mkstemp(prefix='.gpm-sync-',dir=str(path.parent))
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chown(name,uid,gid);os.chmod(name,mode);os.replace(name,str(path))
    finally:
        if os.path.exists(name):os.unlink(name)

def probe(bundle):
    result=subprocess.run(['runuser','-u','gruzpiter','--','php',str(bundle/'probe-test-crm.php')],
                          cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise RuntimeError('API/runtime preflight failed; no credentials printed')
    value=json.loads(result.stdout)
    if not value['test_crm_only'] or not value['new_api_protocol_present'] or not value['integration_auth_valid']:
        raise RuntimeError('Wrong CRM or backend protocol')
    if value['configuration_cached']:raise RuntimeError('Review cached configuration before changing env')
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0 or ROOT.resolve()!=ROOT or BACKUP.resolve()!=BACKUP:
        raise RuntimeError('Unexpected user or scope')
    for name,digest in EXPECTED.items():
        path=ROOT/name
        if path.is_symlink() or ROOT not in path.resolve().parents or sha(path)!=digest:
            raise RuntimeError('Installed CRM code changed; review before enabling')
    expected=json.loads((BACKUP/'encrypted-manifest.json').read_text())
    if expected['scope']!=str(ROOT) or sha(BACKUP/'test-crm-before-sync.tar.gz.age')!=expected['sha256']:
        raise RuntimeError('Missing/mismatching pre-sync backup')
    if CRON.is_symlink() or (CRON.exists() and CRON.read_bytes()!=CRON_BYTES):
        raise RuntimeError('Existing cron differs; refusing to overwrite')
    if not Path('/usr/bin/flock').is_file() or subprocess.run(['systemctl','is-active','--quiet','cron']).returncode:
        raise RuntimeError('Cron/flock is not available')
    bundle=Path(__file__).resolve().parent
    before=probe(bundle)
    env=ROOT/'.env'
    if env.is_symlink():raise RuntimeError('Unexpected env symlink')
    old=env.read_bytes();info=env.stat();text=old.decode('utf-8')
    pattern=r'(?m)^[ \t]*(?:export[ \t]+)?GPM_APP_ORDER_SYNC_ENABLED[ \t]*=.*$'
    matches=list(re.finditer(pattern,text))
    if len(matches)>1:raise RuntimeError('Duplicate sync flag')
    if matches:
        text=re.sub(pattern,'GPM_APP_ORDER_SYNC_ENABLED=true'+('\r' if '\r\n' in text else ''),text)
    else:
        newline='\r\n' if '\r\n' in text else '\n'
        text=text.rstrip('\r\n')+newline+'GPM_APP_ORDER_SYNC_ENABLED=true'+newline
    new=text.encode('utf-8')
    print(json.dumps({'test_crm_root':str(ROOT),'before':before,'env_change':old!=new,'cron_path':str(CRON),'apply':args.apply}))
    if not args.apply:return
    if (BACKUP/'config-before-enable.env.age').exists():
        raise RuntimeError('Prior activation backup exists; review before retry')
    # Encrypt the exact current configuration before replacing its single flag.
    subprocess.run([str(BACKUP/'age'),'--encrypt','--recipient',(BACKUP/'age-recipient.txt').read_text().strip(),
                    '--output',str(BACKUP/'config-before-enable.env.age'),str(env)],check=True,stdout=subprocess.DEVNULL)
    user=pwd.getpwnam('gruzpiter')
    state=ROOT/'storage/app/gpm-app-sync'
    if state.is_symlink() or ROOT not in state.resolve().parents:raise RuntimeError('Unexpected sync state path')
    state.mkdir(mode=0o700,exist_ok=True);os.chown(str(state),user.pw_uid,user.pw_gid);os.chmod(str(state),0o700)
    log=ROOT/'storage/logs/gpm-order-sync.log'
    if log.is_symlink():raise RuntimeError('Unexpected sync log path')
    if not log.exists():
        log.touch(mode=0o640);os.chown(str(log),user.pw_uid,user.pw_gid)
    cron_before=CRON.read_bytes() if CRON.exists() else None
    try:
        if env.read_bytes()!=old:raise RuntimeError('Env changed during activation')
        atomic(env,new,info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))
        after=probe(bundle)
        if not after['sync_enabled']:raise RuntimeError('Sync flag did not take effect')
        completed=subprocess.run(['runuser','-u','gruzpiter','--','php',str(ROOT/'artisan'),'gpm:sync-orders'],
                                 cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if completed.returncode:raise RuntimeError('Initial sync deferred orders; review before scheduling')
        output=completed.stdout.decode('utf-8').strip()
        if not re.search(r'Synced: [0-9]+; deferred: 0',output):raise RuntimeError('Unexpected sync result')
        atomic(CRON,CRON_BYTES,0,0,0o644)
        print(json.dumps({'enabled':True,'cron_installed':True,'initial_sync':output,'other_crm_touched':False}))
    except BaseException:
        if env.read_bytes()==new:atomic(env,old,info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))
        if CRON.exists() and CRON.read_bytes()==CRON_BYTES:
            if cron_before is None:CRON.unlink()
            else:atomic(CRON,cron_before,0,0,0o644)
        raise

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Test CRM activation stopped ('+type(error).__name__+'); credentials not printed.')
        raise SystemExit(1)
