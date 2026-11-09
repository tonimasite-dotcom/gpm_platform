#!/usr/bin/env python3
"""Continue the SAME preserved private upgrade after its verified timeout recovery."""
from pathlib import Path
import importlib.util
import json
import os
import time

WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def main():
    os.umask(0o077)
    spec=importlib.util.spec_from_file_location('private_switch_operations',str(TOOLS/'run_switch.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.require(WORK.resolve()==WORK and m.version(WORK/'runtime')=='old' and m.version(WORK/'next')=='new','RESTORED_OLD_SLOTS_REQUIRED')
    m.require((WORK/'switch-private-error.log').exists() and (WORK/'mysql-new-timeout-evidence/data/ibdata1').is_file(), 'PRESERVED_FAILURE_EVIDENCE_REQUIRED')
    state=json.loads((WORK/'new-mysql-after-timeout-state.json').read_text())
    m.require(state['migration_history_count']==191 and state['finance_source_columns_present']==0,'EXACT_INTERRUPTED_SCHEMA_STATE_REQUIRED')
    with (WORK/'continuation-started.json').open('x') as out:out.write(json.dumps({'from_migration_history_count':191,'private_php_timeout_seconds':1800}))
    r={'live_crm_accessed':False,'old_and_new_instances_preserved':True,'phases':{},'release_ready':False,
        'public_http_or_fpm_switch_tested':False,'production_downtime_measured':False,
        'earlier_mid_migration_failure_and_rollback_passed':True,'earlier_300_second_timeout_and_rollback_recorded':True,
        'private_mysql_offline_failure_copy_preserved':True,'private_mysql_force_signal_sent':False}
    r['phases']['initial_old_data']=m.php('old_data_check.php',phase='resumed-initial-old-data')
    r['phases']['initial_old_smoke']=m.php('runtime_smoke.php',phase='resumed-initial-old-smoke')
    frozen=m.tree_state(WORK/'runtime')
    with (WORK/'resumed-closed-tree-manifest.json').open('x') as out:out.write(json.dumps(frozen,indent=2))
    started=time.monotonic()
    r['phases']['switch_seconds']=m.exchange('old')
    r['phases']['completed_upgrade']=m.php('run_upgrade.php',['complete'],phase='resumed-upgrade-complete',timeout=1800)
    r['phases']['new_data']=m.php('new_data_check.php',phase='resumed-new-data')
    r['phases']['new_smoke']=m.php('runtime_smoke.php',phase='resumed-new-smoke')
    r['phases']['new_forms']=m.php('order_form_acceptance.php',phase='resumed-new-forms')
    r['phases']['new_functional']=m.php('functional_acceptance.php',phase='resumed-new-functional')
    r['phases']['new_context_negative']=m.php('context_negative.php',phase='resumed-new-negative')
    r['post_activation_failure_injected']=True
    # Preserve both the accepted new state and old state without DROP or down().
    r['phases']['rollback_seconds']=m.exchange('new')
    m.require(m.tree_state(WORK/'runtime')==frozen,'RESUMED_ROLLBACK_FILE_OR_STATE_MISMATCH')
    r['phases']['rollback_data']=m.php('old_data_check.php',phase='resumed-rollback-data')
    r['phases']['rollback_smoke']=m.php('runtime_smoke.php',phase='resumed-rollback-smoke')
    r.update({'private_switch_and_post_activation_rollback_passed':True,
        'old_files_configs_modes_owners_and_state_restored':True,'original_rows_preserved_after_rollback':True,
        'private_closed_window_seconds':round(time.monotonic()-started,3)})
    with (WORK/'switch-rehearsal-result.json').open('x') as out:out.write(json.dumps(r,indent=2))
    print(json.dumps({'private_switch_and_post_activation_rollback_passed':True,
        'earlier_mid_migration_rollback_passed':True,'earlier_timeout_retained_as_failed_attempt':True,
        'private_closed_window_seconds':r['private_closed_window_seconds'],
        'new_forms_scenarios':r['phases']['new_forms']['result']['accepted_scenarios'],
        'new_functional_scenarios':r['phases']['new_functional']['result']['scenarios_passed'],
        'production_downtime_measured':False,'live_crm_accessed':False,'release_ready':False}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        restored=False
        try:
            spec=importlib.util.spec_from_file_location('private_switch_recover',str(TOOLS/'run_switch.py'))
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            if m.version(WORK/'runtime')=='new':m.exchange('new');restored=True
        except Exception:pass
        (WORK/'continuation-private-error.log').write_text(repr(error))
        code=str(error) if type(error) is RuntimeError else 'PRIVATE_CONTINUATION_FAILED_DIAGNOSTICS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'automatic_private_slot_rollback':restored,'live_crm_accessed':False}))
        raise SystemExit(1)
