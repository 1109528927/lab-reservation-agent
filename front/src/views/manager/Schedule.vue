<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const labs = ref([])
const blocks = ref([])
const labFilter = ref(null)
const month = ref(new Date())
const dayDrawer = ref(false)
const selectedDay = ref('')
const importDrawer = ref(false)
const preview = ref(null)
const uploading = ref(false)
const fileList = ref([])

const form = reactive({
  lab_id: null,
  title: '',
  range: [],
  note: ''
})

const labName = (id) => labs.value.find((x) => x.id === id)?.name || `#${id}`

const monthRange = computed(() => {
  const d = month.value instanceof Date ? month.value : new Date(month.value)
  const y = d.getFullYear()
  const m = d.getMonth()
  const from = new Date(y, m, 1, 0, 0, 0)
  const to = new Date(y, m + 1, 1, 0, 0, 0)
  const fmt = (x) => {
    const p = (n) => String(n).padStart(2, '0')
    return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}:${p(x.getSeconds())}`
  }
  return { from: fmt(from), to: fmt(to) }
})

const byDate = computed(() => {
  const map = {}
  for (const b of blocks.value) {
    const key = String(b.start_time).slice(0, 10)
    if (!map[key]) map[key] = []
    map[key].push(b)
  }
  return map
})

const dayBlocks = computed(() => byDate.value[selectedDay.value] || [])

const loadLabs = async () => {
  const res = await request.get('/api/labs')
  labs.value = res.data?.data?.items || []
}

const loadBlocks = async () => {
  loading.value = true
  try {
    const params = {
      from: monthRange.value.from,
      to: monthRange.value.to
    }
    if (labFilter.value) params.lab_id = labFilter.value
    const res = await request.get('/api/schedule/blocks', { params })
    blocks.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载排课失败'))
  } finally {
    loading.value = false
  }
}

const openDay = (day) => {
  // el-calendar 可能传 Date 或 string
  const d = day instanceof Date ? day : new Date(day)
  const p = (n) => String(n).padStart(2, '0')
  selectedDay.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  form.lab_id = labFilter.value || labs.value[0]?.id || null
  form.title = ''
  form.range = []
  form.note = ''
  dayDrawer.value = true
}

const addBlock = async () => {
  if (!form.lab_id || !form.title?.trim() || !form.range?.length || form.range.length < 2) {
    ElMessage.warning('请填写实验室、课程名与时间')
    return
  }
  try {
    await request.post('/api/schedule/blocks', {
      lab_id: form.lab_id,
      title: form.title.trim(),
      start_time: form.range[0],
      end_time: form.range[1],
      note: form.note || undefined
    })
    ElMessage.success('已补录')
    form.title = ''
    form.range = []
    form.note = ''
    loadBlocks()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '添加失败'))
  }
}

const removeBlock = async (id) => {
  try {
    await ElMessageBox.confirm('删除该排课占档？', '确认', { type: 'warning' })
    await request.delete(`/api/schedule/blocks/${id}`)
    ElMessage.success('已删除')
    loadBlocks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(getErrorMessage(e, '删除失败'))
  }
}

const downloadTemplate = async () => {
  try {
    const res = await request.get('/api/schedule/template.xlsx', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'lab_schedule_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '下载失败'))
  }
}

const doImport = async (commit) => {
  const raw = fileList.value[0]?.raw
  if (!raw) {
    ElMessage.warning('请先选择 Excel 文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', raw)
    const res = await request.post(`/api/schedule/import?commit=${commit}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    preview.value = res.data?.data || null
    ElMessage.success(res.data?.message || (commit ? '已导入' : '预览完成'))
    if (commit) {
      importDrawer.value = false
      fileList.value = []
      preview.value = null
      loadBlocks()
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '导入失败'))
  } finally {
    uploading.value = false
  }
}

watch([month, labFilter], () => loadBlocks())

onMounted(async () => {
  try {
    await loadLabs()
    await loadBlocks()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '初始化失败'))
  }
})
</script>

<template>
  <div v-loading="loading">
    <div class="bar">
      <h2>排课管理</h2>
      <div class="ops">
        <el-select
          v-model="labFilter"
          clearable
          placeholder="全部实验室"
          style="width: 180px"
        >
          <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
        </el-select>
        <el-date-picker v-model="month" type="month" placeholder="月份" />
        <el-button @click="loadBlocks">刷新</el-button>
        <el-button @click="downloadTemplate">下载模板</el-button>
        <el-button type="primary" @click="importDrawer = true">导入 Excel</el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="大批量请用「周循环」Excel 一行铺整学期；日历上点某日仅做临时调课。"
      style="margin-bottom: 12px"
    />

    <el-calendar v-model="month">
      <template #date-cell="{ data }">
        <div class="cell" @click.stop="openDay(data.date)">
          <div class="day">{{ data.day.split('-').slice(2).join('-') }}</div>
          <div
            v-for="b in (byDate[data.day] || []).slice(0, 3)"
            :key="b.id"
            class="chip"
            :title="`${labName(b.lab_id)} ${b.title}`"
          >
            {{ String(b.start_time).slice(11, 16) }} {{ b.title }}
          </div>
          <div v-if="(byDate[data.day] || []).length > 3" class="more">
            +{{ (byDate[data.day] || []).length - 3 }}
          </div>
        </div>
      </template>
    </el-calendar>

    <el-drawer v-model="dayDrawer" :title="`排课 · ${selectedDay}`" size="420px">
      <div v-if="!dayBlocks.length" class="empty">当天暂无排课</div>
      <div v-for="b in dayBlocks" :key="b.id" class="block-row">
        <div>
          <div class="t">{{ b.title }} · {{ labName(b.lab_id) }}</div>
          <div class="m">{{ b.start_time }} ~ {{ b.end_time }}</div>
          <div v-if="b.note" class="m">{{ b.note }}</div>
        </div>
        <el-button link type="danger" @click="removeBlock(b.id)">删除</el-button>
      </div>

      <el-divider>临时补录</el-divider>
      <el-form label-width="80px">
        <el-form-item label="实验室">
          <el-select v-model="form.lab_id" style="width: 100%">
            <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="课程名">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="时段">
          <el-date-picker
            v-model="form.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" />
        </el-form-item>
        <el-button type="primary" style="width: 100%" @click="addBlock">添加</el-button>
      </el-form>
    </el-drawer>

    <el-drawer v-model="importDrawer" title="导入排课 Excel" size="480px">
      <p class="hint">先下载模板，填「周循环」表后上传预览，确认无误再写入。</p>
      <el-upload
        v-model:file-list="fileList"
        :auto-upload="false"
        :limit="1"
        accept=".xlsx,.xls"
      >
        <el-button>选择文件</el-button>
      </el-upload>
      <div class="import-ops">
        <el-button :loading="uploading" @click="doImport(false)">预览</el-button>
        <el-button type="primary" :loading="uploading" @click="doImport(true)">
          确认导入
        </el-button>
      </div>
      <div v-if="preview" class="preview">
        <p>
          有效行 {{ preview.ok_rows }} · 将写入
          <b>{{ preview.block_count }}</b> 条
          <span v-if="preview.skipped_count">
            · 跳过重叠 {{ preview.skipped_count }} 条
          </span>
        </p>
        <div v-if="preview.errors?.length">
          <p class="err">错误 {{ preview.errors.length }} 条：</p>
          <ul>
            <li v-for="(e, i) in preview.errors.slice(0, 10)" :key="i">
              {{ e.sheet }} 第{{ e.row }}行：{{ e.error }}
            </li>
          </ul>
        </div>
        <div v-if="preview.skipped?.length">
          <p class="skip">重叠跳过样例：</p>
          <ul>
            <li v-for="(s, i) in preview.skipped.slice(0, 8)" :key="i">
              {{ s.title }} {{ s.start_time }} — {{ s.reason }}
            </li>
          </ul>
        </div>
        <div v-if="preview.sample?.length">
          <p>将写入样例：</p>
          <ul>
            <li v-for="(s, i) in preview.sample" :key="i">
              {{ s.title }} {{ s.start_time }} ~ {{ s.end_time }}
            </li>
          </ul>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.cell {
  min-height: 72px;
  cursor: pointer;
  padding: 2px;
}
.day {
  font-weight: 600;
  margin-bottom: 2px;
}
.chip {
  font-size: 11px;
  line-height: 1.3;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 2px;
  padding: 1px 4px;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.more {
  font-size: 11px;
  color: #909399;
}
.block-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.t {
  font-weight: 600;
}
.m {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}
.empty {
  color: #999;
  margin-bottom: 12px;
}
.hint {
  color: #666;
  font-size: 13px;
  margin-bottom: 12px;
}
.import-ops {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.preview {
  margin-top: 16px;
  font-size: 13px;
}
.err {
  color: #f56c6c;
}
.skip {
  color: #e6a23c;
}
</style>
