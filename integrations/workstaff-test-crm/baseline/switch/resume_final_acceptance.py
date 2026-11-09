#!/usr/bin/env python3
"""Accept the completed private upgrade, then verify an atomic old-slot rollback.

This resumes after harness failures; it does NOT claim one uninterrupted run.
"""
from pathlib import Path
import importlib.util,json,os,time,hashlib
W=Path('/root/gpm-ts-update/20261109-switch-01');T=Path('/root/gpm-ts-update/switch-tools-20261109')
def main():
 os.umask(0o077)
 spec=importlib.util.spec_from_file_location('acceptance_switch',str(T/'run_switch.py'))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 try:
  m.require(m.version(W/'runtime')=='old' and m.version(W/'next')=='new','CLOSED_SLOTS_REQUIRED')
  m.require(json.loads((W/'final-upgrade-completed.json').read_text())['success'],'COMPLETED_UPGRADE_REQUIRED')
  frozen=json.loads((W/'final-closed-tree-manifest.json').read_text())
  m.require(m.tree_state(W/'runtime')==frozen,'OLD_FILE_STATE_MISMATCH')
  r={'success':False,'resumed_after_harness_failures':True,'single_uninterrupted_run':False,
   'release_ready':False,'public_fpm_switch_tested':False,'production_downtime_measured':False,
   'live_crm_changed':False,'phases':{}}
  p=r['phases'];started=time.monotonic();p['switch_seconds']=m.exchange('old')
  for key,name in [('email','email_code_acceptance.php'),('new_data','final_new_data_check.php'),
   ('smoke','runtime_smoke.php'),('forms','order_form_acceptance.php'),
   ('functional','functional_acceptance.php'),('negative_context','context_negative.php'),
   ('new_data_after_tests','final_new_data_check.php')]:
   p[key]=m.php(name,phase='accepted-final-'+key.replace('_','-'))
  names=['.env','storage/app/worker-calculation-activation.json','storage/app/planning-day-activation.json',
   '.gpm-switch-version','.gpm-switch-generation']
  state={name:hashlib.sha256((W/'runtime'/name).read_bytes()).hexdigest() for name in names}
  r['post_acceptance_failure_injected']=True;rollback=time.monotonic()
  p['rollback_exchange_seconds']=m.exchange('new')
  m.require(m.tree_state(W/'runtime')==frozen,'OLD_FULL_TREE_ROLLBACK_MISMATCH')
  m.require(all(hashlib.sha256((W/'next'/name).read_bytes()).hexdigest()==value for name,value in state.items()),'NEW_STATE_NOT_PRESERVED')
  p['rollback_data']=m.php('old_data_check.php',phase='accepted-final-rollback-data')
  p['rollback_smoke']=m.php('runtime_smoke.php',phase='accepted-final-rollback-smoke')
  r.update({'success':True,'private_upgrade_acceptance_and_rollback_passed':True,
   'old_file_contents_modes_owners_restored':True,'old_original_rows_preserved':True,
   'new_activation_state_preserved':True,'rollback_verification_seconds':round(time.monotonic()-rollback,3),
   'acceptance_and_rollback_segment_seconds':round(time.monotonic()-started,3)})
  with (W/'switch-rehearsal-result.json').open('x') as out:out.write(json.dumps(r,indent=2))
  print(json.dumps({k:v for k,v in r.items() if k!='phases'}))
 finally:
  if m.version(W/'runtime')=='new':m.exchange('new')
if __name__=='__main__':main()
