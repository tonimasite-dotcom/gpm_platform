#!/usr/bin/env python3
"""Export this chat's visible messages, attachments and encrypted private code."""
from pathlib import Path
import argparse,base64,collections,datetime,hashlib,json,os,re,shutil,subprocess,tarfile
PROJECT=Path('C:/Users/Acer/gpm_platform')
PRIVATE=PROJECT/'.tmp/chat-snapshot-20261110'
WORKTREE=PROJECT/'.tmp/ts-resume-20261109'
THREAD='01a1bf64-9861-7f20-b2b6-3f4076dacbe2'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def transcript():
 PRIVATE.mkdir(parents=True,exist_ok=True)
 target=PRIVATE/'transcript';target.mkdir()
 source=list(Path('C:/Users/Acer/.codex/sessions').rglob('*'+THREAD+'.jsonl'));assert len(source)==1
 messages=[];media={};last_timestamp=None;watermark=source[0].stat().st_size
 with source[0].open('rb') as stream:
  consumed=0
  while consumed<watermark:
   line=stream.readline();consumed+=len(line)
   if not line.endswith(b'\n'):break
   row=json.loads(line);payload=row.get('payload',{});last_timestamp=row.get('timestamp',last_timestamp)
   # Export only user-visible dialogue. No system/developer/context/reasoning records.
   if row.get('type')=='event_msg' and payload.get('type') in ['user_message','agent_message']:
    if payload.get('type')=='agent_message' and payload.get('phase') not in ['final_answer','commentary']:continue
    messages.append({'timestamp':row.get('timestamp'),'role':'user' if payload['type']=='user_message' else 'assistant',
     'phase':payload.get('phase'),'text':payload.get('message','')})
   if row.get('type')=='response_item' and payload.get('type')=='message' and payload.get('role')=='user':
    for content in payload.get('content',[]):
     url=content.get('image_url','')
     if content.get('type')!='input_image' or not isinstance(url,str) or not url.startswith('data:image/'):continue
     head,data=url.split(',',1);blob=base64.b64decode(data);digest=hashlib.sha256(blob).hexdigest()
     if digest in media:continue
     suffix='.png' if 'png' in head else '.jpg' if 'jpeg' in head else '.bin'
     folder=target/'images';folder.mkdir(exist_ok=True);name='image-'+str(len(media)+1).zfill(2)+suffix
     (folder/name).write_bytes(blob);media[digest]={'file':'images/'+name,'sha256':digest,'bytes':len(blob),'timestamp':row.get('timestamp')}
 assert len(messages)>100 and len(media)>=4
 with (target/'messages.jsonl').open('x',encoding='utf-8') as out:
  for item in messages:out.write(json.dumps(item,ensure_ascii=False)+'\n')
 lines=['# Переписка текущего чата','',
  'Экспорт доступных пользовательских сообщений и ответов на момент снимка. Инструменты и доказательства сохранены отдельными файлами.',
  'Источник: текущий чат '+THREAD+'. Срез журнала: '+str(last_timestamp)+'.','']
 for i,item in enumerate(messages,1):
  who='Пользователь' if item['role']=='user' else 'Ассистент'
  lines.extend(['## '+str(i)+'. '+who+' — '+str(item['timestamp']),'',item['text'],''])
 lines.extend(['## Изображения пользователя',''])
 for item in media.values():lines.extend(['![Изображение '+item['timestamp']+']('+item['file']+')',''])
 (target/'CHAT_TRANSCRIPT.md').write_text('\n'.join(lines),encoding='utf-8')
 attachments=PRIVATE/'original-attachments';attachments.mkdir()
 pdf=Path('C:/Users/Acer/Desktop/GPM_2026-11-06_Pauza_i_prodolzhenie.pdf')
 assert pdf.is_file();shutil.copy2(pdf,attachments/pdf.name)
 pasted=list(Path('C:/Users/Acer/.codex/attachments/c92e9f46-aa8e-48d1-94db-06e1f6273a0e').glob('*.txt'));assert len(pasted)==1
 shutil.copy2(pasted[0],attachments/'pasted-project-handoff.txt')
 status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=str(PROJECT))
 (PRIVATE/'original-worktree-status.txt').write_bytes(status)
 info={'thread_id':THREAD,'source_journal':str(source[0]),'source_byte_watermark':watermark,'last_record_timestamp':last_timestamp,
  'user_messages':sum(x['role']=='user' for x in messages),'assistant_messages':sum(x['role']=='assistant' for x in messages),
  'images':list(media.values()),'attachments':[{'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in attachments.iterdir()],
  'full_source_journal_copied':False,'visible_dialogue_exported':True,'raw_service_records_included':False,
  'source_journal_stays_in_original_location':True}
 (PRIVATE/'private-export-metadata.json').write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'visible_messages':len(messages),'user_images':len(media),'original_attachments':2,'private_directory':str(PRIVATE)}))
def encrypt_code():
 PRIVATE.mkdir(parents=True,exist_ok=True)
 output=PRIVATE/'server-code-checkpoint.tar.gz.age';assert not output.exists()
 recovery=PROJECT/'.tmp/crm-recovery-20261109';age=recovery/'tools/age/age.exe';identity=recovery/'age-identity.txt'
 assert age.is_file() and identity.is_file()
 keygen=age.parent/'age-keygen.exe';assert keygen.is_file()
 recipient=subprocess.check_output([str(keygen),'-y',str(identity)],stderr=subprocess.PIPE).decode().strip();assert recipient.startswith('age1')
 ssh=subprocess.Popen(['ssh','-i',str(PROJECT/'.tmp/crm-access-20261109/id_ed25519'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
  '-o','StrictHostKeyChecking=yes','root@5.183.191.222','nice','-n','15','python3','/root/gpm-ts-update/export_resume_code_checkpoint-20261110.py'],
  stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 encrypt=subprocess.Popen([str(age),'-r',recipient,'-o',str(output)],stdin=ssh.stdout,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 ssh.stdout.close();_,encerr=encrypt.communicate();ssherr=ssh.stderr.read();sc=ssh.wait()
 if encrypt.returncode or sc:
  (PRIVATE/'checkpoint-export-error-private.log').write_bytes(encerr+b'\n'+ssherr)
  raise RuntimeError('ENCRYPTED_CODE_EXPORT_FAILED_DETAILS_REMAIN_PRIVATE')
 decrypt=subprocess.Popen([str(age),'-d','-i',str(identity),str(output)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 inventory=[];manifest=None
 with tarfile.open(fileobj=decrypt.stdout,mode='r|gz') as archive:
  for entry in archive:
   assert entry.isfile() and not entry.name.startswith('/') and '..' not in Path(entry.name).parts
   stream=archive.extractfile(entry);h=hashlib.sha256();data=[]
   capture=entry.name.endswith('/candidate-manifest-documents-20261109.json')
   while True:
    block=stream.read(1024*1024)
    if not block:break
    h.update(block)
    if capture:data.append(block)
   if capture:manifest=json.loads(b''.join(data))
   inventory.append({'file':entry.name,'bytes':entry.size,'sha256':h.hexdigest()})
 decrypt.stdout.read();errors=decrypt.stderr.read();assert decrypt.wait()==0,'AGE_DECRYPTION_FAILED'
 assert manifest is not None
 lookup={x['file']:x['sha256'] for x in inventory}
 assert all(lookup['20261106-baseline-01/candidate/'+name]==value for name,value in manifest.items())
 assert len(manifest)==1391
 report={'encrypted_checkpoint':output.name,'bytes':output.stat().st_size,'sha256':sha(output),'decryption_and_tar_stream_verified':True,
  'candidate_code_files_verified':len(manifest),'archived_files':len(inventory),'database_datadirs_or_keys_included':False,
  'env_files_included':False,'all_metadata':inventory}
 (PRIVATE/'server-code-checkpoint-verification-private.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='all_metadata'}))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['transcript','encrypt-code']);args=parser.parse_args()
 (transcript if args.operation=='transcript' else encrypt_code)()
