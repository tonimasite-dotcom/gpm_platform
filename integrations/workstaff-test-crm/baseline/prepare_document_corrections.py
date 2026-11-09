#!/usr/bin/env python3
"""Prepare private code and template overlays. No live/template snapshot edits."""
from pathlib import Path
import hashlib,json,zipfile,re,html,os,shutil
from xml.sax.saxutils import escape
W=Path('/root/gpm-ts-update/20261106-baseline-01')
SOURCE=W/'file-recovery-20261109/tree/storage/app/public/document_templates'
OVERLAY=W/'document-template-overlays-20261109'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace_text(xml,pattern,replacement,expected):
 nodes=list(re.finditer(r'(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)',xml,re.S))
 plain=''.join(html.unescape(m.group(2)) for m in nodes);hits=list(re.finditer(pattern,plain))
 assert len(hits)==expected,'EXACT_TEMPLATE_TEXT_ANCHOR_REQUIRED'
 pieces=[html.unescape(m.group(2)) for m in nodes];starts=[];position=0
 for piece in pieces:starts.append(position);position+=len(piece)
 for hit in reversed(hits):
  inserted=False
  for i in range(len(pieces)):
   a=starts[i];b=a+len(html.unescape(nodes[i].group(2)))
   if a<hit.end() and b>hit.start():
    lo=max(0,hit.start()-a);hi=min(b-a,hit.end()-a)
    pieces[i]=pieces[i][:lo]+(replacement if not inserted else '')+pieces[i][hi:];inserted=True
 assert inserted
 for i in range(len(nodes)-1,-1,-1):
  m=nodes[i];xml=xml[:m.start(2)]+escape(pieces[i])+xml[m.end(2):]
 return xml
def write_template(relative,expected,transform):
 source=SOURCE/relative;assert source.resolve()==source and sha(source)==expected
 target=OVERLAY/relative;target.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(str(source)) as original,zipfile.ZipFile(str(target),'x') as output:
  for info in original.infolist():
   payload=original.read(info.filename)
   if info.filename=='word/document.xml':payload=transform(payload.decode()).encode()
   output.writestr(info,payload)
 assert sha(source)==expected
 return {'relative':relative,'source_sha256':expected,'overlay_sha256':sha(target)}
def act_xml(xml):
 xml=replace_text(xml,r'НДС\s+не\s+облагается\.', '${vat_summary}',1)
 match=re.search(r'<w:tbl[ >].*?\$\{total_cost\}.*?</w:tbl>',xml,re.S);assert match
 table=match.group()
 for old,new,expected in [('6841','6103',4),('862','1600',5),('9158','8420',1)]:
  table,count=re.subn(r'(<w:(?:gridCol|tcW)\b[^>]*\bw:w=")'+old+r'(")',lambda m:m.group(1)+new+m.group(2),table)
  assert count==expected,'EXACT_ACT_COLUMN_WIDTH_REQUIRED'
 return xml[:match.start()]+table+xml[match.end():]
def application_xml(xml):
 xml=replace_text(xml,re.escape('033/22'),'${doc_number}',2)
 return replace_text(xml,r'20\s+июня\s+2022\s*г\.', '${date}',2)
def main():
 os.umask(0o077)
 assert W.resolve()==W and not OVERLAY.exists()
 manifest=json.loads((W/'candidate-manifest-email-code-20261109.json').read_text())
 digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert digest=='51cc81a6b5fe049b81296c7cb3c2fc9059e2d5d507b771c94d95bd5ae9a397cf'
 assert all(sha(W/'candidate'/name)==value for name,value in manifest.items())
 relative='app/Services/Document/DocumentData/ActDataService.php';code=W/'candidate'/relative
 before=code.read_text();anchor="                'sum_string'    => $this->sumWords($totalCost),"
 assert before.count(anchor)==1
 after=before.replace(anchor,anchor+'''
                'vat_summary'   => (float)($data['nds'] ?? 0) > 0
                    ? 'В том числе НДС (' . priceFormat((float)$data['nds']) . '%): '
                        . priceFormat(round($this->ndsCalculate($totalCost, (float)$data['nds']), 2)) . ' руб.'
                    : 'НДС не облагается.',''',1)
 saved=W/'document-corrections-before-20261109';saved.mkdir(mode=0o700)
 shutil.copy2(str(code),str(saved/'ActDataService.php'))
 OVERLAY.mkdir(mode=0o700)
 templates=[write_template('act.docx','3f4b4733a691adbecee86e59731c137904ec69db206513f794683020404e2915',act_xml),
  write_template('contract/ip/application2.docx','27ef3081be9378e0788ada35b3305866083c7ab0314926304d7ff5ee40c88727',application_xml)]
 code.write_text(after);manifest[relative]=sha(code)
 with (W/'candidate-manifest-documents-20261109.json').open('x') as out:out.write(json.dumps(manifest,indent=2,sort_keys=True))
 result={'private_candidate_only':True,'live_crm_changed':False,'original_template_snapshot_unchanged':True,
  'act_vat_uses_prepared_document_rate':True,'act_amount_column_widened':True,'ip_application_uses_current_document_fields':True,
  'code_before_sha256':sha(saved/'ActDataService.php'),'code_after_sha256':sha(code),'templates':templates,
  'candidate_manifest_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 with (W/'document-candidate-corrections-20261109.json').open('x') as out:out.write(json.dumps(result,indent=2))
 with (OVERLAY/'manifest.json').open('x') as out:out.write(json.dumps(templates,indent=2))
 print(json.dumps(result))
if __name__=='__main__':main()
