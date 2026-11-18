import hashlib,json,time,urllib.request,subprocess
from pathlib import Path
base='https://app.gpmbot.ru/'
stamp=str(int(time.time()))
def get(path):
    with urllib.request.urlopen(base+path+'?design_check='+stamp,timeout=60) as response:
        assert response.status==200
        return response.read()
get('')
manifest=json.loads(get('assets/FontManifest.json'))
family=next(row for row in manifest if row['family']=='Manrope')
assert {row['weight'] for row in family['fonts']}=={400,500,600,700,800}
checks=[]
for p in sorted(Path('assets/fonts').glob('*')):
    if p.suffix not in {'.ttf','.txt'}:continue
    content=get('assets/assets/fonts/'+p.name)
    expected=hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+p.as_posix()])).hexdigest()
    assert hashlib.sha256(content).hexdigest()==expected
    checks.append({'asset':p.name,'sha256':expected})
for path in ['assets/images/gpm_logo.png', 'assets/images/gpm_logo_refined.png', 'web/favicon.png',
             'web/icons/Icon-192.png', 'web/icons/Icon-512.png', 'web/manifest.json']:
    url_path = path.removeprefix('web/') if path.startswith('web/') else 'assets/' + path
    content = get(url_path)
    expected = hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+path])).hexdigest()
    assert hashlib.sha256(content).hexdigest() == expected, path
    checks.append({'asset':path,'sha256':expected})
js=get('main.dart.js')
text=js.decode('utf8')
headline='Люди. Работа.'
assert 'Manrope' in text and (headline in text or json.dumps(headline,ensure_ascii=True)[1:-1].lower() in text.lower())
result={'status':'PASS','url':base,'manrope_weights':sorted(row['weight'] for row in family['fonts']),
        'live_font_and_license_hashes_match':True,'logo_and_web_icons_match':True,'assets':checks,'new_login_headline_in_bundle':True,
        'main_js_sha256':hashlib.sha256(js).hexdigest(),'main_js_bytes':len(js),'backend_requests_made':False}
output=Path('.tmp/live-app-design-verification.json')
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='assets'}))
