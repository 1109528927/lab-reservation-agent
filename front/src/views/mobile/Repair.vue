<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const labs = ref([])
const items = ref([])
const loading = ref(false)
const dialog = ref(false)
const form = reactive({ lab_id: null, title: '', description: '' })

const statusLabel = (s) =>
  ({ pending: '待处理', processing: '处理中', done: '已完成' }[s] || s)

const loadLabs = async () => {
  const res = await request.get('/api/labs', { params: { only_open: false } })
  labs.value = res.data?.data?.items || []
}

const loadMine = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/repairs/mine')
    items.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const labName = (id) => labs.value.find((x) => x.id === id)?.name || id

const submit = async () => {
  if (!form.lab_id || !form.title.trim()) {
    ElMessage.warning('请选择实验室并填写标题')
    return
  }
  try {
    await request.post('/api/repairs', {
      lab_id: form.lab_id,
      title: form.title.trim(),
      description: form.description.trim() || null
    })
    ElMessage.success('报修已提交')
    dialog.value = false
    form.title = ''
    form.description = ''
    await loadMine()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '提交失败'))
  }
}

onMounted(async () => {
  await loadLabs()
  await loadMine()
})
</script>

<template>
  <div class="page">
    <button type="button" class="btn" @click="dialog = true">新建报修</button>
    <div v-loading="loading">
      <div v-if="!items.length" class="empty">暂无报修工单</div>
      <div v-for="r in items" :key="r.id" class="card">
        <div class="top">
          <strong>#{{ r.id }} {{ r.title }}</strong>
          <el-tag size="small">{{ statusLabel(r.status) }}</el-tag>
        </div>
        <div class="meta">实验室：{{ labName(r.lab_id) }}</div>
        <div v-if="r.description" class="meta">{{ r.description }}</div>
        <div v-if="r.admin_reply" class="reply">管理员：{{ r.admin_reply }}</div>
      </div>
    </div>

    <el-dialog v-model="dialog" title="提交报修" width="90%">
      <el-form label-position="top">
        <el-form-item label="实验室">
          <el-select v-model="form.lab_id" placeholder="选择实验室" style="width: 100%">
            <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="120" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="3" maxlength="500" />
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
.btn {
  width: 100%;
  border: 0;
  background: #07c160;
  color: #fff;
  padding: 12px;
  border-radius: 8px;
  font-size: 15px;
  margin-bottom: 12px;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #999;
  padding: 40px 0;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 10px;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.meta {
  margin-top: 6px;
  font-size: 13px;
  color: #666;
}
.reply {
  margin-top: 8px;
  font-size: 13px;
  color: #07c160;
  background: #f0fff6;
  padding: 8px;
  border-radius: 6px;
}
</style>
