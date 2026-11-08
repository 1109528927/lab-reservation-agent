<script setup>
import { nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'
import { askAgentStream, getAgentThreadId, warmupAgent } from '@/utils/agentStream'
import { loadLocalChat, saveLocalChat, scrubChatText } from '@/utils/chatPersist'

defineOptions({ name: 'MobileAgent' })

const input = ref('')
const loading = ref(false)
const degraded = ref(false)
const messages = ref([])
const chatEl = ref(null)

const scrollBottom = async () => {
  await nextTick()
  const el = chatEl.value
  if (!el) return
  const pin = () => {
    el.scrollTop = el.scrollHeight
  }
  pin()
  // keep-alive 切回后布局未稳定，再补两次
  requestAnimationFrame(pin)
  setTimeout(pin, 50)
  setTimeout(pin, 200)
}

watch(
  messages,
  (v) => saveLocalChat(v),
  { deep: true }
)

const welcome = (deg) =>
  deg
    ? '助手降级中，仍可用下方预约/通行码功能。'
    : '你好，我可以帮你查实验室、预约、看预约和通行码。'

const loadStatus = async () => {
  const cached = loadLocalChat()
  if (cached?.length) {
    messages.value = cached
  }

  try {
    const res = await request.get('/api/agent/status')
    degraded.value = !!res.data?.data?.degraded

    // 业务库按用户最近 100 条（重新登录也能看）
    const hist = await request.get('/api/agent/history', { params: { limit: 100 } })
    const items = hist.data?.data?.items || []
    if (items.length) {
      messages.value = items.map((m) => ({
        role: m.role,
        content: scrubChatText(m.content)
      }))
      saveLocalChat(messages.value)
    } else if (!messages.value.length) {
      messages.value = [{ role: 'assistant', content: welcome(degraded.value) }]
    }
    // 固定 thread，便于短期记忆与落库一致
    getAgentThreadId()

    if (!degraded.value) warmupAgent().catch(() => {})
  } catch {
    degraded.value = true
    if (!messages.value.length) {
      messages.value = [{ role: 'assistant', content: '助手暂不可用，请用预约页操作。' }]
    }
  }
  scrollBottom()
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
        reply.content = scrubChatText(full)
        scrollBottom()
      },
      onMeta: (p) => {
        if (p.degraded) degraded.value = true
      }
    })
    if (deg) degraded.value = true
    if (!reply.content) reply.content = '无回复'
    else reply.content = scrubChatText(reply.content)
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '发送失败'))
    reply.content = reply.content || '发送失败，请稍后重试或用表单预约。'
  } finally {
    loading.value = false
    saveLocalChat(messages.value)
    scrollBottom()
  }
}

onMounted(loadStatus)
// 底部 Tab 用 keep-alive，切回助手页时需重新贴底
onActivated(() => {
  scrollBottom()
})
</script>

<template>
  <div class="page">
    <el-alert
      v-if="degraded"
      type="warning"
      :closable="false"
      title="助手降级：主业务仍可用"
      class="alert"
    />
    <div ref="chatEl" class="chat">
      <div class="chat-inner">
        <div v-for="(m, i) in messages" :key="i" class="bubble" :class="m.role">
          {{ m.content }}<span
            v-if="loading && i === messages.length - 1 && m.role === 'assistant'"
            class="cursor"
            >|</span
          >
        </div>
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
.page {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 120px);
}
.alert {
  margin-bottom: 10px;
  flex: 0 0 auto;
}
.chat {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  min-height: 360px;
  max-height: 55vh;
  overflow-y: auto;
  margin-bottom: 10px;
}
.chat-inner {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.composer {
  flex: 0 0 auto;
}
.bubble {
  max-width: 85%;
  padding: 8px 12px;
  border-radius: 10px;
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
