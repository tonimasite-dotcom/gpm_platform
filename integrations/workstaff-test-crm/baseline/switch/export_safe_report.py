#!/usr/bin/env python3
"""Export only explicitly selected, structured evidence; no env/SQL/raw logs."""
from pathlib import Path
import json,os,hashlib,ast,shutil
W=Path('/root/gpm-ts-update/20261109-switch-01');S=Path('/root/gpm-ts-update/20261106-baseline-01')
def load(name):return json.loads((W/name).read_text())
def main():
 os.umask(0o077);out=W/'safe-export';out.mkdir()
 report=load('switch-rehearsal-result.json')
 assert report['success'] and (W/'runtime/.gpm-switch-version').read_text().strip()=='old'
 # Row hashes/counts remain in the private originals. Export the preservation decision and explanation.
 for phase in ['new_data','new_data_after_tests']:
  data=report['phases'][phase]['result']
  for key in ['table_checks','changed_tables']:data.pop(key,None)
 checks=[]
 for folder in [S/'rehearsal-mysql',S/'sql-recovery-20261109/rehearsal-mysql',W/'mysql-old',W/'mysql-new',
                W/'mysql-new-failed-after-timeout',W/'mysql-new-timeout-evidence']:
  running=False
  for p in Path('/proc').iterdir():
   if not p.name.isdigit():continue
   try:args=(p/'cmdline').read_bytes().split(b'\0')
   except OSError:continue
   if os.fsencode('--datadir='+str(folder/'data')) in args:running=True
  checks.append({'directory':str(folder),'process_absent':not running,'socket_absent':not (folder/'mysql.sock').exists(),
   'data_files_preserved':(folder/'data/ibdata1').is_file()})
 assert all(x['process_absent'] and x['socket_absent'] and x['data_files_preserved'] for x in checks)
 report['all_private_instances_off']=checks
 report['completed_upgrade']=load('final-upgrade-completed.json')
 report['earlier_completed_upgrade']=load('upgrade-completed.json')
 report['separate_logical_restore_seconds']=load('fresh-upgrade-database.json')['logical_restore_seconds']
 report['private_buffer_pool_bytes']=load('private-resource-adjustment.json')['actual_buffer_pool_bytes']
 report['initial_injected_migration_failure']=load('upgrade-injected-result.json')
 report['initial_rollback_original_data']=load('first-rollback-data-result.json')
 report['original_old_slot_files']=len(load('final-closed-tree-manifest.json'))
 report['remaining_disk_bytes']=shutil.disk_usage(str(W)).free
 report['failed_runs_disclosed']=['Initial preparation Python 3.7 copytree compatibility error, resumed before DB setup.',
  'Initial 300-second upgrade timeout on finance-source ALTER, old slot restored.',
  'Resume of timed-out private InnoDB copy failed with missing plannings in engine; copies preserved offline.',
  'Fresh upgrade completed but wrapper rejected informational console lines; old slot restored.',
  'Final upgrade completed but checker used candidate instead of runtime root; old slot restored.',
  'Checker binding fixed without removing identity guards; acceptance resumed on completed final database.']
 files={'switch-result.json':report,'email-before-fix.json':load('email-code-before-fix-result.json'),
  'email-binding-fix.json':load('email-code-binding-fix.json'),'email-after-fix.json':load('accepted-final-email-result.json'),
  'checker-root-fix.json':load('checker-root-fix.json'),'php-lint.json':load('changed-tools-lint.json'),
  'shutdown.json':load('final-private-shutdown.json'),'ts-fpm-readonly.json':load('ts-fpm-resolved-readonly.json')}
 parsed=[]
 for p in Path('/root/gpm-ts-update/switch-tools-20261109').glob('*.py'):ast.parse(p.read_text());parsed.append(p.name)
 files['python-syntax.json']={'success':True,'files':sorted(parsed),'mode':'ast_parse_no_execution'}
 for name,value in files.items():
  with (out/name).open('x') as stream:stream.write(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'safe_reports':len(files),'all_private_instances_off':True,'original_old_slot_files':report['original_old_slot_files'],
  'remaining_disk_bytes':report['remaining_disk_bytes'],'live_crm_changed':False}))
if __name__=='__main__':main()
