<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const credit = ref(null)
const unread = ref(0)
const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})

const roleLabel = computed(() => {
  const m = { admin: '学校管理', teacher: '老师', student: '学生' }
  return m[user.value.role] || user.value.role || '-'
})
const canDesktop = computed(() => ['admin', 'teacher'].includes(user.value.role))

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('userInfo')
  ElMessage.success('已退出')
  router.push('/login')
}

const goManager = () => {
  if (user.value.role === 'teacher') router.push('/manager/lab')
  else router.push('/manager/home')
}

const refreshMe = async () => {
  try {
    const [c, m, u] = await Promise.all([
      request.get('/api/credit/me'),
      request.get('/api/messages/unread-count'),
      request.get('/api/user/me')
    ])
    credit.value = c.data?.data || null
    unread.value = m.data?.data?.unread || 0
    if (u.data?.data) {
      localStorage.setItem('userInfo', JSON.stringify(u.data.data))
    }
  } catch {
    /* ignore */
  }
}

onMounted(refreshMe)
</script>

<template>
  <div class="page">
    <div class="card profile">
      <div class="name">{{ user.username || '-' }}</div>
      <div class="meta">学号/工号：{{ user.employee_no || '-' }}</div>
      <div class="meta">角色：{{ roleLabel }}</div>
      <div class="meta">
        信用分：{{ credit?.credit_score ?? user.credit_score ?? '-' }}
        <span v-if="credit" class="tip-inline">
          · 低于 {{ credit.min_to_reserve }} 分不可预约
        </span>
      </div>
      <div v-if="user.role === 'student'" class="meta tip">预约需学校管理员审核</div>
      <div v-else-if="user.role === 'teacher'" class="meta tip">预约直接通过，无需审核</div>
    </div>

    <div class="card links">
      <button type="button" class="link" @click="router.push('/m/messages')">
        消息与待办{{ unread > 0 ? `（未读 ${unread}）` : '' }}
      </button>
      <button type="button" class="link" @click="router.push('/m/repair')">报修工单</button>
      <button v-if="canDesktop" type="button" class="link" @click="goManager">
        {{ user.role === 'teacher' ? '进入老师端（桌面）' : '进入管理端（桌面后台）' }}
      </button>
      <button type="button" class="link danger" @click="logout">退出登录</button>
    </div>

    <p class="foot">
      学生主界面为小程序态 H5；老师/管理员用桌面端。后续可迁微信小程序，接口不变。
    </p>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}
.profile .name {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}
.meta {
  font-size: 13px;
  color: #666;
  margin-top: 2px;
}
.meta.tip {
  color: #07c160;
  margin-top: 8px;
}
.tip-inline {
  color: #999;
  font-size: 12px;
}

.links {
  padding: 0;
  overflow: hidden;
}
.link {
  width: 100%;
  border: 0;
  background: #fff;
  text-align: left;
  padding: 14px 16px;
  font-size: 14px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
}
.link.danger {
  color: #e54d42;
}
.foot {
  font-size: 12px;
  color: #999;
  line-height: 1.5;
  padding: 0 4px;
}
</style>
