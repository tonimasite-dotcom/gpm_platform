"""Create an encrypted, metadata-preserving archive of five closed TS rehearsals.

Original directories are retained. No cleanup or database startup is supported.
"""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
from assess_cold_rehearsals import ROOT,NAMES,build_archive

DEST=Path('/root/gpm-ts-update/cold-rehearsals-20261116-01')
ARCHIVE='TS_REHEARSALS_20261109.cas-v2.tar.gz.age'
SEAL=Path('/root/gpm-snapshots/20261015-before-sync')
RESERVE=3*1024**3+128*1024**2

def references():
    targets=[str(ROOT/name) for name in NAMES];found=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
        try:
            command=(proc/'cmdline').read_bytes()
            for target in targets:
                if target.encode() in command:found.append(int(proc.name))
            for node in ['cwd','root']:
                try:resolved=os.readlink(str(proc/node))
                except OSError:continue
                if any(resolved==target or resolved.startswith(target+'/') for target in targets):found.append(int(proc.name))
            for descriptor in (proc/'fd').iterdir():
                try:resolved=os.readlink(str(descriptor))
                except OSError:continue
                if any(resolved==target or resolved.startswith(target+'/') for target in targets):found.append(int(proc.name))
        except FileNotFoundError:pass
    return sorted(set(found))

class Forward:
    def __init__(self,stream):self.stream=stream;self.bytes=0;self.next_check=0
    def write(self,data):
        if self.bytes>=self.next_check:
            if shutil.disk_usage(str(DEST)).free<RESERVE:raise RuntimeError('THREE_GIB_RESERVE_REQUIRED')
            self.next_check=self.bytes+8*1024**2
        count=self.stream.write(data)
        if count!=len(data):raise RuntimeError('ARCHIVE_PIPE_SHORT_WRITE')
        self.bytes+=count;return count
    def flush(self):self.stream.flush()

def main():
    os.umask(0o077);os.nice(15)
    if ROOT.resolve()!=ROOT or DEST.resolve()!=DEST or DEST.exists():raise RuntimeError('NEW_EXACT_COLD_ARCHIVE_DIRECTORY_REQUIRED')
    if shutil.disk_usage(str(ROOT)).free<RESERVE+2200*1024**2:raise RuntimeError('ARCHIVE_AND_RESERVE_SPACE_REQUIRED')
    if references():raise RuntimeError('OLD_REHEARSAL_IN_USE')
    DEST.mkdir(mode=0o700);output=DEST/ARCHIVE
    recipient=(SEAL/'age-recipient.txt').read_text().strip()
    process=subprocess.Popen([str(SEAL/'age'),'--encrypt','--recipient',recipient,'--output',str(output)],
                             stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        result=build_archive(Forward(process.stdin))
        if result['hardlinked_source_files']!=0:raise RuntimeError('SOURCE_HARDLINK_RESTORE_REVIEW_REQUIRED')
        process.stdin.close();process.stderr.read()
        if process.wait():raise RuntimeError('COLD_ARCHIVE_ENCRYPTION_FAILED')
        if references():raise RuntimeError('OLD_REHEARSAL_USE_CHANGED_DURING_PACK')
        digest=hashlib.sha256()
        with output.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        result.update(archive_written=True,artifact=ARCHIVE,encrypted=True,bytes=output.stat().st_size,
            sha256=digest.hexdigest(),decryption_verified=False,original_directories_retained=True,
            github_upload_planned=False,free_bytes_after=shutil.disk_usage(str(DEST)).free)
        (DEST/'pack-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    except Exception:
        if process.poll() is None:process.terminate();process.wait()
        # Only this newly created incomplete artifact; all five originals remain.
        if output.exists() and output.is_file() and not output.is_symlink():output.unlink()
        raise

if __name__=='__main__':main()
