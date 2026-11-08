<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
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
const loading = ref(false)
const mine = ref([])
const pending = ref([])
const labs = ref([])
const dialog = ref(false)
const form = reactive({
  lab_id: null,
  date: '',
  start: '14:00',
  end: '16:00',
  purpose: ''
})
const occupancy = ref({ schedule: [], reservations: [] })
const occupancyDate = ref('')

const freeSlots = computed(() => {
  const date = form.date || occupancyDate.value
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
      date: form.date || occupancyDate.value,
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
    if (form.end > win.end) form.end = win.end
  }
}

const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})
const isAdmin = computed(() => user.value.role === 'admin')

const labName = (id) => labs.value.find((x) => x.id === id)?.name || id

const loadOccupancy = async () => {
  if (!form.lab_id || !occupancyDate.value) {
    occupancy.value = { schedule: [], reservations: [] }
    return
  }
  try {
    const res = await request.get(`/api/labs/${form.lab_id}/day-occupancy`, {
      params: { date: occupancyDate.value }
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


const loadLabs = async () => {
  const res = await request.get('/api/labs', { params: { only_open: true } })
  labs.value = res.data?.data?.items || []
}

const loadMine = async () => {
  const res = await request.get('/api/reservations/mine')
  mine.value = res.data?.data?.items || []
}

const loadPending = async () => {
  if (!isAdmin.value) return
  const res = await request.get('/api/reservations', { params: { status: 'pending' } })
  pending.value = res.data?.data?.items || []
}

const load = async () => {
  loading.value = true
  try {
    await loadLabs()
    await loadMine()
    await loadPending()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const openCreate = async (preferLabId) => {
  const qid = preferLabId ?? Number(route.query.lab_id)
  form.lab_id =
    qid && labs.value.some((x) => x.id === qid) ? qid : labs.value[0]?.id || null
  form.purpose = ''
  form.start = ''
  form.end = ''
  form.date = todayStr()
  occupancyDate.value = form.date
  dialog.value = true
  await loadOccupancy()
}


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
    ElMessage.success(res.data?.message || '提交成功')
    dialog.value = false
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '预约失败（可能时段冲突）'))
  }
}

const approve = async (id) => {
  try {
    await request.post(`/api/reservations/${id}/approve`)
    ElMessage.success('已通过')
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '操作失败'))
  }
}

/** 规则批量自动通过（不调用大模型） */
const autoProcessRules = async (dryRun = false) => {
  try {
    const res = await request.post('/api/reservations/auto-process', null, {
      params: { limit: 20, dry_run: dryRun }
    })
    const d = res.data?.data || {}
    const n = (d.auto_approved || []).length
    const h = (d.need_human || []).length
    ElMessage.success(
      dryRun
        ? `演练：可自动通过 ${n} 条，需人工 ${h} 条`
        : `规则自动通过 ${n} 条，仍待人工 ${h} 条`
    )
    if (!dryRun) load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '规则自动审批失败'))
  }
}

const reject = async (id) => {
  try {
    await request.post(`/api/reservations/${id}/reject`, { reason: '时段安排冲突或不符合规定' })
    ElMessage.success('已驳回')
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '操作失败'))
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

const claimDlg = ref(false)
const claimResId = ref(null)

const openClaim = (id) => {
  claimResId.value = id
  claimDlg.value = true
}

onMounted(async () => {
  await load()
  if (route.query.lab_id) openCreate()
})
</script>

<template>
  <div v-loading="loading">
    <ClaimPasscodeDialog v-model="claimDlg" :reservation-id="claimResId" @done="load" />
    <div class="bar">
      <h2>预约管理</h2>
      <div>
        <el-button @click="load">刷新</el-button>
        <el-button v-if="isAdmin" @click="autoProcessRules(true)">规则演练</el-button>
        <el-button v-if="isAdmin" type="success" @click="autoProcessRules(false)">
          规则自动通过
        </el-button>
        <el-button type="primary" @click="openCreate">新建预约</el-button>
      </div>
    </div>

    <h3>我的预约</h3>
    <el-table :data="mine" style="margin-bottom: 24px" empty-text="暂无预约">
      <el-table-column label="实验室" min-width="120">
        <template #default="{ row }">{{ labName(row.lab_id) }}</template>
      </el-table-column>
      <el-table-column label="提交时间" min-width="150">
        <template #default="{ row }">{{ formatDateTime(row.create_at) }}</template>
      </el-table-column>
      <el-table-column label="开始" min-width="150">
        <template #default="{ row }">{{ formatDateTime(row.start_time) }}</template>
      </el-table-column>
      <el-table-column label="结束" min-width="150">
        <template #default="{ row }">{{ formatDateTime(row.end_time) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ reservationStatusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column prop="purpose" label="用途" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button
            v-if="['approved', 'in_use'].includes(row.status)"
            link
            type="success"
            @click="openClaim(row.id)"
          >
            领通行码
          </el-button>
          <el-button
            v-if="['pending', 'approved'].includes(row.status)"
            link
            type="danger"
            @click="cancel(row.id)"
          >
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <template v-if="isAdmin">
      <h3>待审批</h3>
      <el-table :data="pending" empty-text="没有待审批">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="实验室" min-width="120">
          <template #default="{ row }">{{ labName(row.lab_id) }}</template>
        </el-table-column>
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="start_time" label="开始" min-width="160" />
        <el-table-column prop="end_time" label="结束" min-width="160" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="success" @click="approve(row.id)">通过</el-button>
            <el-button link type="danger" @click="reject(row.id)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <el-dialog v-model="dialog" title="新建预约" width="520px">
      <div class="occ">
        <div class="occ-t">{{ occupancyDate }} 已占用（自动排除）</div>
        <div v-if="!freeSlots.busy.length" class="occ-empty">当天暂无排课/预约</div>
        <div v-for="(b, i) in freeSlots.busy" :key="'b' + i" class="occ-row sch">{{ b.display }}</div>
      </div>
      <el-form label-width="90px">
        <el-form-item label="实验室">
          <el-select
            v-model="form.lab_id"
            style="width: 100%"
            placeholder="选择实验室"
            @change="loadOccupancy"
          >
            <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="预约日期">
          <el-date-picker
            v-model="form.date"
            type="date"
            placeholder="选一天"
            value-format="YYYY-MM-DD"
            :disabled-date="disablePastDate"
            style="width: 100%"
            @change="
              (v) => {
                occupancyDate = v || ''
                loadOccupancy()
              }
            "
          />
        </el-form-item>
        <el-form-item :label="`时段(≤${MAX_RESERVE_HOURS}h)`">
          <div v-if="freeSlots.windows?.length" class="occ-empty" style="margin-bottom: 6px">
            当日空闲：{{ freeSlots.windows.map((w) => w.label).join('、') }}
          </div>
          <div v-else class="occ-empty" style="margin-bottom: 6px">该日已无可约空闲</div>
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
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="form.purpose" placeholder="课程实验 / 项目调试等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="submit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
h3 {
  margin: 8px 0 10px;
  font-size: 16px;
}
.occ {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.occ-t {
  font-weight: 600;
  margin-bottom: 6px;
}
.occ-empty {
  color: #909399;
}
.occ-row {
  margin-top: 4px;
}
.occ-row.sch {
  color: #e6a23c;
}
.occ-row.res {
  color: #409eff;
}
.time-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  width: 100%;
}
</style>
