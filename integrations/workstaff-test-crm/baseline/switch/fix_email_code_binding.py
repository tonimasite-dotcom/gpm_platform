#!/usr/bin/env python3
"""Prepare a narrow auth fix in two private code artifacts, never a live site."""
from pathlib import Path
import hashlib,json,os,shutil
S=Path('/root/gpm-ts-update/20261106-baseline-01')
W=Path('/root/gpm-ts-update/20261109-switch-01')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 os.umask(0o077)
 assert (W/'runtime/.gpm-switch-version').read_text().strip()=='old'
 evidence=json.loads((W/'email-code-before-fix-result.json').read_text())
 assert evidence['other_user_code_returned_jwt'] is True
 relative='app/Http/Controllers/Auth/LoginController.php'
 paths=[S/'candidate'/relative,W/'next'/relative]
 expected='a8b9b1bd885716792a2c7ab19ddcd38df6dd9c0bbeab66bf9cfa6b503f6402c2'
 before="'max:255', 'exists:users,remember_token'"
 after="'max:255', \\Illuminate\\Validation\\Rule::exists('users', 'remember_token')->where('email', (string) $request->input('email'))"
 assert all(p.resolve()==p and sha(p)==expected and p.read_text().count(before)==1 for p in paths)
 folder=W/'preserved/email-code-binding-before-fix';folder.mkdir()
 for i,p in enumerate(paths):
  shutil.copy2(str(p),str(folder/('LoginController-'+str(i)+'.php')))
  p.write_text(p.read_text().replace(before,after,1))
 assert sha(paths[0])==sha(paths[1])
 old=json.loads((S/'candidate-manifest-order-forms-20261109.json').read_text())
 assert all(sha(S/'candidate'/name)==value for name,value in old.items() if name!=relative)
 old[relative]=sha(paths[0])
 manifest=S/'candidate-manifest-email-code-20261109.json'
 with manifest.open('x') as out:out.write(json.dumps(old,indent=2,sort_keys=True))
 result={'candidate_only':True,'live_crm_changed':False,'email_code_setting_changed':False,
  'verification_scoped_to_requested_email':True,'login_controller_before_sha256':expected,
  'login_controller_after_sha256':sha(paths[0]),'candidate_files':len(old),
  'candidate_manifest_sha256':hashlib.sha256(json.dumps(old,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 with (W/'email-code-binding-fix.json').open('x') as out:out.write(json.dumps(result,indent=2))
 print(json.dumps(result))
if __name__=='__main__':main()
