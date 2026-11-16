"""Port the existing TS publication dialog and rate-only editor into the private candidate.

Never use this as an installer for live TS. No role, schema or backend change.
"""
import argparse,hashlib,json,os,re
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE=BASE/'rootfs/work/crm-private-01'
TS=Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
FORM='resources/js/pages/app/orders/logist_orders/LogistOrderForm.vue'
INDEX='resources/js/pages/app/orders/logist_orders/index.vue'
SERVICE='resources/js/services/LogistOrderDataService.js'
EDITOR='resources/js/pages/app/orders/logist_orders/GpmWorkerRateEditor.vue'

def one(text,old,new):
    if text.count(old)!=1:raise RuntimeError('FRONTEND_ANCHOR_NOT_UNIQUE:'+old[:80])
    return text.replace(old,new,1)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    if CANDIDATE.resolve()!=CANDIDATE or not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('MARKED_SYNTHETIC_CANDIDATE_REQUIRED')
    changes={}
    source={name:(CANDIDATE/name).read_bytes() for name in [FORM,INDEX,SERVICE]}
    if any(b'GpmWorkerRateEditor' in value or b'showGpmAppModal' in value for value in source.values()):
        raise RuntimeError('FRONTEND_ALREADY_ADAPTED_REVIEW_REQUIRED')
    form=source[FORM].decode().replace('\r\n','\n')
    ts_form=(TS/FORM).read_text()
    component=re.search(r'    <gpm-worker-rate-editor\b.*?/>',ts_form,re.S)
    if not component:raise RuntimeError('EXISTING_TS_RATE_EDITOR_REQUIRED')
    form=one(form,'<template>\n  <div>\n','<template>\n  <div>\n'+component.group(0)+'\n')
    form=one(form,'export default {',"import GpmWorkerRateEditor from './GpmWorkerRateEditor'\n\nexport default {")
    form=one(form,'  components: {','  components: {\n    GpmWorkerRateEditor,')
    if ':readonly="!readonly"' not in form:raise RuntimeError('KEEP_FORM_READONLY_REQUIRED')
    changes[FORM]=form.encode()
    text=source[SERVICE].decode().replace('\r\n','\n');old=(TS/SERVICE).read_text()
    text=one(text,'    this.getUrl.getHistory =',
        '    this.getUrl.publishGpmApp = (id) => `${API_URL}/manager_orders/publish_gpm_app/${id}`\n    this.getUrl.getHistory =')
    start=old.index('  publishGpmApp(');end=old.index('  getHistory(',start)
    text=one(text,'  getHistory(',old[start:end]+'  getHistory(')
    changes[SERVICE]=text.encode()
    text=source[INDEX].decode().replace('\r\n','\n');old=(TS/INDEX).read_text()
    dialog=re.search(r'    <v-dialog v-model="showGpmAppModal".*?</v-dialog>',old,re.S)
    tooltip=re.search(r'            <v-tooltip bottom>\s*<template #activator="\{ on, attrs \}">\s*<v-btn[^>]*@click="openGpmAppModal\(item\)".*?</v-tooltip>',old,re.S)
    if not dialog or not tooltip:raise RuntimeError('EXISTING_TS_PUBLICATION_UI_REQUIRED')
    offset=text.index('    <v-card-text>');text=text[:offset]+dialog.group(0)+'\n'+text[offset:]
    action_start=text.index('@click="openTelegramModal(item)"');offset=text.index('            <v-tooltip bottom>',action_start)
    text=text[:offset]+tooltip.group(0)+'\n'+text[offset:]
    text=one(text,'      currentItem: null,','      showGpmAppModal: false,\n      gpmAppPhone: "",\n      currentItem: null,')
    start=old.index('    openGpmAppModal(');end=old.index('    async sendToMaxBot(',start)
    text=one(text,'    async sendToMaxBot(',old[start:end]+'    async sendToMaxBot(')
    if text.count('<v-dialog v-model="showGpmAppModal"')!=1:raise RuntimeError('ONE_PUBLICATION_DIALOG_REQUIRED')
    changes[INDEX]=text.encode()
    if (CANDIDATE/EDITOR).exists():raise RuntimeError('NEW_EDITOR_PATH_REQUIRED')
    changes[EDITOR]=(TS/EDITOR).read_bytes()
    rows=[{'file':name,'before_sha256':hashlib.sha256(source[name]).hexdigest() if name in source else None,
           'after_sha256':hashlib.sha256(data).hexdigest()} for name,data in changes.items()]
    result={'private_synthetic_only':True,'live_apply_supported':False,'files':rows,
            'existing_readonly_form_preserved':True,'publication_dialog_count':1,'applied':False}
    if args.apply:
        folder=BASE/'frontend-adaptation-20261116-01';folder.mkdir(mode=0o700)
        for name,data in changes.items():
            target=CANDIDATE/name
            if target.exists():
                before=folder/'before'/name;before.parent.mkdir(parents=True,exist_ok=True);before.write_bytes(target.read_bytes())
            target.write_bytes(data)
        result['applied']=True;(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
