<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PasscodeQrDialog from '@/components/PasscodeQrDialog.vue'
import request, { getErrorMessage } from '@/utils/request'

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

const today = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const padTime = (t) => {
  if (!t) return ''
  return t.length === 5 ? `${t}:00` : t
}

const buildRange = () => {
  if (!form.date || !form.start || !form.end) return null
  return [`${form.date}T${padTime(form.start)}`, `${form.date}T${padTime(form.end)}`]
}

const setQuickSlot = (which) => {
  if (!form.date) form.date = today()
  const slots = {
    am: ['08:00', '11:30'],
    pm: ['14:00', '17:30'],
    eve: ['18:30', '21:00'],
    h2: ['14:00', '16:00']
  }
  const [a, b] = slots[which] || slots.h2
  form.start = a
  form.end = b
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
  } catch {
    occupancy.value = { schedule: [], reservations: [] }
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
  const range = buildRange()
  if (!form.lab_id || !range) {
    ElMessage.warning('请选择实验室、日期与起止时间')
    return
  }
  if (range[1] <= range[0]) {
    ElMessage.warning('结束时间须晚于开始时间')
    return
  }
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

const ack = async (id) => {
  try {
    await request.post('/api/access/safety/ack', { reservation_id: id })
    ElMessage.success('已签须知')
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '签署失败'))
  }
}

const passDlg = ref(false)
const passPayload = ref(null)

const issue = async (id) => {
  try {
    const res = await request.post('/api/access/passcode/issue', { reservation_id: id })
    const data = res.data?.data
    if (data?.code) {
      passPayload.value = data
      await nextTick()
      passDlg.value = true
      ElMessage.success(res.data?.message || '已发码，请截图保存')
    } else {
      ElMessage.success(res.data?.message || '已发码')
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '发码失败'))
  }
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
    <PasscodeQrDialog v-model="passDlg" :passcode="passPayload" show-pass-link />
    <div class="card">
      <div class="card-t">新建预约</div>
      <div class="occ">
        <div class="label">当日占用</div>
        <div v-if="!occupancy.schedule.length && !occupancy.reservations.length" class="empty">
          暂无排课/预约
        </div>
        <div v-for="s in occupancy.schedule" :key="'s' + s.id" class="occ-line">
          排课 {{ String(s.start_time).slice(11, 16) }}-{{ String(s.end_time).slice(11, 16) }}
          《{{ s.title }}》
        </div>
        <div v-for="r in occupancy.reservations" :key="'r' + r.id" class="occ-line">
          预约 {{ String(r.start_time).slice(11, 16) }}-{{ String(r.end_time).slice(11, 16) }}
          （{{ r.status }}）
        </div>
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
          style="width: 100%"
        />
      </div>
      <div class="field">
        <div class="label">快捷时段</div>
        <div class="quick">
          <el-button size="small" @click="setQuickSlot('am')">上午 08:00-11:30</el-button>
          <el-button size="small" @click="setQuickSlot('pm')">下午 14:00-17:30</el-button>
          <el-button size="small" @click="setQuickSlot('eve')">晚上 18:30-21:00</el-button>
          <el-button size="small" @click="setQuickSlot('h2')">两小时 14:00-16:00</el-button>
        </div>
      </div>
      <div class="field time-row">
        <div>
          <div class="label">开始时间</div>
          <el-time-select
            v-model="form.start"
            start="08:00"
            step="00:30"
            end="21:30"
            placeholder="几点开始"
            style="width: 100%"
          />
        </div>
        <div>
          <div class="label">结束时间</div>
          <el-time-select
            v-model="form.end"
            start="08:30"
            step="00:30"
            end="22:00"
            placeholder="几点结束"
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
        <div class="name">{{ labName(r.lab_id) }} · {{ r.status }}</div>
        <div class="meta">{{ r.start_time }}</div>
        <div class="meta">{{ r.end_time }}</div>
        <div class="ops">
          <el-button
            v-if="['approved', 'in_use'].includes(r.status)"
            size="small"
            @click="ack(r.id)"
          >
            签须知
          </el-button>
          <el-button
            v-if="['approved', 'in_use'].includes(r.status)"
            size="small"
            type="success"
            @click="issue(r.id)"
          >
            领码
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
.quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.time-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
</style>
