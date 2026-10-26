<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'
import { askAgentStream, warmupAgent } from '@/utils/agentStream'

const input = ref('')
const loading = ref(false)
const degraded = ref(false)
const messages = ref([])
const chatEl = ref(null)

const scrollBottom = async () => {
  await nextTick()
  if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
}

const loadStatus = async () => {
  try {
    const res = await request.get('/api/agent/status')
    degraded.value = !!res.data?.data?.degraded
    messages.value = [
      {
        role: 'assistant',
        content: degraded.value
          ? '助手降级中，仍可用下方预约/通行码功能。'
          : '你好，我可以帮你查实验室、预约、看预约和通行码。'
      }
    ]
    if (!degraded.value) warmupAgent().catch(() => {})
  } catch {
    degraded.value = true
    messages.value = [{ role: 'assistant', content: '助手暂不可用，请用预约页操作。' }]
  }
}

const send = async () => {
  const text = input.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  messages.value.push({ role: 'assistant', content: '' })
  const reply = messages.value[messages.value.length - 1]
  scrollBottom()
  try {
    const { degraded: deg } = await askAgentStream(text, {
      onDelta: (full) => {
        reply.content = full
        scrollBottom()
      },
      onMeta: (p) => {
        if (p.degraded) degraded.value = true
      }
    })
    if (deg) degraded.value = true
    if (!reply.content) reply.content = '无回复'
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '发送失败'))
    reply.content = reply.content || '发送失败，请稍后重试或用表单预约。'
  } finally {
    loading.value = false
    scrollBottom()
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="page">
    <el-alert
      v-if="degraded"
      type="warning"
      :closable="false"
      title="助手降级：主业务仍可用"
      style="margin-bottom: 10px"
    />
    <div ref="chatEl" class="chat">
      <div v-for="(m, i) in messages" :key="i" class="bubble" :class="m.role">
        {{ m.content }}<span
          v-if="loading && i === messages.length - 1 && m.role === 'assistant'"
          class="cursor"
          >|</span
        >
      </div>
    </div>
    <div class="composer">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        placeholder="例如：有哪些实验室可以预约？"
      />
      <el-button type="success" :loading="loading" style="width: 100%; margin-top: 8px" @click="send">
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  min-height: 360px;
  max-height: 55vh;
  overflow-y: auto;
  margin-bottom: 10px;
}
.bubble {
  max-width: 85%;
  padding: 8px 12px;
  border-radius: 10px;
  margin-bottom: 8px;
  line-height: 1.5;
  font-size: 14px;
  white-space: pre-wrap;
}
.bubble.assistant {
  background: #f2f2f2;
  color: #333;
}
.bubble.user {
  background: #07c160;
  color: #fff;
  margin-left: auto;
}
.cursor {
  color: #07c160;
  font-weight: bold;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  51%,
  100% {
    opacity: 0;
  }
}
</style>
