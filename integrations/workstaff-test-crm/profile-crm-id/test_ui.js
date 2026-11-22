const fs = require('fs')
const vm = require('vm')
const assert = require('assert')
function fragment(text, start, end) {
  assert.strictEqual(text.split(start).length - 1, 1)
  const a = text.indexOf(start); const b = text.indexOf(end, a)
  assert(b > a)
  return text.slice(a, b)
}
const profile = fs.readFileSync(process.argv[2], 'utf8')
const userForm = fs.readFileSync(process.argv[3], 'utf8')
const orders = fs.readFileSync(process.argv[4], 'utf8')
assert(profile.includes('v-if="canUseGpmId"') && profile.includes('v-model="form.gpm_app_crm_id"'))
assert(userForm.includes('v-if="gpmAppIdAllowed"') && userForm.includes('v-model="form.gpm_app_crm_id"'))
const own = vm.runInNewContext('({' + fragment(profile, '    canUseGpmId () {', '\n  },\n\n  created') + '})')
const staff = vm.runInNewContext('({' + fragment(userForm, '    gpmAppIdAllowed () {', '    title:') + '})')
for (const role of ['logist', 'admin', 'loader', 'manager', 'client']) {
  const allowed = ['logist', 'admin'].includes(role)
  const store = { getters: { 'auth/role': (...roles) => roles.includes(role) } }
  assert.strictEqual(own.canUseGpmId.call({ $store: store }), allowed)
  assert.strictEqual(staff.gpmAppIdAllowed.call({ form: { role } }), allowed)
}
const watch = vm.runInNewContext('({' + fragment(userForm, "    'form.role': function", "    'form.fact_address':") + '})')
const change = { form: { gpm_app_crm_id: '#1' } }
watch['form.role'].call(change, 'loader'); assert.strictEqual(change.form.gpm_app_crm_id, '')
const methods = vm.runInNewContext('({' + fragment(orders, '    openGpmAppModal(item) {', '    closeGpmAppModal()') + '})')
for (const saved of ['#1', null]) {
  const view = { $store: { getters: { 'auth/user': { gpm_app_crm_id: saved } } }, gpmAppCrmId: '#999', gpmAppRecipientMode: 'phone' }
  const item = { id: 42, order_number: 'SYNTHETIC/26' }; const before = JSON.stringify(item)
  methods.openGpmAppModal.call(view, item)
  assert.strictEqual(view.gpmAppCrmId, saved || '')
  assert.strictEqual(view.gpmAppRecipientMode, 'id')
  assert.strictEqual(view.showGpmAppModal, true)
  assert.strictEqual(JSON.stringify(item), before)
}
console.log('TS profile ID UI PASS: role visibility, stale field clearing, saved recipient prefill, no stale recipient reuse or order changes')
