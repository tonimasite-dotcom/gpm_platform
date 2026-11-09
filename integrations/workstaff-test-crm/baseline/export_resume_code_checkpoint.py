#!/usr/bin/env python3
"""Stream a private code-only checkpoint for local encryption; never export DBs/keys."""
from pathlib import Path
import hashlib,json,os,sys,tarfile
W=Path('/root/gpm-ts-update/20261106-baseline-01');S=Path('/root/gpm-ts-update/20261109-switch-01')
def main():
 assert W.resolve()==W and S.resolve()==S
 manifest=json.loads((W/'candidate-manifest-documents-20261109.json').read_text())
 assert (hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()==
  'f47de6309adb543870d844b043529124720fe1501d32fb447a74a3c908855548')
 files={}
 def add(path):
  assert path.is_file() and path.resolve()==path and not path.is_symlink()
  assert path.name not in ['.env','identity.json','age-identity.txt','id_ed25519']
  assert path.suffix not in ['.log','.sql','.age']
  relative=path.relative_to(Path('/root/gpm-ts-update'))
  assert not any(p in relative.parts for p in ['vendor','node_modules'])
  files[str(relative)]=path
 for name,expected in manifest.items():
  path=W/'candidate'/name;assert hashlib.sha256(path.read_bytes()).hexdigest()==expected;add(path)
 for root in [W/'source-main',W/'source-ts',W/'merge-base',W/'conflicts',W/'document-template-overlays-20261109',
              W/'runtime-rehearsal-before-20261109',W/'order-permissions-before-20261109',W/'document-corrections-before-20261109']:
  if root.is_dir():
   for path in root.rglob('*'):
    if path.is_file():add(path)
 for name in ['original-data-checks.json','rehearse_migrations.php','preparation.json','review.json','candidate-review.json',
  'candidate-checks.json','rehearsal-adaptations.json','candidate-manifest-order-forms-20261109.json',
  'candidate-manifest-email-code-20261109.json','candidate-manifest-documents-20261109.json','document-candidate-corrections-20261109.json']:
  path=W/name
  if path.is_file():add(path)
 for slot in ['runtime','next','accepted-new-first-run']:
  for relative in ['app/Services/Release/GpmTsSwitchContext.php','app/Services/Release/GpmTsRehearsal.php',
   'app/Services/Release/GpmTsRuntimeContext.php','app/Console/Commands/PlanningDayBoundary.php']:
   path=S/slot/relative
   if path.is_file():add(path)
 for path in Path('/root/gpm-ts-update/switch-tools-20261109').iterdir():
  if path.is_file() and path.suffix in ['.py','.php']:add(path)
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
  for name,path in sorted(files.items()):archive.add(str(path),arcname=name,recursive=False)
if __name__=='__main__':main()
