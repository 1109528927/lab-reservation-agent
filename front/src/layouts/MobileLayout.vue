<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { House, Calendar, Key, ChatDotRound, User } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})

const tabs = [
  { path: '/m/home', label: '首页', icon: House },
  { path: '/m/reserve', label: '预约', icon: Calendar },
  { path: '/m/pass', label: '通行码', icon: Key },
  { path: '/m/agent', label: '助手', icon: ChatDotRound },
  { path: '/m/mine', label: '我的', icon: User }
]

const active = computed(() => route.path)
</script>

<template>
  <div class="mp-shell">
    <header class="mp-nav">
      <div class="mp-nav-title">实验室预约通行</div>
      <div class="mp-nav-sub">{{ user.username || '未登录' }}</div>
    </header>
    <main class="mp-main">
      <router-view />
    </main>
    <nav class="mp-tabbar">
      <button
        v-for="t in tabs"
        :key="t.path"
        type="button"
        class="mp-tab"
        :class="{ on: active === t.path || active.startsWith(t.path + '/') }"
        @click="router.push(t.path)"
      >
        <el-icon :size="20"><component :is="t.icon" /></el-icon>
        <span>{{ t.label }}</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.mp-shell {
  --mp-green: #07c160;
  --mp-bg: #f7f7f7;
  max-width: 430px;
  margin: 0 auto;
  min-height: 100vh;
  background: var(--mp-bg);
  display: flex;
  flex-direction: column;
  position: relative;
  box-shadow: 0 0 24px rgba(0, 0, 0, 0.06);
}
.mp-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #fff;
  padding: 12px 16px 10px;
  border-bottom: 1px solid #eee;
}
.mp-nav-title {
  font-size: 17px;
  font-weight: 600;
}
.mp-nav-sub {
  margin-top: 2px;
  font-size: 12px;
  color: #888;
}
.mp-main {
  flex: 1;
  padding: 12px 12px 72px;
  overflow-y: auto;
}
.mp-tabbar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: 100%;
  max-width: 430px;
  height: 56px;
  background: #fff;
  border-top: 1px solid #e5e5e5;
  display: flex;
  z-index: 20;
}
.mp-tab {
  flex: 1;
  border: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 11px;
  color: #666;
  cursor: pointer;
}
.mp-tab.on {
  color: var(--mp-green);
}
</style>
