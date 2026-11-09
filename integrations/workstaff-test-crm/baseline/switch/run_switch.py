#!/usr/bin/env python3
"""Atomic private old/new switching, two injected failures, preserved rollback."""
from pathlib import Path
import ctypes
import errno
import hashlib
import json
import os
import stat
import subprocess
import time

WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def require(value,code):
    if not value:raise RuntimeError(code)


def version(path):
    require(path.resolve()==path,'REAL_SLOT_DIRECTORY_REQUIRED')
    marker=path/'.gpm-switch-version'
    require(marker.resolve()==marker and marker.is_file(),'REGULAR_VERSION_MARKER_REQUIRED')
    value=marker.read_text().strip()
    require(value in ['old','new'],'KNOWN_PRIVATE_VERSION_REQUIRED')
    return value


def exchange(expected):
    a=WORK/'runtime';b=WORK/'next'
    require(WORK.resolve()==WORK and version(a)==expected and version(b)!=expected,'EXACT_SWITCH_STATE_REQUIRED')
    require((a/'storage/framework/down').is_file() and (b/'storage/framework/down').is_file(),'BOTH_SLOTS_MUST_REMAIN_CLOSED')
    # No symlink/mount imitation: exchange two actual directories on one filesystem.
    require(a.stat().st_dev==b.stat().st_dev,'ATOMIC_EXCHANGE_FILESYSTEM_REQUIRED')
    libc=ctypes.CDLL(None,use_errno=True)
    require(hasattr(libc,'renameat2'),'ATOMIC_EXCHANGE_NOT_AVAILABLE')
    started=time.monotonic()
    result=libc.renameat2(-100,os.fsencode(str(a)),-100,os.fsencode(str(b)),2)
    if result!=0:raise RuntimeError('ATOMIC_EXCHANGE_FAILED_'+str(ctypes.get_errno()))
    require(version(a)!=expected and version(b)==expected,'ATOMIC_EXCHANGE_POSTCONDITION_FAILED')
    return round(time.monotonic()-started,6)


def tree_state(root):
    require(root.resolve()==root,'REAL_TREE_REQUIRED')
    result={}
    for directory,subdirs,files in os.walk(str(root),followlinks=False):
        for name in subdirs+files:
            path=Path(directory)/name
            if path.is_dir() and not path.is_symlink():continue
            info=path.lstat();entry={'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}
            if path.is_symlink():entry.update({'type':'link','target':os.readlink(str(path))})
            else:
                require(stat.S_ISREG(info.st_mode),'UNEXPECTED_TREE_OBJECT')
                value=hashlib.sha256()
                with path.open('rb') as source:
                    for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
                entry.update({'type':'file','bytes':info.st_size,'sha256':value.hexdigest()})
            result[str(path.relative_to(root))]=entry
    return result


def php(name,args=None,expected=0,namespace=True,phase='check',timeout=240):
    env={k:v for k,v in os.environ.items() if not k.startswith(('DB_','APP_','GPM_','CRM_'))}
    env.update({'GPM_TS_SWITCH':'1','GPM_TS_REHEARSAL':'1','CRM_DOCUMENT_COST_WRITERS_STOPPED':'1',
        'GPM_SWITCH_EXPECT_VERSION':version(WORK/'runtime')})
    command=(['unshare','--net'] if namespace else [])+['nice','-n','10','php','-d','memory_limit=512M',str(TOOLS/name)]+(args or [])
    started=time.monotonic()
    result=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=timeout)
    with (WORK/(phase+'-console-private.log')).open('x') as out:out.write(result.stdout+'\n'+result.stderr)
    try:report=json.loads(result.stdout)
    except ValueError:
        # Console commands may emit informational lines before our structured result.
        # Keep all raw output private; accept exactly one explicit final check report.
        reports=[]
        for line in result.stdout.splitlines():
            try:value=json.loads(line)
            except ValueError:continue
            if isinstance(value,dict) and any(k in value for k in ['success','saved_rehearsal_data_acceptance_passed','expected_failure_injected']):
                reports.append(value)
        require(len(reports)==1,'PRIVATE_CHECK_AMBIGUOUS_OUTPUT_'+phase.upper().replace('-','_'))
        report=reports[0]
    with (WORK/(phase+'-result.json')).open('x') as out:out.write(json.dumps(report,indent=2))
    require(result.returncode==expected,'PRIVATE_CHECK_EXIT_FAILED_'+phase.upper().replace('-','_'))
    if expected==0:
        require(report.get('success',report.get('saved_rehearsal_data_acceptance_passed',False)),
            'PRIVATE_CHECK_REJECTED_'+phase.upper().replace('-','_'))
    return {'result':report,'elapsed_seconds':round(time.monotonic()-started,3)}


def main():
    os.umask(0o077)
    require(WORK.resolve()==WORK and version(WORK/'runtime')=='old' and version(WORK/'next')=='new','INITIAL_CLOSED_SLOTS_REQUIRED')
    with (WORK/'switch-run-started.json').open('x') as out:out.write(json.dumps({'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}))
    report={'live_crm_accessed':False,'old_and_new_instances_preserved':True,'phases':{},'release_ready':False,
        'public_http_or_fpm_switch_tested':False,'production_downtime_measured':False}
    started=time.monotonic()
    report['phases']['old_smoke']=php('runtime_smoke.php',phase='initial-old-smoke')
    report['phases']['old_data']=php('old_data_check.php',phase='initial-old-data')
    report['phases']['old_context_negative']=php('context_negative.php',phase='initial-old-negative')
    report['phases']['outside_netns_rejected']=php('context_negative.php',['prebootstrap-denial'],namespace=False,phase='outside-netns-negative')
    frozen=tree_state(WORK/'runtime')
    with (WORK/'original-closed-tree-manifest.json').open('x') as out:out.write(json.dumps(frozen,indent=2))
    window=time.monotonic()
    report['phases']['first_switch_seconds']=exchange('old')
    report['phases']['injected_mid_migration_failure']=php('run_upgrade.php',['fail-after-three'],expected=20,phase='upgrade-injected')
    report['phases']['first_rollback_seconds']=exchange('new')
    require(tree_state(WORK/'runtime')==frozen,'FIRST_ROLLBACK_FILE_OR_STATE_MISMATCH')
    report['phases']['first_rollback_data']=php('old_data_check.php',phase='first-rollback-data')
    report['phases']['first_rollback_smoke']=php('runtime_smoke.php',phase='first-rollback-smoke')
    report['first_private_closed_window_seconds']=round(time.monotonic()-window,3)
    # The smoke adds only its private login log; freeze the exact current old tree again.
    frozen=tree_state(WORK/'runtime')
    with (WORK/'second-closed-tree-manifest.json').open('x') as out:out.write(json.dumps(frozen,indent=2))
    window=time.monotonic()
    report['phases']['second_switch_seconds']=exchange('old')
    report['phases']['completed_upgrade']=php('run_upgrade.php',['complete'],phase='upgrade-complete',timeout=300)
    report['phases']['new_data']=php('new_data_check.php',phase='new-data')
    report['phases']['new_smoke']=php('runtime_smoke.php',phase='new-smoke')
    report['phases']['new_forms']=php('order_form_acceptance.php',phase='new-forms')
    report['phases']['new_functional']=php('functional_acceptance.php',phase='new-functional')
    report['phases']['new_context_negative']=php('context_negative.php',phase='new-negative')
    # Inject a deployment-level failure AFTER successful new runtime acceptance.
    report['post_activation_failure_injected']=True
    report['phases']['second_rollback_seconds']=exchange('new')
    require(tree_state(WORK/'runtime')==frozen,'SECOND_ROLLBACK_FILE_OR_STATE_MISMATCH')
    report['phases']['second_rollback_data']=php('old_data_check.php',phase='second-rollback-data')
    report['phases']['second_rollback_smoke']=php('runtime_smoke.php',phase='second-rollback-smoke')
    report['second_private_closed_window_seconds']=round(time.monotonic()-window,3)
    require(version(WORK/'runtime')=='old' and version(WORK/'next')=='new','FINAL_RESTORED_VERSION_MISMATCH')
    report.update({'private_switch_and_two_rollbacks_passed':True,'old_files_configs_modes_owners_and_state_restored':True,
        'original_rows_preserved_after_both_rollbacks':True,'elapsed_seconds':round(time.monotonic()-started,3)})
    with (WORK/'switch-rehearsal-result.json').open('x') as out:out.write(json.dumps(report,indent=2))
    print(json.dumps({'private_switch_and_two_rollbacks_passed':True,
        'first_private_closed_window_seconds':report['first_private_closed_window_seconds'],
        'second_private_closed_window_seconds':report['second_private_closed_window_seconds'],
        'old_data_and_file_state_restored':True,'old_known_rate_bug_preserved_as_baseline':True,
        'new_forms_scenarios':report['phases']['new_forms']['result']['accepted_scenarios'],
        'new_functional_scenarios':report['phases']['new_functional']['result']['scenarios_passed'],
        'live_crm_accessed':False,'production_downtime_measured':False,'release_ready':False}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        # A failed experiment must return to the preserved old slot, never drop/restore over data.
        restored=False
        try:
            if version(WORK/'runtime')=='new' and version(WORK/'next')=='old':
                exchange('new');restored=True
        except Exception:pass
        (WORK/'switch-private-error.log').write_text(repr(error))
        code=str(error) if type(error) is RuntimeError else 'PRIVATE_SWITCH_FAILED_DIAGNOSTICS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'automatic_private_slot_rollback':restored,
            'live_crm_accessed':False,'release_ready':False}))
        raise SystemExit(1)
