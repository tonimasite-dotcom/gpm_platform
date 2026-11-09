#!/usr/bin/env python3
"""Correct the copied checker root binding; preserve all earlier checker evidence."""
from pathlib import Path
import hashlib,json,os

W=Path('/root/gpm-ts-update/20261109-switch-01')
T=Path('/root/gpm-ts-update/switch-tools-20261109')
os.umask(0o077)
assert W.resolve()==W and (W/'runtime/.gpm-switch-version').read_text().strip()=='old'
backup=W/'preserved/checker-root-before-fix';assert not backup.exists();backup.mkdir(mode=0o700)
changes=[]
for name in ['new_data_check.php','final_new_data_check.php']:
 p=T/name;s=p.read_text();old="$root = $work . '/candidate';";new="$root = $work . '/runtime';"
 assert s.count(old)==1
 (backup/name).write_bytes(p.read_bytes())
 before=hashlib.sha256(p.read_bytes()).hexdigest();p.write_text(s.replace(old,new,1))
 changes.append({'file':name,'before_sha256':before,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
r={'private_checker_root_binding_fixed':True,'guards_removed':False,'application_or_database_changed':False,'changes':changes}
with (W/'checker-root-fix.json').open('x') as out:out.write(json.dumps(r,indent=2))
print(json.dumps(r))
