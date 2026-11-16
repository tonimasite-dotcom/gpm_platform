"""Read-only estimate of lossless content deduplication for five stopped TS rehearsals.

No archive is written and no file is removed. Primary CRM/storage are excluded.
UID/GID, mode, mtime/atime, xattrs and symlink targets are included in the estimate.
"""
import base64
import collections
import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
import time
from pathlib import Path

ROOT=Path('/root/gpm-ts-update/20261109-switch-01')
NAMES=['accepted-new-first-run','next','runtime','mysql-new-failed-after-timeout','mysql-new-timeout-evidence']

class Counter:
    def __init__(self):self.bytes=0
    def write(self,data):self.bytes+=len(data);return len(data)
    def flush(self):pass

def metadata(path,info):
    attrs={}
    for name in os.listxattr(str(path),follow_symlinks=False):
        attrs[name]=base64.b64encode(os.getxattr(str(path),name,follow_symlinks=False)).decode()
    return {'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,
            'mtime_ns':info.st_mtime_ns,'atime_ns':info.st_atime_ns,'xattrs':attrs}

def build_archive(counter):
    if ROOT.resolve()!=ROOT:raise RuntimeError('EXACT_PRIVATE_REHEARSAL_PARENT_REQUIRED')
    inventory=[];objects={};inodes=set();logical=0;allocated=0;hardlinked=0
    started=time.monotonic();regular=0
    with gzip.GzipFile(fileobj=counter,mode='wb',compresslevel=1,mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w|') as archive:
            for alias in NAMES:
                root=ROOT/alias
                if root.resolve()!=root or not root.is_dir():raise RuntimeError('EXACT_STOPPED_DIRECTORY_REQUIRED')
                inventory.append(dict(path=alias,kind='directory',**metadata(root,root.lstat())))
                for directory,dirs,files in os.walk(str(root),followlinks=False):
                    dirs.sort();files.sort();parent=Path(directory)
                    for name in list(dirs):
                        path=parent/name;info=path.lstat();relative=alias+'/'+path.relative_to(root).as_posix()
                        if path.is_symlink():
                            inventory.append(dict(path=relative,kind='symlink',target=os.readlink(str(path)),**metadata(path,info)));dirs.remove(name)
                        else:inventory.append(dict(path=relative,kind='directory',**metadata(path,info)))
                    for name in files:
                        path=parent/name;before=path.lstat();relative=alias+'/'+path.relative_to(root).as_posix()
                        if stat.S_ISLNK(before.st_mode):
                            inventory.append(dict(path=relative,kind='symlink',target=os.readlink(str(path)),**metadata(path,before)));continue
                        if not stat.S_ISREG(before.st_mode):raise RuntimeError('UNEXPECTED_SPECIAL_FILE_IN_COLD_REHEARSAL')
                        digest=hashlib.sha256()
                        with path.open('rb') as stream:
                            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
                        sha=digest.hexdigest();regular+=1;logical+=before.st_size
                        key=(before.st_dev,before.st_ino)
                        if key not in inodes:allocated+=before.st_blocks*512;inodes.add(key)
                        if before.st_nlink!=1:hardlinked+=1
                        inventory.append(dict(path=relative,kind='file',bytes=before.st_size,sha256=sha,
                                              source_nlink=before.st_nlink,**metadata(path,before)))
                        if sha not in objects:
                            record=tarfile.TarInfo('objects/'+sha);record.mode=0o600;record.size=before.st_size
                            with path.open('rb') as stream:archive.addfile(record,stream)
                            objects[sha]=before.st_size
                        after=path.lstat()
                        if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                            raise RuntimeError('COLD_SOURCE_CHANGED_DURING_ESTIMATE')
                        if regular%10000==0:
                            print(json.dumps({'stage':'read_only_dedup_estimate','files':regular,'unique_objects':len(objects),
                                'gzip_bytes_so_far':counter.bytes}),flush=True)
            body=json.dumps({'format':'gpm-cold-rehearsal-cas-v2','roots':{name:str(ROOT/name) for name in NAMES},
                             'files':inventory,'objects':objects},ensure_ascii=True).encode()
            record=tarfile.TarInfo('MANIFEST.json');record.mode=0o600;record.size=len(body)
            archive.addfile(record,io.BytesIO(body))
    cipher_bound=counter.bytes+((counter.bytes+65535)//65536)*16+2048
    result={'status':'PASS','targets':NAMES,'regular_files':regular,'entries':len(inventory),
        'source_logical_bytes':logical,'source_allocated_regular_bytes':allocated,'unique_objects':len(objects),
        'unique_content_bytes':sum(objects.values()),'gzip_bytes':counter.bytes,'encrypted_bytes_upper_bound':cipher_bound,
        'expected_net_reclaim_bytes':allocated-cipher_bound,'hardlinked_source_files':hardlinked,
        'xattr_entries':sum(bool(row['xattrs']) for row in inventory),'uid_gid_pairs':len({(row['uid'],row['gid']) for row in inventory}),
        'archive_written':False,'files_removed':False,'elapsed_seconds':round(time.monotonic()-started,1),
        'manifest_sha256':hashlib.sha256(body).hexdigest()}
    return result

def main():
    os.nice(15)
    print(json.dumps(build_archive(Counter())),flush=True)

if __name__=='__main__':main()
