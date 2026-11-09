#!/usr/bin/env python3
"""Private document acceptance. Keep all outputs, including failed attempts."""
from pathlib import Path
import json,os,secrets,subprocess,shutil
W=Path('/root/gpm-ts-update/20261106-baseline-01')
def main():
 os.umask(0o077)
 assert W.resolve()==W and shutil.disk_usage(str(W)).free>512*1024**2
 fixture=W/('extended-document-fixtures-'+secrets.token_hex(6));fixture.mkdir(mode=0o700)
 for name in ['public','config','cache','tmp']:(fixture/name).mkdir(mode=0o700)
 env={k:v for k,v in os.environ.items() if not k.startswith(('DB_','APP_','GPM_','CRM_'))}
 env.update({'GPM_TS_REHEARSAL':'1','GPM_TS_DOCUMENT_FIXTURE':str(fixture),'XDG_CONFIG_HOME':str(fixture/'config'),
  'XDG_CACHE_HOME':str(fixture/'cache'),'TMPDIR':str(fixture/'tmp')})
 r=subprocess.run(['unshare','--net','nice','-n','10','php','-d','memory_limit=512M',
  str(W/'acceptance-20261109/payload/extended_document_acceptance.php')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
  universal_newlines=True,timeout=600)
 (fixture/'stdout-private.log').write_text(r.stdout);(fixture/'stderr-private.log').write_text(r.stderr)
 result=json.loads(r.stdout)
 with (fixture/'safe-result.json').open('x') as out:out.write(json.dumps(result,indent=2))
 print(json.dumps({'fixture':fixture.name,'result':result}));raise SystemExit(r.returncode)
if __name__=='__main__':main()
