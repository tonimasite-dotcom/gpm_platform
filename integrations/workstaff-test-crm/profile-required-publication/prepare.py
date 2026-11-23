"""Prepare only the TS publication UI/service delta after the profile-ID release."""
from pathlib import Path
import argparse,hashlib,json
DIALOG = "          <v-alert v-if=\"!gpmAppCrmId\" type=\"warning\" outlined>\n            Сначала добавьте ID в приложении в настройках профиля.\n            <router-link :to=\"{ name: 'user.profile' }\">Открыть профиль</router-link>\n          </v-alert>\n          <v-text-field v-model=\"gpmAppCrmId\" label=\"ID в приложении\"\n            hint=\"Из настроек вашего профиля\" persistent-hint readonly />\n"
METHODS = "    openGpmAppModal(item) {\n      const profile = this.$store.getters['auth/user'];\n      this.gpmAppCrmId = profile && profile.gpm_app_crm_id ? String(profile.gpm_app_crm_id) : '';\n      this.currentItem = item;\n      this.showGpmAppModal = true;\n    },\n    closeGpmAppModal() {\n      this.showGpmAppModal = false;\n      this.gpmAppCrmId = '';\n    },\n    sendToGpmApp(item) {\n      if (!item || this.gpmAppSending) return;\n      const profile = this.$store.getters['auth/user'];\n      const id = profile && profile.gpm_app_crm_id ? String(profile.gpm_app_crm_id).trim() : '';\n      if (!/^#?[1-9][0-9]{0,8}$/.test(id)) {\n        this.$toast.error('Сначала добавьте ID в приложении в настройках профиля');\n        return;\n      }\n      this.gpmAppCrmId = id;\n      this.gpmAppSending = true;\n      LogistOrderDataService.publishGpmApp(item.id, id)\n        .then((result) => {\n          if (!result || result.success !== true) {\n            this.$toast.error((result && result.message) || 'Не удалось опубликовать в приложении');\n            return;\n          }\n          this.$toast.success('Заявка опубликована в приложении');\n          this.closeGpmAppModal();\n        })\n        .catch((error) => {\n          const data = error.response && error.response.data;\n          this.$toast.error((data && data.message) || 'Не удалось опубликовать в приложении');\n        })\n        .finally(() => { this.gpmAppSending = false; });\n    },\n"
def digest(data): return hashlib.sha256(data).hexdigest()
def replace_once(text, old, new):
    if text.count(old) != 1: raise RuntimeError('Expected source contract changed')
    return text.replace(old,new,1)
def prepare(root, output):
    if root.resolve() != root or not root.is_dir(): raise RuntimeError('Noncanonical TS source')
    output.mkdir(parents=True,exist_ok=False)
    paths = ['resources/js/pages/app/orders/logist_orders/index.vue','resources/js/services/LogistOrderDataService.js']
    tracked=[]
    for rel in paths:
        target=root/rel
        if target.is_symlink() or root not in target.resolve().parents: raise RuntimeError('Unsafe source')
        before=target.read_bytes(); text=before.decode('utf-8')
        if rel.endswith('index.vue'):
            start=text.index('          <v-radio-group v-model="gpmAppRecipientMode"')
            end=text.index('        </v-card-text>',start)
            text=text[:start]+DIALOG+text[end:]
            text=replace_once(text,':loading="gpmAppSending" @click="sendToGpmApp(currentItem)"',':loading="gpmAppSending" :disabled="!gpmAppCrmId" @click="sendToGpmApp(currentItem)"')
            text=replace_once(text,'      gpmAppPhone: "",\n','')
            text=replace_once(text,"      gpmAppRecipientMode: 'id',\n",'')
            start=text.index('    openGpmAppModal(item) {')
            end=text.index('    async sendToMaxBot(item)',start)
            text=text[:start]+METHODS+'\n'+text[end:]
        else:
            text=replace_once(text,"  publishGpmApp(id, phone = '', crmId = '') {\n    const payload = crmId ? { logist_crm_id: crmId } : { logist_phone: phone }","  publishGpmApp(id, crmId = '') {\n    const payload = { logist_crm_id: crmId }")
        after=text.encode('utf-8')
        for folder,data in [('before',before),('files',after)]:
            path=output/folder/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        tracked.append({'file':rel,'before':digest(before),'after':digest(after)})
    (output/'preparation-result.json').write_text(json.dumps({'tracked':tracked,'schema_changed':False},indent=2)+'\n')
    print(json.dumps({'prepared':True,'files':len(tracked),'schema_changed':False}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();prepare(a.root,a.output)
