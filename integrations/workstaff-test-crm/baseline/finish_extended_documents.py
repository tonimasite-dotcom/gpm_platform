#!/usr/bin/env python3
"""Stop only the private acceptance DB and export selected safe evidence."""
from pathlib import Path
import json,os,importlib.util,shutil
W=Path('/root/gpm-ts-update/20261106-baseline-01');SWITCH=Path('/root/gpm-ts-update/20261109-switch-01')
def main():
 os.umask(0o077)
 verified=json.loads((W/'extended-documents-verification-20261109.json').read_text());assert verified['success']
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:args=(p/'cmdline').read_bytes().split(b'\0')
  except OSError:continue
  assert not any(os.fsencode(str(W/name)) in args for name in ['run_extended_documents.py','verify_extended_documents.py'])
 spec=importlib.util.spec_from_file_location('private_document_shutdown','/root/gpm-ts-update/switch-tools-20261109/stop_private_mysql.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 stopped=module.stop(W/'rehearsal-mysql')
 states=[]
 for directory in [W/'rehearsal-mysql',W/'sql-recovery-20261109/rehearsal-mysql',
  SWITCH/'mysql-old',SWITCH/'mysql-new',SWITCH/'mysql-new-failed-after-timeout',SWITCH/'mysql-new-timeout-evidence']:
  active=False
  for p in Path('/proc').iterdir():
   if not p.name.isdigit():continue
   try:args=(p/'cmdline').read_bytes().split(b'\0')
   except OSError:continue
   if os.fsencode('--datadir='+str(directory/'data')) in args:active=True
  states.append({'directory':str(directory),'process_absent':not active,'socket_absent':not (directory/'mysql.sock').exists(),
   'data_files_preserved':(directory/'data/ibdata1').is_file()})
 assert all(x['process_absent'] and x['socket_absent'] and x['data_files_preserved'] for x in states)
 report={'success':True,'shutdown':stopped,'all_private_instances':states,'live_mysql_accessed':False,
  'remaining_disk_bytes':shutil.disk_usage(str(W)).free}
 with (W/'extended-documents-final-status-20261109.json').open('x') as out:out.write(json.dumps(report,indent=2))
 out=W/'extended-documents-safe-export-20261109';out.mkdir(mode=0o700)
 files={'verification.json':W/'extended-documents-verification-20261109.json',
  'candidate-corrections.json':W/'document-candidate-corrections-20261109.json',
  'shutdown.json':W/'extended-documents-final-status-20261109.json',
  'before-corrections.json':W/'extended-document-fixtures-2ad94bb11e78/safe-result.json',
  'after-corrections.json':W/'extended-document-fixtures-862723389003/safe-result.json',
  'fixture-vat-error.json':W/'extended-document-fixtures-67430b9c32c6/safe-result.json',
  'fixture-application-return-error.json':W/'extended-document-fixtures-433836cb676f/safe-result.json'}
 for name,source in files.items():
  data=json.loads(source.read_text())
  with (out/name).open('x') as stream:stream.write(json.dumps(data,indent=2)+'\n')
 print(json.dumps({'success':True,'all_six_private_instances_off':True,'data_preserved':True,'safe_reports_exported':len(files),
  'remaining_disk_bytes':report['remaining_disk_bytes'],'live_crm_changed':False}))
if __name__=='__main__':main()
