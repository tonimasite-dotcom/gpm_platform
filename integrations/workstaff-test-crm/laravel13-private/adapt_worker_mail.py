"""Stop the new worker mail sender before locks, state writes or SMTP; private only."""
import argparse,hashlib,json,os,re
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE=BASE/'rootfs/work/crm-private-01'
NAME='app/Services/Order/OrderWorkerMailService.php'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    if CANDIDATE.resolve()!=CANDIDATE or not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('MARKED_SYNTHETIC_CANDIDATE_REQUIRED')
    expected=json.loads((BASE/'crm-code-manifest.json').read_text())[NAME]['sha256']
    path=CANDIDATE/NAME;before=path.read_bytes()
    if hashlib.sha256(before).hexdigest()!=expected:raise RuntimeError('EXACT_UNADAPTED_WORKER_MAIL_REQUIRED')
    matches=list(re.finditer(rb'private function withLock\(int \$id, \?array \$manual\): array\s*\{',before))
    if len(matches)!=1:raise RuntimeError('WORKER_MAIL_ENTRY_ANCHOR_NOT_UNIQUE')
    pos=matches[0].end()
    after=before[:pos]+b"\n        // TS demo: stop before locks, state changes or attachments.\n        \\App\\Services\\Release\\GpmTsDemoPolicy::deny('mail');\n"+before[pos:]
    result={'private_only':True,'live_apply_supported':False,'file':NAME,'before_sha256':expected,
            'after_sha256':hashlib.sha256(after).hexdigest(),'applied':False}
    if args.apply:
        folder=BASE/'worker-mail-adaptation-20261116-01';folder.mkdir(mode=0o700)
        (folder/'service-before.php').write_bytes(before);path.write_bytes(after)
        result['applied']=True;(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
