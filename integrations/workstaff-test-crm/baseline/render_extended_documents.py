#!/usr/bin/env python3
"""Read private QA PDFs, render every page, and make deduplicated review sheets."""
from pathlib import Path
import sys,json,hashlib,argparse
def main():
 parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--library-path')
 args=parser.parse_args()
 if args.library_path:sys.path.insert(0,args.library_path)
 import pymupdf as fitz
 root=Path(args.folder).resolve();assert root.is_dir()
 index=json.loads((root/'index.json').read_text());output=root/'renders';output.mkdir()
 results=[];unique=[];seen={}
 for item in index:
  document=fitz.open(root/item['file']);pages=[]
  for number,page in enumerate(document):
   text=page.get_text();rect=page.rect;blocks=page.get_text('blocks')
   outside=sum(1 for b in blocks if b[0]<-1 or b[1]<-1 or b[2]>rect.width+1 or b[3]>rect.height+1)
   pix=page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False);digest=hashlib.sha256(pix.samples).hexdigest()
   label=item['file']+' p'+str(number+1)
   if digest not in seen:
    name='page-'+str(len(unique)).zfill(2)+'.png';pix.save(output/name)
    unique.append({'image':name,'label':label,'case':item['case'],'kind':item['kind'],'page':number+1,
     'width':pix.width,'height':pix.height});seen[digest]=name
   pages.append({'page':number+1,'characters':len(text),'unresolved_placeholders':'${' in text,
    'outside_page_blocks':outside,'render_sha256':digest,'review_image':seen[digest]})
  results.append(dict(item,pages=pages))
 sheets=[]
 for start in range(0,len(unique),9):
  contact=fitz.open();canvas=contact.new_page(width=1500,height=2250)
  for i,row in enumerate(unique[start:start+9]):
   x=(i%3)*500;y=(i//3)*750
   canvas.insert_text((x+10,y+14),row['label']+' '+row['kind'],fontsize=10)
   canvas.insert_image(fitz.Rect(x+6,y+25,x+494,y+744),filename=str(output/row['image']),keep_proportion=True)
  name='sheet-'+str(len(sheets)).zfill(2)+'.png';canvas.get_pixmap(alpha=False).save(output/name);sheets.append(name)
 report={'pdfs_checked':len(results),'pages_rendered':sum(len(x['pages']) for x in results),
  'unique_page_renders':len(unique),'review_sheets':sheets,
  'unresolved_placeholders':sum(p['unresolved_placeholders'] for x in results for p in x['pages']),
  'outside_page_blocks':sum(p['outside_page_blocks'] for x in results for p in x['pages']),
  'all_pages_have_text':all(p['characters']>0 for x in results for p in x['pages']),
  'visual_review_completed':False,'contains_private_requisites':True}
 (root/'page-review-index-private.json').write_text(json.dumps(unique,indent=2))
 (root/'page-checks-private.json').write_text(json.dumps(results,indent=2))
 (root/'safe-render-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
