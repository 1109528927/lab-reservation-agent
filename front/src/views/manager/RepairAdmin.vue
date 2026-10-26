<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const items = ref([])
const labs = ref([])
const dialog = ref(false)
const current = ref(null)
const form = reactive({ status: 'processing', admin_reply: '' })

const statusLabel = (s) =>
  ({ pending: '待处理', processing: '处理中', done: '已完成' }[s] || s)
const labName = (id) => labs.value.find((x) => x.id === id)?.name || id

const load = async () => {
  loading.value = true
  try {
    const [r1, r2] = await Promise.all([
      request.get('/api/repairs'),
      request.get('/api/labs', { params: { only_open: false } })
    ])
    items.value = r1.data?.data?.items || []
    labs.value = r2.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const open = (row) => {
  current.value = row
  form.status = row.status === 'pending' ? 'processing' : row.status
  form.admin_reply = row.admin_reply || ''
  dialog.value = true
}

const save = async () => {
  try {
    await request.post(`/api/repairs/${current.value.id}/update`, {
      status: form.status,
      admin_reply: form.admin_reply || null
    })
    ElMessage.success('已更新')
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '更新失败'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px">
      <h3 style="margin: 0">报修工单</h3>
      <el-button @click="load">刷新</el-button>
    </div>
    <el-table v-loading="loading" :data="items" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="实验室" min-width="120">
        <template #default="{ row }">{{ labName(row.lab_id) }}</template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">{{ statusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column prop="admin_reply" label="回复" min-width="140" show-overflow-tooltip />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">处理</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="处理工单" width="480px">
      <el-form label-width="80px">
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="回复">
          <el-input v-model="form.admin_reply" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
