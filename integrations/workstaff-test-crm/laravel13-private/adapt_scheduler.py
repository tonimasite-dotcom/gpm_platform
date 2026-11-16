"""Disable all general scheduled jobs only in the marked synthetic TS candidate.

The existing independent GPM cron is outside this file and is never modified.
"""
import argparse,hashlib,json,os
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE=BASE/'rootfs/work/crm-private-01'
EXPECTED='5521e327db0edc28bbef6efd0207886dd1d968401f1e02b9738907819fa4521f'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    if CANDIDATE.resolve()!=CANDIDATE or not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('MARKED_SYNTHETIC_CANDIDATE_REQUIRED')
    path=CANDIDATE/'app/Console/Kernel.php';old=path.read_bytes()
    if hashlib.sha256(old).hexdigest()!=EXPECTED:
        raise RuntimeError('EXACT_UNADAPTED_SCHEDULER_REQUIRED')
    anchor=b'    protected function schedule(Schedule $schedule)\n    {'
    if old.count(anchor)!=1:raise RuntimeError('EXACT_SCHEDULE_ANCHOR_REQUIRED')
    new=old.replace(anchor,anchor+b"\n        // TS: do not register general background/debtor/mail jobs. GPM has its separate cron.\n        \\App\\Services\\Release\\GpmTsDemoPolicy::assertContext();\n        return;\n",1)
    result={'private_synthetic_only':True,'live_apply_supported':False,'file':'app/Console/Kernel.php',
        'before_sha256':EXPECTED,'after_sha256':hashlib.sha256(new).hexdigest(),'applied':False,
        'cron_files_modified':False,'gpm_sync_command_modified':False}
    if args.apply:
        folder=BASE/'scheduler-adaptation-20261116-01';folder.mkdir(mode=0o700)
        (folder/'Kernel-before.php').write_bytes(old)
        path.write_bytes(new)
        result['applied']=True
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
