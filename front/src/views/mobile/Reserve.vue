<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import ClaimPasscodeDialog from '@/components/ClaimPasscodeDialog.vue'
import request, { getErrorMessage } from '@/utils/request'
import { formatDateTime, reservationStatusLabel } from '@/utils/labels'
import {
  MAX_RESERVE_HOURS,
  computeFreeSlots,
  defaultEndAfterStart,
  disablePastDate,
  todayStr,
  validateReserveRange
} from '@/utils/reserveTime'

const route = useRoute()
const labs = ref([])
const mine = ref([])
const loading = ref(false)
const occupancy = ref({ schedule: [], reservations: [] })
const form = reactive({
  lab_id: null,
  date: '',
  start: '14:00',
  end: '16:00',
  purpose: ''
})

const labName = (id) => labs.value.find((x) => x.id === id)?.name || id

const today = () => todayStr()

/** 占用接口 + 本人同实验室同日活跃预约，双重排除已占时段 */
const freeSlots = computed(() => {
  const date = form.date || today()
  const labId = form.lab_id
  const mineBusy = (mine.value || [])
    .filter(
      (r) =>
        labId &&
        r.lab_id === labId &&
        ['pending', 'approved', 'in_use'].includes(r.status) &&
        String(r.start_time || '').slice(0, 10) === date
    )
    .map((r) => ({
      start_time: r.start_time,
      end_time: r.end_time,
      title: r.purpose || `预约#${r.id}`,
      kind: 'reservation'
    }))
  return computeFreeSlots({
    date,
    schedule: occupancy.value.schedule,
    reservations: [...(occupancy.value.reservations || []), ...mineBusy]
  })
})

const onStartChange = (v) => {
  form.start = v || ''
  if (!form.start) {
    form.end = ''
    return
  }
  if (!form.end || form.end <= form.start) {
    form.end = defaultEndAfterStart(form.start)
  } else {
    const check = validateReserveRange({
      date: form.date || today(),
      start: form.start,
      end: form.end
    })
    if (!check.ok && check.message.includes('最长')) {
      form.end = defaultEndAfterStart(form.start)
    }
  }
}

const applyDefaultIfEmpty = () => {
  const win = freeSlots.value.windows?.[0]
  if (!win) {
    if (!form.start) form.start = ''
    if (!form.end) form.end = ''
    return
  }
  if (!form.start || !form.end) {
    form.start = win.start
    form.end = defaultEndAfterStart(win.start)
    // 默认结束不超过该空闲窗
    if (form.end > win.end) form.end = win.end
  }
}

const loadOccupancy = async () => {
  if (!form.lab_id) {
    occupancy.value = { schedule: [], reservations: [] }
    return
  }
  const date = form.date || today()
  try {
    const res = await request.get(`/api/labs/${form.lab_id}/day-occupancy`, {
      params: { date }
    })
    occupancy.value = {
      schedule: res.data?.data?.schedule || [],
      reservations: res.data?.data?.reservations || []
    }
    applyDefaultIfEmpty()
  } catch {
    occupancy.value = { schedule: [], reservations: [] }
    form.start = ''
    form.end = ''
  }
}

const load = async () => {
  loading.value = true
  try {
    const [l, r] = await Promise.all([
      request.get('/api/labs', { params: { only_open: true } }),
      request.get('/api/reservations/mine')
    ])
    labs.value = l.data?.data?.items || []
    mine.value = r.data?.data?.items || []
    const qid = Number(route.query.lab_id)
    if (qid && labs.value.some((x) => x.id === qid)) {
      form.lab_id = qid
    } else if (!form.lab_id && labs.value.length) {
      form.lab_id = labs.value[0].id
    }
    if (!form.date) form.date = today()
    await loadOccupancy()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

watch(
  () => [form.lab_id, form.date],
  () => loadOccupancy()
)


const submit = async () => {
  if (!form.lab_id) {
    ElMessage.warning('请选择实验室、日期与起止时间')
    return
  }
  const check = validateReserveRange({
    ...form,
    busy: freeSlots.value.busy
  })
  if (!check.ok) {
    ElMessage.warning(check.message)
    return
  }
  const range = check.range
  try {
    const res = await request.post('/api/reservations', {
      lab_id: form.lab_id,
      start_time: range[0],
      end_time: range[1],
      purpose: form.purpose || undefined
    })
    ElMessage.success(res.data?.message || '已提交')
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '预约失败'))
  }
}

const claimDlg = ref(false)
const claimResId = ref(null)

const openClaim = (id) => {
  claimResId.value = id
  claimDlg.value = true
}

const cancel = async (id) => {
  try {
    await request.post(`/api/reservations/${id}/cancel`)
    ElMessage.success('已取消')
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '取消失败'))
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page">
    <ClaimPasscodeDialog
      v-model="claimDlg"
      :reservation-id="claimResId"
      show-pass-link
      @done="load"
    />
    <div class="card">
      <div class="card-t">新建预约</div>
      <div class="occ">
        <div class="label">当前实验室当日已占用（可选时段已自动排除）</div>
        <div v-if="!freeSlots.busy.length" class="empty">暂无排课/预约</div>
        <div v-for="(b, i) in freeSlots.busy" :key="'b' + i" class="occ-line">{{ b.display }}</div>
      </div>
      <div class="field">
        <div class="label">实验室</div>
        <el-select v-model="form.lab_id" style="width: 100%" placeholder="选择">
          <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
        </el-select>
      </div>
      <div class="field">
        <div class="label">预约日期</div>
        <el-date-picker
          v-model="form.date"
          type="date"
          placeholder="选一天"
          value-format="YYYY-MM-DD"
          :disabled-date="disablePastDate"
          style="width: 100%"
        />
      </div>
      <div class="field">
        <div class="label">
          预约时段（自由选择，单次最长 {{ MAX_RESERVE_HOURS }} 小时，可另约续约）
        </div>
        <div v-if="freeSlots.windows?.length" class="win-hint">
          当日空闲：{{ freeSlots.windows.map((w) => w.label).join('、') }}
        </div>
        <div v-else class="empty">该日已无可约空闲</div>
        <div class="time-row">
          <el-time-select
            :model-value="form.start"
            start="08:00"
            step="00:10"
            end="21:50"
            placeholder="开始"
            style="width: 100%"
            @update:model-value="onStartChange"
          />
          <el-time-select
            v-model="form.end"
            start="08:10"
            step="00:10"
            end="22:00"
            :min-time="form.start || '08:00'"
            placeholder="结束"
            style="width: 100%"
          />
        </div>
      </div>
      <div class="field">
        <div class="label">用途</div>
        <el-input v-model="form.purpose" placeholder="可选" />
      </div>
      <el-button type="success" style="width: 100%" @click="submit">提交预约</el-button>
    </div>

    <div class="card">
      <div class="card-t">我的预约</div>
      <div v-if="!mine.length" class="empty">暂无</div>
      <div v-for="r in mine" :key="r.id" class="item">
        <div class="name">{{ labName(r.lab_id) }} · {{ reservationStatusLabel(r.status) }}</div>
        <div class="meta">提交 {{ formatDateTime(r.create_at) }}</div>
        <div class="meta">时段 {{ formatDateTime(r.start_time) }} ~ {{ formatDateTime(r.end_time) }}</div>
        <div class="ops">
          <el-button
            v-if="['approved', 'in_use'].includes(r.status)"
            size="small"
            type="success"
            @click="openClaim(r.id)"
          >
            领通行码
          </el-button>
          <el-button
            v-if="['pending', 'approved', 'in_use'].includes(r.status)"
            size="small"
            type="danger"
            plain
            @click="cancel(r.id)"
          >
            取消
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.card-t {
  font-weight: 600;
  margin-bottom: 10px;
}
.field {
  margin-bottom: 10px;
}
.label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
.item {
  padding: 10px 0;
  border-top: 1px solid #f0f0f0;
}
.name {
  font-size: 14px;
  font-weight: 600;
}
.meta {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}
.ops {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.empty {
  color: #999;
  font-size: 13px;
}
.occ {
  background: #f7f7f7;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 10px;
}
.occ-line {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
.win-hint {
  font-size: 12px;
  color: #67c23a;
  margin-bottom: 8px;
  line-height: 1.4;
}
.time-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
</style>
