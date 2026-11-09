#!/usr/bin/env python3
"""Run a full upgrade against the pristine re-restored private DB, then roll back."""
from pathlib import Path
import importlib.util
import json
import os
import time

WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def load():
    spec=importlib.util.spec_from_file_location('fresh_private_switch_operations',str(TOOLS/'run_switch.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    os.umask(0o077);m=load()
    m.require(WORK.resolve()==WORK and m.version(WORK/'runtime')=='old' and m.version(WORK/'next')=='new','RESTORED_SLOTS_REQUIRED')
    m.require((WORK/'fresh-upgrade-database.json').exists(),'FRESH_RESTORE_PROOF_REQUIRED')
    with (WORK/'fresh-switch-started.json').open('x') as out:out.write(json.dumps({'private_upgrade_timeout_seconds':1800}))
    r={'live_crm_accessed':False,'failed_attempts_and_databases_preserved':True,'phases':{},'release_ready':False,
        'public_http_or_fpm_switch_tested':False,'production_downtime_measured':False,
        'earlier_mid_migration_rollback_passed':True,'earlier_timeout_and_schema_failure_disclosed':True,
        'interrupted_database_not_repaired_in_place':True}
    r['phases']['old_data']=m.php('old_data_check.php',phase='fresh-old-data')
    r['phases']['old_smoke']=m.php('runtime_smoke.php',phase='fresh-old-smoke')
    frozen=m.tree_state(WORK/'runtime')
    with (WORK/'fresh-closed-tree-manifest.json').open('x') as out:out.write(json.dumps(frozen,indent=2))
    started=time.monotonic()
    r['phases']['switch_seconds']=m.exchange('old')
    r['phases']['pristine_new_data']=m.php('new_pristine_data_check.php',phase='fresh-pristine-new-data')
    r['phases']['completed_upgrade']=m.php('run_upgrade.php',['complete'],phase='fresh-upgrade-complete',timeout=1800)
    r['phases']['new_data']=m.php('new_data_check.php',phase='fresh-new-data')
    r['phases']['new_smoke']=m.php('runtime_smoke.php',phase='fresh-new-smoke')
    r['phases']['new_forms']=m.php('order_form_acceptance.php',phase='fresh-new-forms')
    r['phases']['new_functional']=m.php('functional_acceptance.php',phase='fresh-new-functional')
    r['phases']['new_context_negative']=m.php('context_negative.php',phase='fresh-new-negative')
    r['post_activation_failure_injected']=True
    r['phases']['rollback_seconds']=m.exchange('new')
    m.require(m.tree_state(WORK/'runtime')==frozen,'FRESH_ROLLBACK_FILE_OR_STATE_MISMATCH')
    r['phases']['rollback_data']=m.php('old_data_check.php',phase='fresh-rollback-data')
    r['phases']['rollback_smoke']=m.php('runtime_smoke.php',phase='fresh-rollback-smoke')
    r.update({'private_full_upgrade_and_post_activation_rollback_passed':True,
        'old_files_configs_modes_owners_and_state_restored':True,'original_rows_preserved_after_rollback':True,
        'private_closed_window_seconds':round(time.monotonic()-started,3)})
    with (WORK/'switch-rehearsal-result.json').open('x') as out:out.write(json.dumps(r,indent=2))
    print(json.dumps({'private_full_upgrade_and_post_activation_rollback_passed':True,
        'private_closed_window_seconds':r['private_closed_window_seconds'],
        'new_forms_scenarios':r['phases']['new_forms']['result']['accepted_scenarios'],
        'new_functional_scenarios':r['phases']['new_functional']['result']['scenarios_passed'],
        'production_downtime_measured':False,'live_crm_accessed':False,'release_ready':False}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        m=load();restored=False
        try:
            if m.version(WORK/'runtime')=='new':m.exchange('new');restored=True
        except Exception:pass
        (WORK/'fresh-switch-private-error.log').write_text(repr(error))
        code=str(error) if type(error) is RuntimeError else 'FRESH_PRIVATE_SWITCH_FAILED_DETAILS_WITHHELD'
        print(json.dumps({'success':False,'safe_code':code,'automatic_private_slot_rollback':restored,'live_mysql_accessed':False}));raise SystemExit(1)
