<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})
const isAdmin = computed(() => user.value.role === 'admin')
const isTeacher = computed(() => user.value.role === 'teacher')
const stats = ref(null)

onMounted(async () => {
  if (isTeacher.value) {
    router.replace('/manager/lab')
    return
  }
  if (!isAdmin.value) return
  try {
    const res = await request.get('/api/stats/overview')
    stats.value = res.data?.data || null
  } catch {
    stats.value = null
  }
})
</script>

<template>
  <div class="home">
    <h2>系统首页</h2>
    <p class="sub">
      欢迎，{{ user.username || '用户' }}（{{ user.role || '-' }} / {{ user.employee_no || '-' }}）
    </p>
    <el-alert
      type="success"
      :closable="false"
      title="学校管理：排课 / 审预约 / 维护实验室；老师直接预约；学生预约待审"
      description="软件主线：预约 → 签须知 → 领码 → 模拟门核验；助手可降级"
      show-icon
    />

    <el-row v-if="stats" :gutter="16" class="cards">
      <el-col :span="4">
        <el-card shadow="never" class="click" @click="router.push('/manager/lab')">
          <div class="t">实验室</div>
          {{ stats.labs }}
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never"><div class="t">用户</div>{{ stats.users }}</el-card>
      </el-col>
      <el-col :span="4">
        <el-card
          shadow="never"
          class="click warn"
          @click="router.push('/manager/reservation')"
        >
          <div class="t">待审</div>
          {{ stats.reservations_pending }}
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never"><div class="t">有效预约</div>{{ stats.reservations_active }}</el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never"><div class="t">放行</div>{{ stats.access_allow }}</el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never"><div class="t">拒绝</div>{{ stats.access_deny }}</el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="cards">
      <el-col :span="6">
        <el-card shadow="never" class="click" @click="router.push('/manager/schedule')">
          <div class="t">排课</div>
          Excel 导入 / 月历
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="click" @click="router.push('/manager/reservation')">
          <div class="t">审批</div>
          处理学生待审预约
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="click" @click="router.push('/manager/access')">
          <div class="t">门禁</div>
          模拟扫码核验
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="t">B1</div>ESP32 + GM65（后续）</el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.home h2 {
  margin-bottom: 8px;
}
.sub {
  color: #606266;
  margin-bottom: 16px;
}
.cards {
  margin-top: 20px;
}
.t {
  font-weight: 700;
  margin-bottom: 6px;
}
.click {
  cursor: pointer;
}
.click:hover {
  outline: 1px solid #409eff;
}
.warn .t {
  color: #e6a23c;
}
</style>
