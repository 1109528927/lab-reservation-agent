<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const items = ref([])
const unread = ref(0)

const typeLabel = (t) =>
  ({
    approve: '审批通过',
    reject: '审批驳回',
    pass_expire: '码将过期',
    no_show: '爽约',
    repair: '报修',
    system: '系统'
  }[t] || t)

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

const markOne = async (row) => {
  if (row.is_read) return
  try {
    await request.post(`/api/messages/${row.id}/read`)
    row.is_read = 1
    unread.value = Math.max(0, unread.value - 1)
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '标记失败'))
  }
}

const markAll = async () => {
  try {
    await request.post('/api/messages/read-all')
    ElMessage.success('已全部标为已读')
    await load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '操作失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="bar">
      <span>消息与待办 · 未读 {{ unread }}</span>
      <button type="button" class="link" @click="markAll">全部已读</button>
    </div>
    <div v-loading="loading">
      <div v-if="!items.length" class="empty">暂无消息</div>
      <div
        v-for="m in items"
        :key="m.id"
        class="card"
        :class="{ unread: !m.is_read }"
        @click="markOne(m)"
      >
        <div class="top">
          <el-tag size="small" :type="m.is_read ? 'info' : 'warning'">
            {{ typeLabel(m.msg_type) }}
          </el-tag>
          <span class="time">{{ m.create_at }}</span>
        </div>
        <div class="title">{{ m.title }}</div>
        <div class="body">{{ m.content }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
}
.link {
  border: 0;
  background: transparent;
  color: #07c160;
  font-size: 13px;
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
  border-left: 3px solid transparent;
}
.card.unread {
  border-left-color: #e6a23c;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.time {
  font-size: 11px;
  color: #aaa;
}
.title {
  margin-top: 6px;
  font-weight: 600;
  font-size: 14px;
}
.body {
  margin-top: 4px;
  font-size: 13px;
  color: #666;
  line-height: 1.45;
}
</style>
