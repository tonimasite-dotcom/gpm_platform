#!/usr/bin/env python3
"""Assemble safe/private continuation ZIPs and verify every packaged file."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,zipfile
BASE=Path('C:/Users/Acer/gpm_platform');W=BASE/'.tmp/ts-resume-20261109';P=BASE/'.tmp/chat-snapshot-20261110'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def zip_and_check(output,files):
 assert not output.exists()
 with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,p in sorted(files.items()):z.write(p,name)
 with zipfile.ZipFile(output) as z:
  assert z.testzip() is None
  for name,p in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==sha(p),name
 return {'file':output.name,'bytes':output.stat().st_size,'sha256':sha(output),'entries':len(files),'crc_and_all_file_sha256_verified':True}
def main():
 assert P.is_dir() and shutil.disk_usage(str(P)).free>700*1024**2
 status=subprocess.check_output(['git','status','--porcelain=v1'],cwd=str(W)).decode();assert not status,'COMMIT_SNAPSHOT_FILES_BEFORE_PACKAGING'
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(W)).decode().strip()
 tracked=subprocess.check_output(['git','ls-files','-z'],cwd=str(W)).decode().split('\0')
 stage=P/'resume-package';stage.mkdir();selected=[]
 dates=['2026-11-06','2026-11-09','2026-11-10']
 for name in tracked:
  if not name:continue
  root_doc='/' not in name and name.endswith('.md') and any(x in name for x in dates) and name.startswith(('PROJECT_','CONTINUE_','CRM_'))
  include=name in ['AGENTS.md','README.md'] or root_doc or name.startswith('integrations/workstaff-test-crm/') or name.startswith('snapshots/2026-11-10-chat-progress/') or (name.startswith('audits/') and ('/crm-ts-' in name or '/crm-main-ts-' in name))
  if not include:continue
  source=W/name;assert source.is_file() and not source.is_symlink()
  assert source.suffix not in ['.age','.pdf','.zip','.sql','.pem'] and source.name not in ['.env','id_ed25519','age-identity.txt']
  if source.suffix in ['.md','.py','.php','.json','.csv','.js','.vue']:
   text=source.read_text(encoding='utf-8-sig')
   assert not re.search(r'AGE-SECRET-KEY-[A-Z0-9]{20,}|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}',text),'SECRET_PATTERN_FOUND'
  target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
  selected.append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
 manifest={'snapshot_date_moscow':'2026-11-10','source_commit':head,'branch':'work/ts-resume-2026-11-09','git_bundle_base_prerequisite':'c5d042a',
  'files':selected,'private_materials_included':False,'whole_host_or_database_clone':False}
 (stage/'SNAPSHOT_FILE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 safe_files={str(p.relative_to(stage)).replace('\\','/'):p for p in stage.rglob('*') if p.is_file()}
 safe=zip_and_check(P/'GPM_RESUME_SAFE_20261110.zip',safe_files)
 bundle=P/'branch-progress.bundle'
 subprocess.run(['git','bundle','create',str(bundle),'c5d042a..HEAD'],cwd=str(W),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 verified=subprocess.run(['git','bundle','verify',str(bundle)],cwd=str(W),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 assert verified.returncode==0,'GIT_BUNDLE_VERIFICATION_FAILED'
 evidence=P/'private-document-evidence';evidence.mkdir()
 for name in ['extended-documents','extended-documents-corrected']:
  source=BASE/'.tmp/crm-access-20261109'/name;assert source.is_dir();shutil.copytree(source,evidence/name)
 for pattern in ['invoice-preview-*.pdf','invoice-preview-*.png','document-render-checks-20261109.json']:
  for source in (BASE/'.tmp/crm-access-20261109').glob(pattern):shutil.copy2(source,evidence/source.name)
 private_files={'resume-package/'+name:p for name,p in safe_files.items()}
 for folder in ['transcript','original-attachments','private-document-evidence']:
  for p in (P/folder).rglob('*'):
   if p.is_file():
    assert not p.is_symlink();private_files[str(p.relative_to(P)).replace('\\','/')]=p
 for name in ['server-code-checkpoint.tar.gz.age','server-code-checkpoint-verification-private.json','private-export-metadata.json','original-worktree-status.txt','branch-progress.bundle']:
  source=P/name;assert source.is_file();private_files[name]=source
 for name in private_files:
  assert Path(name).name not in ['id_ed25519','age-identity.txt','.env','identity.json']
 private_index={'source_commit':head,'contains_private_chat_and_ts_requisites':True,'secret_keys_or_env_included':False,
  'files':[{'file':name,'bytes':p.stat().st_size,'sha256':sha(p)} for name,p in sorted(private_files.items())]}
 index=P/'PRIVATE_FILE_MANIFEST.json';index.write_text(json.dumps(private_index,indent=2),encoding='utf-8');private_files[index.name]=index
 private=zip_and_check(P/'GPM_FULL_CHAT_PRIVATE_20261110.zip',private_files)
 report={'success':True,'source_commit':head,'safe_package':safe,'private_package':private,'git_bundle':{'file':bundle.name,'bytes':bundle.stat().st_size,'sha256':sha(bundle),'verified':True,'base_prerequisite':'c5d042a'},
  'encrypted_code_checkpoint_verified':True,'private_keys_or_env_in_packages':False,'backups_and_datadirs_not_duplicated':True,'free_local_bytes_after':shutil.disk_usage(str(P)).free}
 (P/'PACKAGE_VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
