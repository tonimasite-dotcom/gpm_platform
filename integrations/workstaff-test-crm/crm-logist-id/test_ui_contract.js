// Exercise the actual prepared Vue submit method and Axios adapter with fake HTTP.
// No browser login, network, CRM account, phone update or order mutation.
const fs = require('fs')
const vm = require('vm')
const assert = require('assert')

function method(text, start, end) {
  assert.strictEqual(text.split(start).length - 1, 1)
  const a = text.indexOf(start)
  const b = text.indexOf(end, a)
  assert(b > a)
  return text.slice(a, b)
}

async function main() {
  const index = fs.readFileSync(process.argv[2], 'utf8')
  const serviceText = fs.readFileSync(process.argv[3], 'utf8')
  assert.strictEqual(index.split('v-model="showGpmAppModal"').length - 1, 1)
  assert(index.includes('label="ID в приложении"'))
  const requests = []
  let finish
  let rejectNext = false
  const axios = { put(url, payload) {
    requests.push({ url, payload: JSON.parse(JSON.stringify(payload)) })
    if (rejectNext) {
      rejectNext = false
      return Promise.reject({ response: { data: { message: 'Synthetic routing error' } } })
    }
    return new Promise(resolve => { finish = resolve })
  } }
  const service = vm.runInNewContext('({' + method(serviceText,
    "  publishGpmApp(id, phone = '', crmId = '') {", '  getHistory(') + '})', { axios })
  service.getUrl = { publishGpmApp: id => '/synthetic/' + id }
  const methods = vm.runInNewContext('({' + method(index,
    '    sendToGpmApp(item) {', '    async sendToMaxBot(') + '})', { LogistOrderDataService: service })
  const errors = []
  let closed = 0
  const view = {
    gpmAppRecipientMode: 'id', gpmAppCrmId: ' #1 ', gpmAppPhone: '+71111111111', gpmAppSending: false,
    $toast: { error: message => errors.push(message), success() {} },
    closeGpmAppModal() { closed++ }
  }
  const item = { id: 42, order_number: 'SYNTHETIC/26', contact_phone: '+72222222222' }
  const before = JSON.stringify(item)
  const tick = () => new Promise(resolve => setImmediate(resolve))
  methods.sendToGpmApp.call(view, item)
  methods.sendToGpmApp.call(view, item)
  assert.strictEqual(requests.length, 1)
  assert.deepStrictEqual(requests[0].payload, { logist_crm_id: '#1' })
  finish({ data: { success: true } })
  await tick()
  assert.strictEqual(view.gpmAppSending, false)
  assert.strictEqual(closed, 1)
  assert.strictEqual(JSON.stringify(item), before)
  view.gpmAppCrmId = '#0'
  methods.sendToGpmApp.call(view, item)
  assert.strictEqual(requests.length, 1)
  assert(errors.pop().includes('ID'))
  view.gpmAppRecipientMode = 'phone'
  methods.sendToGpmApp.call(view, item)
  assert.deepStrictEqual(requests[1].payload, { logist_phone: '+71111111111' })
  finish({ data: { success: true } })
  await tick()
  view.gpmAppRecipientMode = 'id'
  view.gpmAppCrmId = '#1'
  rejectNext = true
  methods.sendToGpmApp.call(view, item)
  await tick()
  assert.strictEqual(errors.pop(), 'Synthetic routing error')
  assert.strictEqual(view.gpmAppSending, false)
  assert.strictEqual(JSON.stringify(item), before)
  console.log('Prepared TS UI contract PASS: separate ID, phone compatibility, no number changes, duplicate click blocked, errors shown')
}

main().catch(error => { console.error(error.message); process.exitCode = 1 })
