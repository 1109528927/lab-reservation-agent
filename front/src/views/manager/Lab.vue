<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

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
  } catch {
    occupancy.value = { schedule: [], reservations: [] }
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
  reserveForm.start = '14:00'
  reserveForm.end = '16:00'
  occupancyDate.value = day
  reserveDialog.value = true
  await loadOccupancy(row.id, occupancyDate.value)
}

const setQuickSlot = (which) => {
  if (!reserveForm.date) {
    const d = new Date()
    const p = (n) => String(n).padStart(2, '0')
    reserveForm.date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  }
  occupancyDate.value = reserveForm.date
  const slots = {
    am: ['08:00', '11:30'],
    pm: ['14:00', '17:30'],
    eve: ['18:30', '21:00'],
    h2: ['14:00', '16:00']
  }
  const [a, b] = slots[which] || slots.h2
  reserveForm.start = a
  reserveForm.end = b
  loadOccupancy(reserveForm.lab_id, reserveForm.date)
}



const submitReserve = async () => {
  const range = buildReserveRange()
  if (!reserveForm.lab_id || !range) {
    ElMessage.warning('请选择日期与起止时间')
    return
  }
  if (range[1] <= range[0]) {
    ElMessage.warning('结束时间须晚于开始时间')
    return
  }
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
      <el-table-column prop="status" label="状态" width="90" />

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
          {{ occupancyDate }} 占用
          <el-button
            link
            type="primary"
            @click="loadOccupancy(reserveForm.lab_id, occupancyDate)"
          >
            刷新
          </el-button>
        </div>
        <div v-if="!occupancy.schedule.length && !occupancy.reservations.length" class="occ-empty">
          当天暂无排课/预约
        </div>
        <div v-for="s in occupancy.schedule" :key="'s' + s.id" class="occ-row sch">
          排课 {{ String(s.start_time).slice(11, 16) }}-{{ String(s.end_time).slice(11, 16) }}
          《{{ s.title }}》
        </div>
        <div v-for="r in occupancy.reservations" :key="'r' + r.id" class="occ-row res">
          预约 {{ String(r.start_time).slice(11, 16) }}-{{ String(r.end_time).slice(11, 16) }}
          {{ r.title }}（{{ r.status }}）
        </div>
      </div>
      <el-form label-width="90px">
        <el-form-item label="预约日期">
          <el-date-picker
            v-model="reserveForm.date"
            type="date"
            placeholder="选一天"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            @change="
              (v) => {
                occupancyDate = v || ''
                loadOccupancy(reserveForm.lab_id, occupancyDate)
              }
            "
          />
        </el-form-item>
        <el-form-item label="快捷">
          <el-button size="small" @click="setQuickSlot('am')">上午 08:00-11:30</el-button>
          <el-button size="small" @click="setQuickSlot('pm')">下午 14:00-17:30</el-button>
          <el-button size="small" @click="setQuickSlot('eve')">晚上 18:30-21:00</el-button>
          <el-button size="small" @click="setQuickSlot('h2')">两小时 14:00-16:00</el-button>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-time-select
            v-model="reserveForm.start"
            start="08:00"
            step="00:30"
            end="21:30"
            placeholder="几点开始"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-select
            v-model="reserveForm.end"
            start="08:30"
            step="00:30"
            end="22:00"
            placeholder="几点结束"
            style="width: 100%"
          />
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
</style>
