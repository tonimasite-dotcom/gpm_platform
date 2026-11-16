// Compile actual Vue templates and exercise the rate editor request/error contract.
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const compiler = require('vue-template-compiler')
const root = process.argv[2]
const checks = []
function must (name, value) {
  if (!value) throw new Error(`FRONTEND_ASSERTION:${name}`)
  checks.push(name)
}
for (const name of ['GpmWorkerRateEditor.vue', 'LogistOrderForm.vue', 'index.vue']) {
  const file = path.join(root, 'resources/js/pages/app/orders/logist_orders', name)
  const component = compiler.parseComponent(fs.readFileSync(file, 'utf8'))
  const compiled = compiler.compile(component.template.content)
  must(`${name}_template_compiles`, compiled.errors.length === 0)
}
const text = fs.readFileSync(path.join(root, 'resources/js/pages/app/orders/logist_orders/GpmWorkerRateEditor.vue'), 'utf8')
const parsed = compiler.parseComponent(text)
const script = parsed.script.content.replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
let calls = []
let rejectStatus = null
const axios = { patch: async (url, body) => {
  calls.push({ url, body })
  if (rejectStatus) throw { response: { status: rejectStatus } }
} }
const sandbox = { module: { exports: {} }, axios, API_URL: '/api' }
vm.runInNewContext(script, sandbox)
const component = sandbox.module.exports
function fixture (rate = 700) {
  const result = { rate, initialRate: '600', orderId: '12/34', saving: false, error: '', events: [], toasts: [] }
  result.$toast = { success: message => result.toasts.push(message) }
  result.$emit = event => result.events.push(event)
  Object.defineProperty(result, 'validRate', { get: () => component.computed.validRate.call(result) })
  return result
}
async function main () {
  const item = fixture()
  await component.methods.save.call(item)
  must('one_patch', calls.length === 1)
  must('encoded_order_id', calls[0].url === '/api/logist_orders/12%2F34/gpm_worker_rate')
  must('rate_only_payload', JSON.stringify(calls[0].body) === JSON.stringify({ workers_cost: 700, expected_workers_cost: 600 }))
  must('success_emits_saved', item.events.length === 1 && item.events[0] === 'saved')
  must('success_clears_saving', item.saving === false && item.toasts.length === 1)
  for (const rate of [0, -1, 1.5, '', 'invalid', 100000001]) {
    const invalid = fixture(rate)
    const before = calls.length
    await component.methods.save.call(invalid)
    must(`invalid_${String(rate)}_not_sent`, calls.length === before)
  }
  const busy = fixture(); busy.saving = true
  const before = calls.length
  await component.methods.save.call(busy)
  must('duplicate_save_not_sent', calls.length === before)
  for (const status of [409, 403, 404, 422, 500]) {
    rejectStatus = status
    const item = fixture()
    await component.methods.save.call(item)
    must(`error_${status}_preserves_input_and_clears_saving`, item.rate === 700 && !item.saving && item.error.length > 0 && item.events.length === 0 && item.toasts.length === 0)
  }
  const refreshed = fixture()
  component.watch.initialRate.call(refreshed, 650)
  must('fresh_rate_updates_editor', refreshed.rate === 650)
  process.stdout.write(JSON.stringify({ status: 'PASS', scenarios: checks.length, checks, browser_rendered: false, actual_http_used: false }))
}
main().catch(error => { process.stderr.write(String(error)); process.exitCode = 1 })
