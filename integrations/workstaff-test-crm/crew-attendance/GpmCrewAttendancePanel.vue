<template>
  <v-card v-if="visible" class="ma-3" outlined>
    <v-card-title>Онлайн-табель GPM</v-card-title>
    <v-card-text>
      <v-alert v-if="error" dense text type="error">{{ error }}</v-alert>
      <v-progress-linear v-if="busy" indeterminate />
      <template v-if="document.enabled">
        <p>Приход и уход подтверждаются через QR. Старший собирает исполнителей, заказчик подтверждает список.</p>
        <p>Свяжите каждого рабочего CRM с его профилем GPM. В списке доступны исполнители, уже назначенные на эту заявку в GPM.</p>
        <v-simple-table dense>
          <thead><tr><th>Рабочий CRM</th><th>Профиль GPM</th><th>Связь</th></tr></thead>
          <tbody>
            <tr v-for="worker in document.crm_workers || []" :key="worker.id">
              <td>{{ worker.name }}{{ worker.is_leader ? ' · старший' : '' }}</td>
              <td>
                <span v-if="linked(worker.id)">{{ linked(worker.id).worker_name }}</span>
                <v-select v-else v-model="selection[worker.id]" :items="candidates(worker.id)"
                  item-text="label" item-value="worker_account_id" label="Выберите профиль"
                  :disabled="busy" dense hide-details />
              </td>
              <td>
                <span v-if="linked(worker.id)">Связан</span>
                <v-btn v-else small color="primary" :disabled="busy || !selection[worker.id]"
                  @click="link(worker.id)">Связать</v-btn>
              </td>
            </tr>
          </tbody>
        </v-simple-table>
        <v-row class="mt-2">
          <v-col cols="12" md="4">
            <v-btn block color="primary" :disabled="busy || !!error" @click="command('roster')">
              Обновить старшего
            </v-btn>
          </v-col>
          <v-col cols="12" md="4">
            <v-btn block outlined :disabled="busy || !!error" @click="confirmRoster = true">
              Применить состав CRM
            </v-btn>
          </v-col>
          <v-col cols="12" md="4">
            <v-btn v-if="!document.enrolled" block color="primary" :disabled="busy || !!error"
              @click="command('enable')">Включить QR-табель</v-btn>
            <v-chip v-else color="success" outlined>QR-табель включен</v-chip>
          </v-col>
        </v-row>
        <p class="mt-3">Фактическое время исполнителей</p>
        <v-simple-table dense>
          <thead><tr><th>Исполнитель</th><th>Приход</th><th>Уход</th><th>Длительность</th><th>Статус</th></tr></thead>
          <tbody><tr v-for="person in document.rows || []" :key="person.worker_account_id">
            <td>{{ person.worker_name }}{{ person.is_leader ? ' · старший' : '' }}</td>
            <td>{{ time(person.check_in_at) }}</td>
            <td>{{ time(person.check_out_at) }}</td>
            <td>{{ person.duration_minutes == null ? '—' : person.duration_minutes + ' мин' }}</td>
            <td>{{ pending(person.worker_account_id) ? 'На проверке у логиста' : person.check_out_at ? 'Уход подтвержден' : person.check_in_at ? 'Приход подтвержден' : 'Ожидает QR' }}</td>
          </tr></tbody>
        </v-simple-table>
        <v-card v-for="proof in reviews" :key="proof.evidence_id" class="mt-3" outlined>
          <v-card-text>
            <strong>{{ proof.worker_name }} · {{ proof.action === 'check_out' ? 'Уход' : 'Приход' }}</strong>
            <p>Сканирование: {{ time(proof.collected_at) }}. Ожидает решения по геолокации.</p>
            <p v-for="(evidence, index) in [proof.worker_evidence, proof.scanner_evidence]" :key="index">
              {{ index === 0 ? 'Исполнитель' : 'Старший' }}:
              {{ evidence && evidence.reason || 'Геолокация передана' }}
              {{ evidence && evidence.distance_m != null ? ' · ' + evidence.distance_m + ' м от объекта' : '' }}
              {{ evidence && evidence.accuracy != null ? ' · точность ' + evidence.accuracy + ' м' : '' }}
            </p>
            <v-btn small color="primary" :disabled="busy || !!error" @click="openReview(proof, 'approve')">Подтвердить</v-btn>
            <v-btn small outlined class="ml-2" :disabled="busy || !!error" @click="openReview(proof, 'reject')">Отклонить</v-btn>
          </v-card-text>
        </v-card>
        <v-btn text small :disabled="busy" class="mt-2" @click="refresh">Обновить табель</v-btn>
        <span v-if="updatedAt" class="caption">Обновлено {{ time(updatedAt) }}</span>
      </template>
    </v-card-text>
    <v-dialog v-model="reviewDialog" max-width="520">
      <v-card>
        <v-card-title>{{ reviewDecision === 'approve' ? 'Подтвердить отметку' : 'Отклонить отметку' }}</v-card-title>
        <v-card-text>
          <p>{{ reviewProof && reviewProof.worker_name }} · {{ time(reviewProof && reviewProof.collected_at) }}</p>
          <v-textarea v-model="reviewReason" label="Причина решения" maxlength="1000" counter />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn text :disabled="busy" @click="reviewDialog = false">Отмена</v-btn>
          <v-btn color="primary" :disabled="busy || reviewReason.trim().length < 3" @click="saveReview">Сохранить решение</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="confirmRoster" max-width="520">
      <v-card>
        <v-card-title>Применить состав CRM в GPM?</v-card-title>
        <v-card-text>Будет использован назначенный в CRM состав. Снять исполнителя с уже записанными отметками автоматически нельзя.</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn text @click="confirmRoster = false">Отмена</v-btn>
          <v-btn color="primary" :disabled="busy" @click="applyRoster">Подтвердить состав</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script>
import axios from 'axios'
import { API_URL } from '../../../../services/api-url'

export default {
  name: 'GpmCrewAttendancePanel',
  props: { orderId: { type: [String, Number], required: true } },
  data () {
    return {
      document: { enabled: false }, selection: {}, busy: false, error: '', timer: null,
      updatedAt: null, reviewDialog: false, reviewProof: null, reviewDecision: '', reviewReason: '',
      confirmRoster: false
    }
  },
  computed: {
    visible () { return this.document.enabled || !!this.error || this.busy },
    reviews () { return (this.document.proofs || []).filter(p => p.status === 'pending_review') }
  },
  watch: {
    orderId () { this.document = { enabled: false }; this.selection = {}; this.refresh() }
  },
  mounted () {
    this.refresh()
    this.timer = setInterval(() => {
      if (!this.busy && !this.reviewDialog && !this.confirmRoster && this.document.enabled &&
        document.visibilityState === 'visible' && this.$el && this.$el.offsetParent !== null) this.refresh()
    }, 10000)
  },
  beforeDestroy () { clearInterval(this.timer) },
  methods: {
    time (value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('ru-RU')
    },
    linked (id) { return (this.document.rows || []).find(r => String(r.crm_worker_id) === String(id)) },
    pending (id) { return this.reviews.some(p => p.worker_account_id === id) },
    candidates (id) {
      return (this.document.rows || []).filter(r => !r.crm_worker_id || String(r.crm_worker_id) === String(id))
        .map(r => ({ ...r, label: r.worker_name + (r.phone_hint ? ' · ' + r.phone_hint : '') }))
    },
    async request (operation, input = {}) {
      const orderId = this.orderId
      const response = await axios.post(`${API_URL}/logist_orders/gpm_crew/${operation}`, {
        ...input, order_id: Number(orderId)
      })
      if (String(orderId) !== String(this.orderId)) return
      const next = response.data
      if (next.enabled && this.document.order_id === next.order_id &&
        Number(this.document.revision_number || 0) > Number(next.revision_number || 0)) return
      this.document = next
      this.updatedAt = new Date().toISOString()
    },
    failure (error) {
      const response = error.response || {}
      if ([403, 404].includes(response.status)) this.document = { enabled: false }
      const message = response.data && response.data.message
      this.error = typeof message === 'string' ? message : 'Нет связи с GPM. Показаны данные последнего обновления.'
    },
    async refresh () {
      if (this.busy || Number(this.orderId) <= 0) return
      this.busy = true
      try { await this.request('state'); this.error = '' }
      catch (error) { this.failure(error) }
      finally { this.busy = false }
    },
    async command (operation, input = {}) {
      if (this.busy) return
      this.busy = true
      try { await this.request(operation, input); this.error = ''; this.$emit('updated') }
      catch (error) { this.failure(error) }
      finally { this.busy = false }
    },
    link (id) { this.command('link', { crm_worker_id: String(id), worker_account_id: this.selection[id] }) },
    async applyRoster () {
      this.confirmRoster = false
      await this.command('roster', { apply_roster: true, expected_roster: this.document.roster_fingerprint })
    },
    openReview (proof, decision) {
      this.reviewProof = proof; this.reviewDecision = decision; this.reviewReason = ''; this.reviewDialog = true
    },
    async saveReview () {
      if (!this.reviewProof || this.reviewReason.trim().length < 3) return
      await this.command('review', { evidence_id: this.reviewProof.evidence_id,
        decision: this.reviewDecision, reason: this.reviewReason.trim() })
      if (!this.error) this.reviewDialog = false
    }
  }
}
</script>
