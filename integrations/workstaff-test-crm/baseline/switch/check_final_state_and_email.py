#!/usr/bin/env python3
from pathlib import Path
import importlib.util,json,os
W=Path('/root/gpm-ts-update/20261109-switch-01');T=Path('/root/gpm-ts-update/switch-tools-20261109')
os.umask(0o077)
spec=importlib.util.spec_from_file_location('current_final_check_operations',str(T/'run_switch.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
try:
 m.require(m.version(W/'runtime')=='old' and m.version(W/'next')=='new','RESTORED_OLD_RUNTIME_REQUIRED')
 original=json.loads((W/'final-closed-tree-manifest.json').read_text())
 m.require(m.tree_state(W/'runtime')==original,'OLD_TREE_RESTORE_MISMATCH')
 m.exchange('old')
 data=m.php('final_new_data_check.php',phase='fixed-guard-final-data')
 email=m.php('email_code_acceptance.php',phase='email-code-before-fix',expected=1)
 m.require(email['result'].get('other_user_code_returned_jwt') is True,'EXPECTED_CROSS_USER_CODE_FINDING_NOT_REPRODUCED')
 print(json.dumps({'new_final_data_preservation_verified':True,'email_code_cross_user_finding_reproduced':True,'live_crm_changed':False}))
finally:
 if m.version(W/'runtime')=='new':m.exchange('new')
