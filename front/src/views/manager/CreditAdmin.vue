<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const items = ref([])
const minScore = ref(60)
const logs = ref([])
const logUser = ref(null)
const drawer = ref(false)

const load = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/credit/users')
    items.value = res.data?.data?.items || []
    minScore.value = res.data?.data?.min_to_reserve ?? 60
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const showLogs = async (row) => {
  logUser.value = row
  drawer.value = true
  try {
    const res = await request.get(`/api/credit/users/${row.id}/logs`)
    logs.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载流水失败'))
  }
}

const runTick = async () => {
  try {
    const res = await request.post('/api/ops/tick')
    const d = res.data?.data || {}
    ElMessage.success(`扫描完成：爽约 ${d.no_show || 0}，过期提醒 ${d.pass_expire || 0}`)
    await load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '扫描失败'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 8px">
      <h3 style="margin: 0">信用与爽约 · 预约门槛 {{ minScore }} 分</h3>
      <div>
        <el-button type="warning" @click="runTick">扫描爽约/过期提醒</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="items" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户" width="120" />
      <el-table-column prop="employee_no" label="学号/工号" width="140" />
      <el-table-column prop="role" label="角色" width="100" />
      <el-table-column prop="credit_score" label="信用分" width="100" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="primary" @click="showLogs(row)">流水</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer
      v-model="drawer"
      :title="logUser ? `${logUser.username} 信用流水` : '流水'"
      size="40%"
    >
      <el-table :data="logs" border size="small">
        <el-table-column prop="delta" label="变动" width="80" />
        <el-table-column prop="score_after" label="之后" width="80" />
        <el-table-column prop="reason" label="原因" min-width="180" />
        <el-table-column prop="create_at" label="时间" width="170" />
      </el-table>
    </el-drawer>
  </div>
</template>
