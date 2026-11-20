"""Prepare four reviewed TS integration files in a private candidate.

Does not deploy, change a DB, renumber orders, edit phones, cron or environment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
PUBLISHER = 'app/Services/Order/GpmAppOrderPublisher.php'
CONTROLLER = 'app/Http/Controllers/Order/ManagerOrderController.php'
SERVICE = 'resources/js/services/LogistOrderDataService.js'
INDEX = 'resources/js/pages/app/orders/logist_orders/index.vue'
EXPECTED = {
    PUBLISHER: '906dacd8a5a1366ada2ad842878305c2d3c7916b9d6f9c05544996ac27668f95',
    CONTROLLER: 'd6fd52b422146f85dc45750979de3861fdcab87cc61848733c320fb899cbb7c3',
    SERVICE: '5657fbb8541023ee9bab8842cbef48fb986c1ecabde3c89a55a86224fe44ae41',
    INDEX: '5d46c56bf4f152de30c08dadb286b0760dc747c53b10d677c87aab19aae0590a',
}
DIALOG = '    <v-dialog v-model="showGpmAppModal" max-width="500" scrollable :persistent="gpmAppSending">\n      <v-card>\n        <v-card-title>Отправить в приложение GPM</v-card-title>\n        <v-card-text>\n          <v-radio-group v-model="gpmAppRecipientMode" row :disabled="gpmAppSending">\n            <v-radio label="По ID в приложении" value="id" />\n            <v-radio label="По телефону" value="phone" />\n          </v-radio-group>\n          <v-text-field v-if="gpmAppRecipientMode === \'id\'"\n            v-model="gpmAppCrmId" label="ID в приложении" placeholder="#1"\n            hint="Указан в профиле логиста Джи Пи Эм" persistent-hint\n            maxlength="10" :disabled="gpmAppSending" />\n          <v-text-field v-else v-model="gpmAppPhone" label="Телефон логиста"\n            placeholder="+7 999 123-45-67" :disabled="gpmAppSending" />\n        </v-card-text>\n        <v-card-actions>\n          <v-btn color="primary" :loading="gpmAppSending" @click="sendToGpmApp(currentItem)">Отправить</v-btn>\n          <v-btn color="error" :disabled="gpmAppSending" @click="closeGpmAppModal">Отмена</v-btn>\n        </v-card-actions>\n      </v-card>\n    </v-dialog>'
SEND = "    sendToGpmApp(item) {\n      if (!item || this.gpmAppSending) return;\n      const byId = this.gpmAppRecipientMode === 'id';\n      const id = String(this.gpmAppCrmId || '').trim();\n      if (byId && !/^#?[1-9][0-9]{0,8}$/.test(id)) {\n        this.$toast.error('Укажите ID в приложении, например #1');\n        return;\n      }\n      if (!byId && !this.gpmAppPhone) {\n        this.$toast.error('Пожалуйста, введите телефон логиста');\n        return;\n      }\n      this.gpmAppSending = true;\n      LogistOrderDataService.publishGpmApp(item.id, byId ? '' : this.gpmAppPhone, byId ? id : '')\n        .then((result) => {\n          if (!result || result.success !== true) {\n            this.$toast.error((result && result.message) || 'Не удалось опубликовать в приложении');\n            return;\n          }\n          this.$toast.success('Заявка опубликована в приложении');\n          this.closeGpmAppModal();\n        })\n        .catch((error) => {\n          const data = error.response && error.response.data;\n          this.$toast.error((data && data.message) || 'Не удалось опубликовать в приложении');\n        })\n        .finally(() => { this.gpmAppSending = false; });\n    },\n\n"
SERVICE_METHOD = "  publishGpmApp(id, phone = '', crmId = '') {\n    const payload = crmId ? { logist_crm_id: crmId } : { logist_phone: phone }\n    return axios\n      .put(this.getUrl.publishGpmApp(id), payload)\n      .then(response => response.data)\n  }\n"
CONTROLLER_METHOD = "    public function publishGpmApp(Order $order, Request $request)\n    {\n        $publisher = new GpmAppOrderPublisher();\n        $success = $publisher->publish($order,\n            (string) $request->input('logist_phone', ''),\n            (string) $request->input('logist_crm_id', ''));\n        return response()->json([\n            'success' => $success,\n            'message' => $success ? 'Заявка опубликована в приложении' : $publisher->errorMessage(),\n        ], $success ? 200 : $publisher->errorStatus());\n    }\n\n"


def between(text, start, end, desired):
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError('Reviewed integration method changed')
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + desired + text[b:]


def transform(files, publisher):
    result = {PUBLISHER: publisher}
    result[CONTROLLER] = between(files[CONTROLLER],
        '    public function publishGpmApp(', '    public function getHistory(', CONTROLLER_METHOD)
    result[SERVICE] = between(files[SERVICE],
        '  publishGpmApp(id, phone) {', '  getHistory(', SERVICE_METHOD + '\n')
    text = files[INDEX]
    blocks = re.findall(r'    <v-dialog v-model="showGpmAppModal"[\s\S]*?</v-dialog>', text)
    if len(blocks) != 2 or blocks[0] != blocks[1]:
        raise RuntimeError('Reviewed duplicate GPM dialogs changed')
    text = text.replace(blocks[0], DIALOG, 1).replace(blocks[1], '', 1)
    marker = '      gpmAppPhone: "",'
    if text.count(marker) != 1:
        raise RuntimeError('Reviewed GPM form state changed')
    text = text.replace(marker, marker + "\n      gpmAppCrmId: '',\n      gpmAppRecipientMode: 'id',\n      gpmAppSending: false,", 1)
    result[INDEX] = between(text, '    sendToGpmApp(item) {', '    async sendToMaxBot(', SEND)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError('Unexpected TS scope')
    output = args.output
    if not output.is_absolute() or output.exists() or output.is_symlink() or output.resolve() != output:
        raise RuntimeError('Candidate must be a new canonical private directory')
    if output == ROOT or ROOT in output.parents or str(output).startswith('/var/www/'):
        raise RuntimeError('Candidate must be outside live hosting')
    files = {}
    for relative, expected in EXPECTED.items():
        source = ROOT / relative
        if source.is_symlink() or ROOT not in source.resolve().parents:
            raise RuntimeError('Unsafe TS source path')
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError('TS source changed; re-inspect before preparing')
        files[relative] = raw.decode('utf-8')
    bundle = Path(__file__).resolve().parents[1]
    desired = transform(files, (bundle / PUBLISHER).read_text())
    os.umask(0o077)
    output.mkdir(mode=0o700)
    changes = []
    for relative, after in desired.items():
        for kind, content in [('before', files[relative]), ('files', after)]:
            target = output / kind / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            os.chmod(target, 0o600)
        changes.append({'file': relative, 'before': EXPECTED[relative], 'after': hashlib.sha256(after.encode()).hexdigest()})
        if relative.endswith('.php'):
            subprocess.run(['/usr/bin/php', '-l', str(output / 'files' / relative)], check=True)
    (output / 'manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    print(json.dumps({'prepared': True, 'live_changed': False, 'files': len(changes)}))


if __name__ == '__main__':
    main()
