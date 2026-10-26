<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PasscodeQrDialog from '@/components/PasscodeQrDialog.vue'
import request, { getErrorMessage } from '@/utils/request'

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

const padTime = (t) => (t && t.length === 5 ? `${t}:00` : t || '')
const buildRange = () => {
  if (!form.date || !form.start || !form.end) return null
  return [`${form.date}T${padTime(form.start)}`, `${form.date}T${padTime(form.end)}`]
}
const setQuickSlot = (which) => {
  if (!form.date) {
    const d = new Date()
    const p = (n) => String(n).padStart(2, '0')
    form.date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  }
  occupancyDate.value = form.date
  const slots = {
    am: ['08:00', '11:30'],
    pm: ['14:00', '17:30'],
    eve: ['18:30', '21:00'],
    h2: ['14:00', '16:00']
  }
  const [a, b] = slots[which] || slots.h2
  form.start = a
  form.end = b
  loadOccupancy()
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
  } catch {
    occupancy.value = { schedule: [], reservations: [] }
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
  form.start = '14:00'
  form.end = '16:00'
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  form.date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  occupancyDate.value = form.date
  dialog.value = true
  await loadOccupancy()
}


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

const ackSafety = async (id) => {
  try {
    await request.post('/api/access/safety/ack', { reservation_id: id })
    ElMessage.success('安全须知已签署')
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '签署失败'))
  }
}

const passDlg = ref(false)
const passPayload = ref(null)

const issueCode = async (id) => {
  try {
    const res = await request.post('/api/access/passcode/issue', { reservation_id: id })
    const data = res.data?.data
    if (data?.code) {
      passPayload.value = data
      passDlg.value = true
      ElMessage.success(res.data?.message || '已发码，请截图保存')
    } else {
      ElMessage.success(res.data?.message || '已发码')
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '发码失败（请先签署须知）'))
  }
}

onMounted(async () => {
  await load()
  if (route.query.lab_id) openCreate()
})
</script>

<template>
  <div v-loading="loading">
    <PasscodeQrDialog v-model="passDlg" :passcode="passPayload" />
    <div class="bar">
      <h2>预约管理</h2>
      <div>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建预约</el-button>
      </div>
    </div>

    <h3>我的预约</h3>
    <el-table :data="mine" style="margin-bottom: 24px" empty-text="暂无预约">
      <el-table-column label="实验室" min-width="120">
        <template #default="{ row }">{{ labName(row.lab_id) }}</template>
      </el-table-column>
      <el-table-column prop="start_time" label="开始" min-width="160" />
      <el-table-column prop="end_time" label="结束" min-width="160" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="purpose" label="用途" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button
            v-if="['approved', 'in_use'].includes(row.status)"
            link
            type="primary"
            @click="ackSafety(row.id)"
          >
            签须知
          </el-button>
          <el-button
            v-if="['approved', 'in_use'].includes(row.status)"
            link
            type="success"
            @click="issueCode(row.id)"
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
        <div class="occ-t">{{ occupancyDate }} 占用</div>
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
            style="width: 100%"
            @change="
              (v) => {
                occupancyDate = v || ''
                loadOccupancy()
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
            v-model="form.start"
            start="08:00"
            step="00:30"
            end="21:30"
            placeholder="几点开始"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-select
            v-model="form.end"
            start="08:30"
            step="00:30"
            end="22:00"
            placeholder="几点结束"
            style="width: 100%"
          />
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
</style>
