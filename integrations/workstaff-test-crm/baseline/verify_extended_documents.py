#!/usr/bin/env python3
"""Verify code/row preservation and regression, preserving older reports."""
from pathlib import Path
import json,hashlib,subprocess,os
W=Path('/root/gpm-ts-update/20261106-baseline-01');P=W/'acceptance-20261109/payload'
def php(name,phase):
 result=subprocess.run(['unshare','--net','nice','-n','10','php','-d','memory_limit=512M',str(P/name)],
  env=dict(os.environ,GPM_TS_REHEARSAL='1'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=240)
 with (W/(phase+'-console-private.log')).open('x') as out:out.write(result.stdout+'\n'+result.stderr)
 report=json.loads(result.stdout)
 with (W/(phase+'-result.json')).open('x') as out:out.write(json.dumps(report,indent=2))
 assert result.returncode==0 and report.get('success',report.get('saved_rehearsal_data_acceptance_passed',False)), 'PRIVATE_CHECK_FAILED'
 return report
def main():
 os.umask(0o077);output=W/'extended-documents-verification-20261109.json';assert not output.exists()
 for name,value in {'original-data-checks.json':'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec',
  'rehearse_migrations.php':'0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259'}.items():
  assert hashlib.sha256((W/name).read_bytes()).hexdigest()==value
 manifest=json.loads((W/'candidate-manifest-documents-20261109.json').read_text())
 assert all(hashlib.sha256((W/'candidate'/name).read_bytes()).hexdigest()==value for name,value in manifest.items())
 lint=['extended_document_acceptance.php']
 for name in lint:
  assert subprocess.run(['php','-l',str(P/name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode==0
 assert subprocess.run(['php','-l',str(W/'candidate/app/Services/Document/DocumentData/ActDataService.php')],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode==0
 for original,target in [('order_form_acceptance.php','extended_documents_forms.php'),('functional_acceptance.php','extended_documents_functional.php')]:
  code=(P/original).read_text()
  if original.startswith('order_form'):code=code.replace('order-form-','extended-documents-order-form-').replace('legacy-financial-','extended-documents-legacy-financial-')
  else:code=code.replace('functional-','extended-documents-functional-')
  with (P/target).open('x') as out:out.write(code)
 forms=php('extended_documents_forms.php','extended-documents-forms')
 functional=php('extended_documents_functional.php','extended-documents-functional')
 preserved=php('diagnose_original_data.php','extended-documents-data')
 assert preserved['all_original_rows_preserved'] and preserved['expected_new_cash_audit_verified']
 for key in ['table_checks','changed_tables']:preserved.pop(key,None)
 report={'success':True,'forms_scenarios':forms['accepted_scenarios'],'functional_scenarios':functional['scenarios_passed'],
  'original_data':preserved,'changed_php_files_lint_passed':2,'candidate_files_verified':len(manifest),
  'candidate_manifest_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
  'candidate_next_switch_slot_not_updated':True,'live_crm_changed':False,'release_ready':False}
 with output.open('x') as out:out.write(json.dumps(report,indent=2))
 print(json.dumps({'success':True,'forms_scenarios':forms['accepted_scenarios'],'functional_scenarios':functional['scenarios_passed'],
  'original_tables_checked':preserved['tables_checked'],'all_original_rows_preserved':True}))
if __name__=='__main__':main()
