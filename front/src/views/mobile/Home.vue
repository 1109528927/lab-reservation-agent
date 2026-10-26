<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const labs = ref([])
const mine = ref([])
const keyword = ref('')

const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})

const filteredLabs = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return labs.value
  return labs.value.filter((l) =>
    `${l.name || ''} ${l.location || ''}`.toLowerCase().includes(kw)
  )
})

const goReserve = (labId) => {
  router.push({ path: '/m/reserve', query: labId ? { lab_id: String(labId) } : {} })
}

onMounted(async () => {
  try {
    const [l, r] = await Promise.all([
      request.get('/api/labs', { params: { only_open: true } }),
      request.get('/api/reservations/mine')
    ])
    labs.value = l.data?.data?.items || []
    mine.value = (r.data?.data?.items || []).slice(0, 3)
  } catch {
    /* ignore */
  }
})
</script>

<template>
  <div class="page">
    <div class="hero">
      <div class="hi">你好，{{ user.username || '同学' }}</div>
      <div class="tip">预约实验室 · 领取通行码 · 扫码通行</div>
    </div>

    <div class="grid">
      <button class="cell" type="button" @click="goReserve()">去预约</button>
      <button class="cell" type="button" @click="router.push('/m/pass')">我的通行码</button>
      <button class="cell" type="button" @click="router.push('/m/agent')">智能助手</button>
      <button class="cell" type="button" @click="router.push('/m/scan')">模拟扫码</button>
    </div>

    <div class="card">
      <div class="card-t">开放实验室</div>
      <el-input
        v-model="keyword"
        clearable
        placeholder="筛选名称/位置"
        size="small"
        style="margin-bottom: 8px"
      />
      <div v-if="!filteredLabs.length" class="empty">暂无</div>
      <div v-for="l in filteredLabs" :key="l.id" class="row">
        <div>
          <div class="name">{{ l.name }}</div>
          <div class="meta">{{ l.location || '位置待定' }} · 容量 {{ l.capacity }}</div>
        </div>
        <div class="right">
          <span class="tag">{{ user.role === 'teacher' ? '老师直通' : '需管理员审' }}</span>
          <el-button size="small" type="success" @click="goReserve(l.id)">预约</el-button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-t">最近预约</div>
      <div v-if="!mine.length" class="empty">还没有预约</div>
      <div v-for="r in mine" :key="r.id" class="row">
        <div>
          <div class="name">#{{ r.id }} · {{ r.status }}</div>
          <div class="meta">{{ r.start_time }} ~ {{ r.end_time }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero {
  background: linear-gradient(135deg, #07c160, #06ad56);
  color: #fff;
  border-radius: 12px;
  padding: 18px 16px;
  margin-bottom: 12px;
}
.hi {
  font-size: 18px;
  font-weight: 600;
}
.tip {
  margin-top: 6px;
  font-size: 13px;
  opacity: 0.92;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.cell {
  border: 0;
  background: #fff;
  border-radius: 10px;
  padding: 16px 12px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.card-t {
  font-weight: 600;
  margin-bottom: 8px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid #f0f0f0;
}
.name {
  font-size: 14px;
}
.meta {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}
.right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.tag {
  font-size: 11px;
  color: #07c160;
  background: #e8f8ef;
  padding: 2px 8px;
  border-radius: 999px;
}
.empty {
  color: #999;
  font-size: 13px;
  padding: 8px 0;
}
</style>
