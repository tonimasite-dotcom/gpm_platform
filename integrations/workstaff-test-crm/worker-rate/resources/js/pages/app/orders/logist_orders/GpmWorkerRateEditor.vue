<template>
  <v-card class="mb-4">
    <v-card-title>Ставка для рабочих</v-card-title>
    <v-card-text>
      <v-form @submit.prevent="save">
        <v-text-field v-model="rate" label="Ставка рабочим, ₽/час" type="number" min="1" step="1"
          :disabled="saving" :error-messages="error" @input="error = ''" />
        <p>Логист меняет только ставку для рабочих. Адрес и клиентскую ставку меняет менеджер.</p>
        <v-btn type="submit" color="primary" :loading="saving" :disabled="saving || !validRate">
          Сохранить ставку рабочим
        </v-btn>
      </v-form>
    </v-card-text>
  </v-card>
</template>

<script>
import axios from 'axios'
import { API_URL } from '../../../../services/api-url'

export default {
  props: {
    orderId: { type: [String, Number], required: true },
    initialRate: { type: [String, Number], default: null }
  },
  data () {
    return { rate: this.initialRate, saving: false, error: '' }
  },
  computed: {
    validRate () {
      const value = Number(this.rate)
      return Number.isInteger(value) && value > 0 && value <= 100000000
    }
  },
  watch: {
    initialRate (value) { this.rate = value }
  },
  methods: {
    async save () {
      if (!this.validRate || this.saving) return
      this.saving = true
      this.error = ''
      try {
        await axios.patch(`${API_URL}/logist_orders/${encodeURIComponent(this.orderId)}/gpm_worker_rate`, {
          workers_cost: Number(this.rate),
          expected_workers_cost: this.initialRate == null ? null : Number(this.initialRate)
        })
        this.$toast.success('Ставка для рабочих сохранена')
        this.$emit('saved')
      } catch (error) {
        const status = error.response && error.response.status
        this.error = status === 409
          ? 'Заказ закрыт или ставка уже изменилась. Обновите страницу.'
          : status === 403 || status === 404
            ? 'Нет доступа к изменению ставки этого заказа.'
            : 'Не удалось сохранить ставку. Проверьте значение и повторите.'
      } finally {
        this.saving = false
      }
    }
  }
}
</script>
