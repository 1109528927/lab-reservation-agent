<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Menu as IconMenu,
  House,
  Calendar,
  Key,
  ChatDotRound,
  SwitchButton,
  Notebook,
  Bell,
  Tools,
  Medal
} from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const route = useRoute()
const pendingCount = ref(0)
const unreadMsg = ref(0)

const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})
const isSchoolAdmin = computed(() => user.value.role === 'admin')
const isTeacher = computed(() => user.value.role === 'teacher')
const roleLabel = computed(() => {
  const m = { admin: '学校管理', teacher: '老师', student: '学生' }
  return m[user.value.role] || user.value.role || '-'
})
const portalLabel = computed(() => {
  if (user.value.role === 'admin') return '管理端'
  if (user.value.role === 'teacher') return '老师端'
  return '用户端'
})

const loadPending = async () => {
  if (!isSchoolAdmin.value) return
  try {
    const res = await request.get('/api/reservations', { params: { status: 'pending' } })
    pendingCount.value = (res.data?.data?.items || []).length
  } catch {
    pendingCount.value = 0
  }
}

const loadUnread = async () => {
  try {
    const res = await request.get('/api/messages/unread-count')
    unreadMsg.value = res.data?.data?.unread || 0
  } catch {
    unreadMsg.value = 0
  }
}

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('userInfo')
  router.push('/login')
}

onMounted(() => {
  loadPending()
  loadUnread()
})
watch(
  () => route.path,
  () => {
    if (isSchoolAdmin.value) loadPending()
    loadUnread()
  }
)
</script>

<template>
  <div>
    <el-container style="min-height: 100vh">
      <el-header
        style="
          display: flex;
          align-items: center;
          border-bottom: 1px solid #ddd;
          background-color: #fff;
        "
      >
        <div
          style="flex: 1; display: flex; align-items: center; font-size: 22px; font-weight: bold"
        >
          <img style="width: 40px" src="@/assets/imgs/logo.png" alt="" />
          <div style="margin-left: 8px">智能实验室预约通行系统</div>
          <el-tag size="small" style="margin-left: 10px" type="info">{{ portalLabel }}</el-tag>
        </div>
        <div style="display: flex; align-items: center; gap: 12px">
          <el-button
            v-if="isSchoolAdmin && pendingCount > 0"
            type="warning"
            plain
            @click="router.push('/manager/reservation')"
          >
            待审 {{ pendingCount }}
          </el-button>
          <el-button text type="success" @click="router.push('/m/home')">移动端</el-button>
          <span>{{ user.username || '用户' }}（{{ roleLabel }}）</span>
          <el-button text type="danger" :icon="SwitchButton" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-container>
        <el-aside width="220px">
          <el-menu router style="height: 100%" :default-active="route.path">
            <el-menu-item v-if="isSchoolAdmin" index="/manager/home">
              <el-icon><icon-menu /></el-icon>
              <span>系统首页</span>
            </el-menu-item>
            <el-menu-item index="/manager/lab">
              <el-icon><House /></el-icon>
              <span>{{ isTeacher ? '实验室预约' : '实验室管理' }}</span>
            </el-menu-item>
            <el-menu-item v-if="isSchoolAdmin" index="/manager/schedule">
              <el-icon><Notebook /></el-icon>
              <span>排课管理</span>
            </el-menu-item>
            <el-menu-item index="/manager/reservation">
              <el-icon><Calendar /></el-icon>
              <span>预约管理</span>
              <span v-if="isSchoolAdmin && pendingCount > 0" class="badge">{{ pendingCount }}</span>
            </el-menu-item>
            <el-menu-item index="/manager/access">
              <el-icon><Key /></el-icon>
              <span>模拟门禁</span>
            </el-menu-item>
            <el-menu-item index="/manager/messages">
              <el-icon><Bell /></el-icon>
              <span>消息中心</span>
              <span v-if="unreadMsg > 0" class="badge">{{ unreadMsg }}</span>
            </el-menu-item>
            <el-menu-item v-if="isSchoolAdmin" index="/manager/repair">
              <el-icon><Tools /></el-icon>
              <span>报修工单</span>
            </el-menu-item>
            <el-menu-item v-if="isSchoolAdmin" index="/manager/credit">
              <el-icon><Medal /></el-icon>
              <span>信用管理</span>
            </el-menu-item>
            <el-menu-item index="/manager/agent">
              <el-icon><ChatDotRound /></el-icon>
              <span>智能助手</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
.badge {
  margin-left: 8px;
  background: #e6a23c;
  color: #fff;
  border-radius: 10px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 18px;
}
</style>
