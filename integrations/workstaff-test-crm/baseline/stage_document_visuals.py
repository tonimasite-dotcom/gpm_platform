#!/usr/bin/env python3
from pathlib import Path
import json,re,sys,os,hashlib
W=Path('/root/gpm-ts-update/20261106-baseline-01')
def main():
 os.umask(0o077);name=sys.argv[1]
 assert re.fullmatch(r'extended-document-fixtures-[a-f0-9]{12}',name)
 fixture=W/name;assert fixture.resolve()==fixture
 report=json.loads((fixture/'safe-result.json').read_text());assert report['success']
 items=json.loads((fixture/'artifact-index-private.json').read_text());folder=fixture/'safe-visual-input';folder.mkdir()
 index=[]
 for item in items:
  if item['kind'].startswith('pdf'):
   source=Path(item['path']);assert source.resolve()==source and fixture in source.parents
   assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']
   dest='document-'+str(len(index)).zfill(2)+'.pdf';(folder/dest).write_bytes(source.read_bytes())
   index.append({'file':dest,'case':item['case'],'part':item['part'],'kind':item['kind']})
 (folder/'index.json').write_text(json.dumps(index,indent=2));print(json.dumps({'pdfs_staged':len(index)}))
if __name__=='__main__':main()
