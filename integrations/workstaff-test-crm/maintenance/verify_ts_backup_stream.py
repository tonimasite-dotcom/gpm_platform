"""Verify the fresh encrypted TS backup in memory; no CRM archive is saved on the PC.

The private age key stays local. This verifies SQL/file integrity, not SQL restore.
"""
import gzip
import hashlib
import json
import re
import subprocess
import tarfile
import threading
from pathlib import Path,PurePosixPath

BACKUP='/root/gpm-ts-update/20261106-baseline-01/backup-preparation-20261116-gpm'
AGE=Path('.tmp/full-project-snapshot-20261015/tools/age.exe')
KEY=Path('.tmp/production-backup-20261015/age-identity.txt')
SSH=['ssh','-i','C:/Users/Юра/.ssh/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
     '-o','UserKnownHostsFile=.tmp/test-crm-known-hosts','root@5.183.191.222']

class Decrypted:
    def __init__(self,name,expected):
        if name not in ['ts-manifest.json.age','ts-mysql.sql.gz.age','ts-files.tar.gz.age']:
            raise RuntimeError('EXACT_BACKUP_ARTIFACT_REQUIRED')
        self.name=name;self.expected=expected;self.hash=hashlib.sha256();self.bytes=0;self.error=None
        self.source=subprocess.Popen(SSH+['cat '+BACKUP+'/'+name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.decrypt=subprocess.Popen([str(AGE),'--decrypt','--identity',str(KEY)],stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.thread=threading.Thread(target=self.pump);self.thread.start()
    def pump(self):
        try:
            for block in iter(lambda:self.source.stdout.read(1024*1024),b''):
                self.hash.update(block);self.bytes+=len(block);self.decrypt.stdin.write(block)
        except Exception as error:self.error=type(error).__name__
        finally:
            try:self.decrypt.stdin.close()
            except OSError:pass
    def finish(self):
        for block in iter(lambda:self.decrypt.stdout.read(1024*1024),b''):pass
        self.thread.join()
        self.source.stderr.read();self.decrypt.stderr.read()
        if self.source.wait() or self.decrypt.wait() or self.error:
            raise RuntimeError('ENCRYPTED_STREAM_OR_KEY_CHECK_FAILED:'+self.name)
        if self.bytes!=self.expected['bytes'] or self.hash.hexdigest()!=self.expected['sha256']:
            raise RuntimeError('ENCRYPTED_STREAM_HASH_MISMATCH:'+self.name)
    def abort(self):
        for process in [self.source,self.decrypt]:
            if process.poll() is None:process.terminate()

def verify():
    public_result=subprocess.run(SSH+['cat '+BACKUP+'/verification.json'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if public_result.returncode:raise RuntimeError('BACKUP_PUBLIC_REPORT_READ_FAILED')
    public=json.loads(public_result.stdout)
    manifest_stream=Decrypted('ts-manifest.json.age',public['artifacts']['ts-manifest.json.age'])
    try:
        content=manifest_stream.decrypt.stdout.read(64*1024*1024+1)
        if len(content)>64*1024*1024:raise RuntimeError('MANIFEST_TOO_LARGE')
        manifest=json.loads(content);manifest_stream.finish()
    except Exception:manifest_stream.abort();raise
    print(json.dumps({'stage':'manifest_verified','file_entries':len(manifest['files']),
                      'table_count':manifest['database']['table_count'],'key_uploaded':False}),flush=True)
    sql=Decrypted('ts-mysql.sql.gz.age',public['artifacts']['ts-mysql.sql.gz.age'])
    digest=hashlib.sha256();counts={};creates=0;drop_count=0
    try:
        with gzip.GzipFile(fileobj=sql.decrypt.stdout,mode='rb') as stream:
            for line in stream:
                digest.update(line)
                match=re.match(rb'^CREATE TABLE `([^`]+)`',line)
                if match:counts.setdefault(match[1].decode(),0);creates+=1
                match=re.match(rb'^INSERT INTO `([^`]+)`(?:\s|\()',line)
                if match:
                    name=match[1].decode();counts[name]=counts.get(name,0)+1
                if line.startswith(b'DROP TABLE IF EXISTS '):drop_count+=1
                if line.startswith((b'USE ',b'CREATE DATABASE ',b'GRANT ',b'DROP DATABASE ')):
                    raise RuntimeError('DATABASE_WIDE_STATEMENT_IN_BACKUP')
        sql.finish()
    except Exception:sql.abort();raise
    if digest.hexdigest()!=manifest['database']['sql_sha256'] or counts!=manifest['database']['row_counts']:
        raise RuntimeError('DECRYPTED_SQL_MANIFEST_MISMATCH')
    print(json.dumps({'stage':'sql_integrity_verified','tables':creates,'restore_executed':False}),flush=True)
    files=Decrypted('ts-files.tar.gz.age',public['artifacts']['ts-files.tar.gz.age'])
    seen=set();regular=0;links=0;total_bytes=0
    try:
        with tarfile.open(fileobj=files.decrypt.stdout,mode='r|gz') as archive:
            for member in archive:
                name=member.name;relative=PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts or name in seen or name not in manifest['files']:
                    raise RuntimeError('UNEXPECTED_BACKUP_MEMBER')
                expected=manifest['files'][name];seen.add(name)
                if member.issym():
                    if expected.get('kind')!='symlink' or member.linkname!=expected['target']:
                        raise RuntimeError('SYMLINK_METADATA_MISMATCH')
                    links+=1
                elif member.isfile():
                    if expected.get('kind')!='file' or member.size!=expected['bytes']:
                        raise RuntimeError('FILE_METADATA_MISMATCH')
                    content=archive.extractfile(member);value=hashlib.sha256()
                    for block in iter(lambda:content.read(1024*1024),b''):value.update(block)
                    if value.hexdigest()!=expected['sha256']:raise RuntimeError('BACKUP_FILE_HASH_MISMATCH')
                    regular+=1;total_bytes+=member.size
                else:raise RuntimeError('UNSUPPORTED_BACKUP_MEMBER_TYPE')
                if len(seen)%5000==0:print(json.dumps({'stage':'file_integrity_progress','entries':len(seen)}),flush=True)
        files.finish()
    except Exception:files.abort();raise
    if seen!=set(manifest['files']):raise RuntimeError('BACKUP_FILE_INVENTORY_MISMATCH')
    result={'status':'PASS','ciphertext_artifacts_verified':3,'private_key_uploaded':False,
        'sql_integrity_verified':True,'sql_restore_executed':False,'sql_tables':creates,
        'drop_table_statements_identified_for_empty_restore_filter':drop_count,
        'all_file_hashes_verified':True,'file_entries':len(seen),'regular_files':regular,'symlinks':links,
        'regular_file_bytes':total_bytes,'plaintext_files_extracted':False,'archive_saved_on_pc':False,
        'unstable_online_file_count':len(manifest['unstable_online_files']),
        'backup_kind':public['kind'],'release_quiesced_checkpoint':False}
    Path('.tmp/ts-backup-stream-verification-20261116.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':verify()
