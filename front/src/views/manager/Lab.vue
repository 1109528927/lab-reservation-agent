<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'
import { labStatusLabel, reservationStatusLabel } from '@/utils/labels'
import {
  MAX_RESERVE_HOURS,
  computeFreeSlots,
  defaultEndAfterStart,
  disablePastDate,
  validateReserveRange
} from '@/utils/reserveTime'

const loading = ref(false)
const items = ref([])
const dialog = ref(false)
const reserveDialog = ref(false)
const filters = reactive({
  keyword: '',
  status: ''
})

const form = reactive({
  id: null,
  name: '',
  location: '',
  capacity: 20,
  need_approve: 1,
  status: 'open',
  description: ''
})
const reserveForm = reactive({
  lab_id: null,
  lab_name: '',
  date: '',
  start: '14:00',
  end: '16:00',
  purpose: ''
})
const occupancy = ref({ schedule: [], reservations: [] })
const occupancyDate = ref('')

const padTime = (t) => (t && t.length === 5 ? `${t}:00` : t || '')
const buildReserveRange = () => {
  if (!reserveForm.date || !reserveForm.start || !reserveForm.end) return null
  return [
    `${reserveForm.date}T${padTime(reserveForm.start)}`,
    `${reserveForm.date}T${padTime(reserveForm.end)}`
  ]
}


const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})
const isAdmin = computed(() => user.value.role === 'admin')


const filtered = computed(() => {
  const kw = filters.keyword.trim().toLowerCase()
  return items.value.filter((row) => {
    if (filters.status && row.status !== filters.status) return false
    if (!kw) return true
    const blob = `${row.name || ''} ${row.location || ''} ${row.description || ''}`.toLowerCase()
    return blob.includes(kw)
  })
})


const load = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/labs')
    items.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  Object.assign(form, {
    id: null,
    name: '',
    location: '',
    capacity: 20,
    need_approve: 1,
    status: 'open',
    description: ''
  })
  dialog.value = true
}

const openEdit = (row) => {
  Object.assign(form, { ...row })
  dialog.value = true
}

const save = async () => {
  if (!form.name?.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  try {
    const payload = {
      name: form.name,
      location: form.location,
      capacity: form.capacity,
      need_approve: form.need_approve,
      status: form.status,
      description: form.description
    }
    if (form.id) {
      await request.put(`/api/labs/${form.id}`, payload)
      ElMessage.success('已更新')
    } else {
      await request.post('/api/labs', payload)
      ElMessage.success('已创建')
    }
    dialog.value = false
    load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '保存失败'))
  }
}

const toggleClose = async (row) => {
  const next = row.status === 'open' ? 'closed' : 'open'
  const tip = next === 'closed' ? '关闭后学生将无法新预约该实验室' : '重新开放该实验室？'
  try {
    await ElMessageBox.confirm(tip, '确认', { type: 'warning' })
    await request.put(`/api/labs/${row.id}`, { status: next })
    ElMessage.success(next === 'closed' ? '已关闭' : '已开放')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(getErrorMessage(e, '操作失败'))
  }
}

const freeSlots = computed(() =>
  computeFreeSlots({
    date: reserveForm.date || occupancyDate.value,
    schedule: occupancy.value.schedule,
    reservations: occupancy.value.reservations
  })
)

const onStartChange = (v) => {
  reserveForm.start = v || ''
  if (!reserveForm.start) {
    reserveForm.end = ''
    return
  }
  if (!reserveForm.end || reserveForm.end <= reserveForm.start) {
    reserveForm.end = defaultEndAfterStart(reserveForm.start)
  } else {
    const check = validateReserveRange({
      date: reserveForm.date || occupancyDate.value,
      start: reserveForm.start,
      end: reserveForm.end
    })
    if (!check.ok && check.message.includes('最长')) {
      reserveForm.end = defaultEndAfterStart(reserveForm.start)
    }
  }
}

const applyDefaultIfEmpty = () => {
  const win = freeSlots.value.windows?.[0]
  if (!win) {
    if (!reserveForm.start) reserveForm.start = ''
    if (!reserveForm.end) reserveForm.end = ''
    return
  }
  if (!reserveForm.start || !reserveForm.end) {
    reserveForm.start = win.start
    reserveForm.end = defaultEndAfterStart(win.start)
    if (reserveForm.end > win.end) reserveForm.end = win.end
  }
}

const loadOccupancy = async (labId, dateStr) => {
  if (!labId || !dateStr) {
    occupancy.value = { schedule: [], reservations: [] }
    return
  }
  try {
    const res = await request.get(`/api/labs/${labId}/day-occupancy`, {
      params: { date: dateStr }
    })
    occupancy.value = {
      schedule: res.data?.data?.schedule || [],
      reservations: res.data?.data?.reservations || []
    }
    applyDefaultIfEmpty()
  } catch {
    occupancy.value = { schedule: [], reservations: [] }
    reserveForm.start = ''
    reserveForm.end = ''
  }
}

const openReserve = async (row) => {
  if (row.status !== 'open') {
    ElMessage.warning('该实验室已关闭，无法预约')
    return
  }
  reserveForm.lab_id = row.id
  reserveForm.lab_name = row.name
  reserveForm.purpose = ''
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  const day = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  reserveForm.date = day
  reserveForm.start = ''
  reserveForm.end = ''
  occupancyDate.value = day
  reserveDialog.value = true
  await loadOccupancy(row.id, occupancyDate.value)
}



const submitReserve = async () => {
  if (!reserveForm.lab_id) {
    ElMessage.warning('请选择实验室')
    return
  }
  const check = validateReserveRange({
    ...reserveForm,
    busy: freeSlots.value.busy
  })
  if (!check.ok) {
    ElMessage.warning(check.message)
    return
  }
  const range = check.range
  try {
    const res = await request.post('/api/reservations', {
      lab_id: reserveForm.lab_id,
      start_time: range[0],
      end_time: range[1],
      purpose: reserveForm.purpose || undefined
    })
    ElMessage.success(res.data?.message || '预约已提交')
    reserveDialog.value = false
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '预约失败（可能时段冲突）'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="bar">
      <h2>实验室管理</h2>
      <div>
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button v-if="isAdmin" type="primary" @click="openCreate">新建实验室</el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
      title="老师预约直接通过；学生预约须学校管理员审核。排课占档请到「排课管理」。"
    />

    <el-form :inline="true" class="filters" @submit.prevent>
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="名称 / 位置 / 简介"
          style="width: 200px"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="开放" value="open" />
          <el-option label="关闭" value="closed" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <span class="count">共 {{ filtered.length }} / {{ items.length }} 间</span>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="filtered" empty-text="没有匹配的实验室">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="location" label="位置" min-width="140" />
      <el-table-column prop="capacity" label="容量" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ labStatusLabel(row.status) }}</template>
      </el-table-column>

      <el-table-column label="操作" :width="isAdmin ? 220 : 100" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="success"
            :disabled="row.status !== 'open'"
            @click="openReserve(row)"
          >
            预约
          </el-button>
          <template v-if="isAdmin">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :type="row.status === 'open' ? 'danger' : 'warning'"
              @click="toggleClose(row)"
            >
              {{ row.status === 'open' ? '关闭' : '开放' }}
            </el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="form.id ? '编辑实验室' : '新建实验室'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" />
        </el-form-item>
        <el-form-item label="容量">
          <el-input-number v-model="form.capacity" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="状态">

          <el-select v-model="form.status" style="width: 100%">
            <el-option label="开放" value="open" />
            <el-option label="关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reserveDialog" :title="`预约 · ${reserveForm.lab_name}`" width="520px">
      <div class="occ">
        <div class="occ-t">
          {{ occupancyDate }} 已占用（自动排除）
          <el-button
            link
            type="primary"
            @click="loadOccupancy(reserveForm.lab_id, occupancyDate)"
          >
            刷新
          </el-button>
        </div>
        <div v-if="!freeSlots.busy.length" class="occ-empty">当天暂无排课/预约</div>
        <div v-for="(b, i) in freeSlots.busy" :key="'b' + i" class="occ-row sch">
          {{ b.display }}
        </div>
      </div>
      <el-form label-width="90px">
        <el-form-item label="预约日期">
          <el-date-picker
            v-model="reserveForm.date"
            type="date"
            placeholder="选一天"
            value-format="YYYY-MM-DD"
            :disabled-date="disablePastDate"
            style="width: 100%"
            @change="
              (v) => {
                occupancyDate = v || ''
                loadOccupancy(reserveForm.lab_id, occupancyDate)
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
              :model-value="reserveForm.start"
              start="08:00"
              step="00:10"
              end="21:50"
              placeholder="开始"
              style="width: 100%"
              @update:model-value="onStartChange"
            />
            <el-time-select
              v-model="reserveForm.end"
              start="08:10"
              step="00:10"
              end="22:00"
              :min-time="reserveForm.start || '08:00'"
              placeholder="结束"
              style="width: 100%"
            />
          </div>
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="reserveForm.purpose" placeholder="课程实验 / 项目调试等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reserveDialog = false">取消</el-button>
        <el-button type="success" @click="submitReserve">提交预约</el-button>
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
.filters {
  margin-bottom: 8px;
}
.count {
  color: #909399;
  font-size: 13px;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
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
