const fs = require('fs')
const vm = require('vm')
const assert = require('assert')
const orders = fs.readFileSync(process.argv[2], 'utf8')
const serviceSource = fs.readFileSync(process.argv[3], 'utf8')
assert(!orders.includes('gpmAppRecipientMode') && !orders.includes('gpmAppPhone'))
assert(orders.includes('persistent-hint readonly'))
assert(orders.includes(':disabled="!gpmAppCrmId"'))
assert(orders.includes("name: 'user.profile'"))
assert(!serviceSource.includes('const payload = crmId ?'))
assert(serviceSource.includes('const payload = { logist_crm_id: crmId }'))
const start = orders.indexOf('    openGpmAppModal(item) {')
const end = orders.indexOf('    async sendToMaxBot(item)', start)
assert(start >= 0 && end > start)
const calls = []
const api = { publishGpmApp: (...args) => { calls.push(args); return Promise.resolve({ success: true }) } }
const methods = vm.runInNewContext('({' + orders.slice(start, end) + '})', { LogistOrderDataService: api })
async function run() {
  for (const saved of [null, '', '#1', 1]) {
    calls.length = 0
    const errors = []
    const view = { $store: { getters: { 'auth/user': { gpm_app_crm_id: saved } } },
      $toast: { error: message => errors.push(message), success: () => {} },
      gpmAppCrmId: '#999', showGpmAppModal: false, gpmAppSending: false }
    view.closeGpmAppModal = methods.closeGpmAppModal.bind(view)
    const item = { id: 42, order_number: 'SYNTHETIC/26' }
    const before = JSON.stringify(item)
    methods.openGpmAppModal.call(view, item)
    assert.strictEqual(view.gpmAppCrmId, saved ? String(saved) : '')
    assert.strictEqual(view.showGpmAppModal, true)
    view.gpmAppCrmId = '#999'
    methods.sendToGpmApp.call(view, item)
    await new Promise(resolve => setImmediate(resolve))
    if (saved) {
      assert.strictEqual(calls.length, 1)
      assert.deepStrictEqual(calls[0], [42, String(saved)])
      assert.strictEqual(view.showGpmAppModal, false)
      assert.strictEqual(view.gpmAppCrmId, '')
    } else {
      assert.strictEqual(calls.length, 0)
      assert.strictEqual(errors.length, 1)
      assert(errors[0].includes('настройках профиля'))
    }
    assert.strictEqual(JSON.stringify(item), before)
  }
  calls.length = 0
  const view = { $store: { getters: { 'auth/user': { gpm_app_crm_id: '#1' } } }, $toast: { error: () => {}, success: () => {} } }
  methods.openGpmAppModal.call(view, { id: 1 })
  view.$store.getters['auth/user'].gpm_app_crm_id = null
  methods.sendToGpmApp.call(view, { id: 1 })
  assert.strictEqual(calls.length, 0)
  console.log('TS publication UI PASS: saved profile ID required, automatic prefill, readonly recipient, forged dialog ID rejected, no phone fallback, profile removal blocks sending')
}
run().catch(error => { console.error(error); process.exitCode = 1 })
