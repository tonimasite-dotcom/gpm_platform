#!/usr/bin/env python3
"""Remove only reproducible Babel/Terser caches in the private candidate."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,stat,subprocess
W=Path('/root/gpm-ts-update/20261106-baseline-01');ROOT=W/'candidate'
ALLOWED=[ROOT/'node_modules/.cache/terser-webpack-plugin',ROOT/'node_modules/.cache/babel-loader']
OUTPUT=Path('/root/gpm-ts-update/disk-cleanup-20261109-cache.json')
def require(value,message):
 if not value:raise RuntimeError(message)
def code_check():
 manifest=json.loads((W/'candidate-manifest-documents-20261109.json').read_text())
 require(hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()==
  'f47de6309adb543870d844b043529124720fe1501d32fb447a74a3c908855548','KNOWN_CODE_MANIFEST_REQUIRED')
 for name,expected in manifest.items():
  p=ROOT/name
  require(p.resolve()==p and hashlib.sha256(p.read_bytes()).hexdigest()==expected,'CANDIDATE_CODE_CHANGED')
 return len(manifest)
def no_active_users():
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:args=(p/'cmdline').read_bytes();cwd=(p/'cwd').resolve()
  except OSError:continue
  require(os.fsencode(str(ROOT)) not in args and ROOT!=cwd and ROOT not in cwd.parents,'CANDIDATE_PROCESS_ACTIVE')
  try:fds=list((p/'fd').iterdir())
  except OSError:continue
  for fd in fds:
   try:target=os.readlink(str(fd))
   except OSError:continue
   require(not any(target==str(path) or target.startswith(str(path)+'/') for path in ALLOWED),'CACHE_FILE_OPEN')
def inspect():
 require(ROOT.resolve()==ROOT and not OUTPUT.exists(),'PRIVATE_ROOT_AND_NEW_REPORT_REQUIRED')
 rows=[]
 for directory in ALLOWED:
  require(directory.resolve()==directory and directory.is_dir(),'EXACT_REGULAR_CACHE_DIRECTORY_REQUIRED')
  device=directory.stat().st_dev;files=0;bytes_total=0;allocated=0
  for base,dirs,names in os.walk(str(directory),followlinks=False):
   for name in dirs+names:
    p=Path(base)/name;s=p.lstat()
    require(not p.is_symlink() and s.st_dev==device and p.resolve()==p,'CACHE_LINK_OR_MOUNT_REFUSED')
    require(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink==1),'CACHE_SPECIAL_OBJECT_REFUSED')
    if stat.S_ISREG(s.st_mode):files+=1;bytes_total+=s.st_size;allocated+=s.st_blocks*512
  rows.append({'path':str(directory),'files':files,'bytes':bytes_total,'allocated_file_bytes':allocated})
 return rows
def main():
 os.umask(0o077);parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');options=parser.parse_args()
 count=code_check();no_active_users();rows=inspect()
 report={'apply':options.apply,'directories':rows,'candidate_code_files_verified':count,'live_crm_accessed':False,
  'backups_or_databases_removed':False,'rebuild_dependency_downloads_required':False}
 if options.apply:
  before=shutil.disk_usage('/').free
  # Paths are fixed above, fully validated, and checked again immediately before removal.
  for row,directory in zip(rows,ALLOWED):
   require(directory.resolve()==directory and str(directory)==row['path'],'CACHE_PATH_CHANGED')
   shutil.rmtree(str(directory))
  report.update({'candidate_code_files_verified_after':code_check(),'all_cache_targets_removed':all(not p.exists() for p in ALLOWED),
   'free_bytes_before':before,'free_bytes_after':shutil.disk_usage('/').free})
  with OUTPUT.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
if __name__=='__main__':main()
