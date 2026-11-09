#!/usr/bin/env python3
"""Remove exactly the three explicitly approved, locally preserved duplicates."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,stat
ROOT=Path('/root/gpm-ts-update/20261106-baseline-01/backup-preparation-20261109')
PLAN=Path('/root/gpm-ts-update/disk-cleanup-approved-archive-plan-20261109.json')
PROOF=Path('/root/gpm-ts-update/disk-cleanup-approved-local-proof-20261109.json')
OUTPUT=Path('/root/gpm-ts-update/disk-cleanup-approved-archive-removal-20261109.json')
EXPECTED={
 'ts-files.tar.gz.age':{'bytes':1785435811,'sha256':'61c8d7ecdeb95016ee46bff482dbd893d4e4a73552fa7c8ea28d8528ae71a25a'},
 'ts-mysql.sql.gz.age':{'bytes':55778125,'sha256':'fa2149e8b84bc8a7eadfffbe19942b0e9335ad3a3105cf9606f12a25bdf5ecd4'},
 'ts-manifest.json.age':{'bytes':4697281,'sha256':'aad15269ff34bfb2d2dbcf1d5c28bd58137fc1713c1e3739cdc244a00b6eedb6'}}
def require(value,message):
 if not value:raise RuntimeError(message)
def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
def main():
 os.umask(0o077)
 require(ROOT.resolve()==ROOT and ROOT.is_dir() and not OUTPUT.exists(),'EXACT_APPROVED_ROOT_AND_NEW_REPORT_REQUIRED')
 plan=json.loads(PLAN.read_text());proof=json.loads(PROOF.read_text())
 require(plan['server_directory']==str(ROOT) and plan['files']==EXPECTED and proof['files']==EXPECTED
  and proof['local_files_revalidated'] is True,'EXACT_PLAN_AND_FRESH_LOCAL_PROOF_REQUIRED')
 require(sum(x['bytes'] for x in EXPECTED.values())==1845911217,'APPROVED_SIZE_REQUIRED')
 retained={p.name:identity(p.lstat()) for p in ROOT.iterdir() if p.name not in EXPECTED}
 opened={};removed=[];before=shutil.disk_usage('/').free
 try:
  for name,expected in EXPECTED.items():
   path=ROOT/name;require(path.resolve()==path and not path.is_symlink(),'REGULAR_ARCHIVE_PATH_REQUIRED')
   fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW);opened[name]=fd;s=os.fstat(fd)
   require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==expected['bytes'],'EXACT_REGULAR_ARCHIVE_REQUIRED')
   h=hashlib.sha256()
   while True:
    block=os.read(fd,4*1024*1024)
    if not block:break
    h.update(block)
   require(h.hexdigest()==expected['sha256'] and identity(os.fstat(fd))==identity(s),'SERVER_ARCHIVE_HASH_OR_STATE_CHANGED')
  identities={(os.fstat(fd).st_dev,os.fstat(fd).st_ino) for fd in opened.values()}
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
   try:fds=list((proc/'fd').iterdir())
   except OSError:continue
   for fd in fds:
    try:s=fd.stat()
    except OSError:continue
    require((s.st_dev,s.st_ino) not in identities,'ARCHIVE_IN_USE_BY_ANOTHER_PROCESS')
  with OUTPUT.open('x') as out:out.write(json.dumps({'status':'verified_before_unlink','approved_files':EXPECTED},indent=2)+'\n')
  for name in EXPECTED:
   path=ROOT/name
   require(path.resolve()==path and identity(path.lstat())==identity(os.fstat(opened[name])),'ARCHIVE_PATH_CHANGED_BEFORE_UNLINK')
   os.unlink(str(path));removed.append(name)
   OUTPUT.write_text(json.dumps({'status':'removal_in_progress','removed':removed,'approved_files':EXPECTED},indent=2)+'\n')
 finally:
  for fd in opened.values():os.close(fd)
 require(all(not (ROOT/name).exists() for name in EXPECTED),'ARCHIVE_REMOVAL_VERIFICATION_FAILED')
 require({p.name:identity(p.lstat()) for p in ROOT.iterdir()}==retained,'UNAPPROVED_DIRECTORY_ENTRY_CHANGED')
 report={'success':True,'user_explicitly_approved_only_three_server_duplicates':True,
  'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'removed_server_directory':str(ROOT),'removed_files':EXPECTED,'archive_bytes_removed':1845911217,
  'local_files_revalidated_before_removal':True,'server_sha256_revalidated_before_removal':True,
  'open_file_check_passed':True,'other_entries_in_directory_preserved':True,'retained_entries':sorted(retained),
  'local_archives_or_key_modified':False,'live_crm_accessed':False,'database_or_runtime_tree_removed':False,
  'free_bytes_before':before,'free_bytes_after':shutil.disk_usage('/').free}
 OUTPUT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
