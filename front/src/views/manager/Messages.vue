<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const items = ref([])
const unread = ref(0)

const load = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/messages')
    items.value = res.data?.data?.items || []
    unread.value = res.data?.data?.unread || 0
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const markAll = async () => {
  await request.post('/api/messages/read-all')
  ElMessage.success('已全部已读')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px">
      <h3 style="margin: 0">消息中心 · 未读 {{ unread }}</h3>
      <div>
        <el-button @click="markAll">全部已读</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="items" border stripe>
      <el-table-column prop="msg_type" label="类型" width="120" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
      <el-table-column label="已读" width="80">
        <template #default="{ row }">{{ row.is_read ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="create_at" label="时间" width="170" />
    </el-table>
  </div>
</template>
