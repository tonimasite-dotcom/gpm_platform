#!/usr/bin/env python3
"""Resolve the inspected candidate using current upstream code plus explicit ts hooks.

This changes ONLY /root/gpm-ts-update/.../candidate and private metadata.
It has no live apply mode and never loads Laravel or reads a database.
"""
from pathlib import Path
import hashlib
import json
import re

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
PRESERVE_TS = {
    'app/Providers/AppServiceProvider.php': 'Preserve ts model guard and provider behavior',
    'config/auth.php': 'Preserve ts login email-code flag; upstream login supports direct JWT',
    'resources/views/spa.blade.php': 'Preserve ts public CAPTCHA fallback and analytics settings',
    'database/migrations/2024_01_25_120000_sync_test_database_structure_with_production.php':
        'Already applied historical migration; preserve ts source and do not rerun',
}
# Existing credential-bearing code is taken from TS itself. Upstream literals are
# never published as a patch or used to configure the candidate.
TS_SETTINGS = (
    'config/yandex-geocoding.php', 'config/banking.php',
    'app/Services/Banking/BankingService.php',
    'app/Services/Settings/BankingSettingsService.php',
    'app/Http/Controllers/BotController.php',
    'app/Http/Controllers/QtsmsSms/test_config.php',
    'app/Traits/sendSmsTrait.php', 'resources/js/plugins/ymapPlugin.js',
)


def one(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Unexpected source anchor: ' + old[:80])
    return text.replace(old, new, 1)


def main():
    if WORK.resolve() != WORK or WORK.is_symlink():
        raise RuntimeError('Unsafe workspace')
    report = json.loads((WORK / 'preparation.json').read_text())
    target = WORK / 'candidate'
    decisions = {}
    for relative in report['source_manifests']['main']:
        p = target / relative
        p.write_bytes((WORK / 'source-main' / relative).read_bytes())
        if relative in report['source_manifests']['ts']:
            decisions[relative] = 'Current upstream common functionality'
    for relative, reason in PRESERVE_TS.items():
        (target / relative).write_bytes((WORK / 'source-ts' / relative).read_bytes())
        decisions[relative] = reason
    for relative in TS_SETTINGS:
        if not (WORK / 'source-ts' / relative).is_file():
            raise RuntimeError('Missing ts configuration source: ' + relative)
        (target / relative).write_bytes((WORK / 'source-ts' / relative).read_bytes())
        decisions[relative] = 'Keep existing ts integration configuration; no upstream credentials'

    def read(name): return (target / name).read_text()
    def save(name, value, why):
        if any(marker in value for marker in ['<<<<<<< upstream', '||||||| ts-git-head', '>>>>>>> live-ts']):
            raise RuntimeError('Unresolved conflict: ' + name)
        (target / name).write_text(value)
        decisions[name] = why

    name = 'app/Http/Controllers/Auth/LoginController.php'
    text = read(name)
    anchor = '            // Mail-code bypass is controlled explicitly; credential/account checks ran above.'
    own_login = """            // Keep the existing TS setting after credentials/account checks.
            if (realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'
                && rtrim((string)config('app.url'), '/') === 'https://ts.workstaffcrm.ru'
                && !config('auth.login_email_code_enabled', true)) {
                return $this->sendLoginResponse($request);
            }
"""
    text = one(text, anchor, own_login + anchor)
    text = one(text, "'max:255', 'exists:users,remember_token'",
               "'max:255', \\Illuminate\\Validation\\Rule::exists('users', 'remember_token')->where('email', (string) $request->input('email'))")
    save(name, text, 'Upstream account checks plus existing ts-only mail-code setting; no credential changes')

    name = 'app/Http/Controllers/Order/ManagerOrderController.php'
    text = read(name)
    text = one(text, 'use App\\Services\\Order\\ManagerOrderService;',
               'use App\\Services\\Order\\ManagerOrderService;\nuse App\\Services\\Order\\GpmAppOrderPublisher;')
    ts = (WORK / 'source-ts' / name).read_text()
    start = ts.index('    public function publishGpmApp(')
    end = ts.index('    public function getHistory(', start)
    text = one(text, '    public function getHistory(', ts[start:end] + '    public function getHistory(')
    save(name, text, 'Upstream controller plus unchanged ts GPM publication method')

    name = 'routes/api.php';text = read(name)
    ts = (WORK / 'source-ts' / name).read_text()
    for key, anchor in [('manager_orders/publish_gpm_app/', "    Route::put('manager_orders/set_feedback/"),
                        ('logist_orders/{order}/gpm_worker_rate', "    Route::resource('logist_orders',")]:
        line = next(line for line in ts.splitlines() if key in line)
        if key in text: raise RuntimeError('GPM route already exists')
        index = text.index(anchor)
        text = text[:index] + line + '\n' + text[index:]
    save(name, text, 'Upstream routes plus two existing authenticated ts GPM routes')

    name = 'resources/js/services/LogistOrderDataService.js';text = read(name)
    text = one(text, "    this.getUrl.getHistory =", "    this.getUrl.publishGpmApp = (id) => `${API_URL}/manager_orders/publish_gpm_app/${id}`\n    this.getUrl.getHistory =")
    ts = (WORK / 'source-ts' / name).read_text()
    start = ts.index('  publishGpmApp(');end = ts.index('  getHistory(', start)
    text = one(text, '  getHistory(', ts[start:end] + '  getHistory(')
    save(name, text, 'Upstream service plus unchanged ts publication request')

    name = 'resources/js/pages/app/orders/logist_orders/LogistOrderForm.vue';text = read(name)
    ts = (WORK / 'source-ts' / name).read_text()
    component = re.search(r'    <gpm-worker-rate-editor\b.*?/>', ts, re.S).group(0)
    text = one(text, '<template>\n  <div>\n', '<template>\n  <div>\n' + component + '\n')
    text = one(text, 'export default {', "import GpmWorkerRateEditor from './GpmWorkerRateEditor'\n\nexport default {")
    text = one(text, '  components: {', '  components: {\n    GpmWorkerRateEditor,')
    save(name, text, 'Latest upstream form plus existing ts rate-only editor and visibility condition')

    name = 'resources/js/pages/app/orders/logist_orders/index.vue';text = read(name)
    ts = (WORK / 'source-ts' / name).read_text()
    dialog = re.search(r'    <v-dialog v-model="showGpmAppModal".*?</v-dialog>', ts, re.S).group(0)
    # Live ts contains duplicate dialogs; preserve one instance of the feature.
    first_card_text = text.index('    <v-card-text>')
    text = text[:first_card_text] + dialog + '\n' + text[first_card_text:]
    tooltip = re.search(r'            <v-tooltip bottom>\s*<template #activator="\{ on, attrs \}">\s*<v-btn[^>]*@click="openGpmAppModal\(item\)".*?</v-tooltip>', ts, re.S).group(0)
    anchor = '            <v-tooltip bottom>'
    # Place in actions next to the existing Telegram/MAX publication actions.
    actions_start = text.index('@click="openTelegramModal(item)"')
    insert_at = text.index(anchor, actions_start)
    text = text[:insert_at] + tooltip + '\n' + text[insert_at:]
    text = one(text, '      currentItem: null,', '      showGpmAppModal: false,\n      gpmAppPhone: "",\n      currentItem: null,')
    start = ts.index('    openGpmAppModal(');end = ts.index('    async sendToMaxBot(', start)
    text = one(text, '    async sendToMaxBot(', ts[start:end] + '    async sendToMaxBot(')
    save(name, text, 'Upstream order list plus existing GPM dialog/action/methods; one dialog instance')

    # TLS options are site settings. Keep exactly TS options while retaining the
    # new upstream banking/payment implementation; values are never logged.
    for name in ['app/Http/Controllers/Payment/TinkofWebhookController.php',
                 'app/Services/Payment/ManagerPaymentService.php']:
        text = read(name);ts = (WORK / 'source-ts' / name).read_text()
        for field in ['cert', 'ssl_key']:
            pattern = re.compile(r"['\"]" + field + r"['\"]\s*=>\s*\[[^\n]+\]")
            own = pattern.findall(ts)
            current = pattern.findall(text)
            if len(own) != len(current): raise RuntimeError('TLS option layout changed')
            for old, new in zip(current, own): text = text.replace(old, new, 1)
        save(name, text, 'Latest upstream payment logic with original ts TLS options')

    # Keep a redacted upstream source archive. TS settings remain only in its
    # private source/candidate, never in public reports or Git.
    literal = re.compile(r'''((?:password|passwd|api[_-]?key|secret|token)['"]?\s*(?:=>|=|:)\s*['"])([^'"\r\n]{8,})(['"])''',re.I)
    for name in TS_SETTINGS:
        p = WORK / 'source-main' / name
        text = p.read_text()
        p.write_text(literal.sub(r'\1UPSTREAM_CREDENTIAL_NOT_IMPORTED\3', text))

    changed = []
    for name, reason in sorted(decisions.items()):
        path = target / name
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        upstream = report['source_manifests']['main'][name]['sha256']
        if sha != upstream:
            changed.append({'path': name, 'sha256': sha, 'upstream_sha256': upstream, 'reason': reason})
    out = {'mode': 'private_candidate_only', 'live_changed': False, 'deployable': False,
           'conflicts_resolved_by_reviewed_upstream_and_ts_hooks': True,
           'upstream_differences': changed,
           'pending': ['migration adapters', 'complete secret review', 'PHP/regression checks',
                       'private frontend build', 'backup/restore and database rehearsal']}
    (WORK / 'candidate-review.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps({'candidate_adaptations': len(changed), 'live_changed': False, 'deployable': False}))


if __name__ == '__main__': main()
