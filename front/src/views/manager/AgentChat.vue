<script setup>
import { nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'
import { askAgentStream, getAgentThreadId, warmupAgent } from '@/utils/agentStream'
import { loadLocalChat, saveLocalChat, scrubChatText } from '@/utils/chatPersist'

defineOptions({ name: 'ManagerAgent' })

const input = ref('')
const loading = ref(false)
const degraded = ref(true)
const statusText = ref('检查助手状态…')
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
  requestAnimationFrame(pin)
  setTimeout(pin, 50)
  setTimeout(pin, 200)
}

watch(
  messages,
  (v) => saveLocalChat(v),
  { deep: true }
)

const loadStatus = async () => {
  const cached = loadLocalChat()
  if (cached?.length) messages.value = cached

  try {
    const res = await request.get('/api/agent/status')
    const d = res.data?.data || {}
    degraded.value = !!d.degraded

    getAgentThreadId()
    const hist = await request.get('/api/agent/history', { params: { limit: 100 } })
    const items = hist.data?.data?.items || []
    if (items.length) {
      messages.value = items.map((m) => ({
        role: m.role,
        content: scrubChatText(m.content)
      }))
      saveLocalChat(messages.value)
      statusText.value = degraded.value
        ? '助手降级中；主业务菜单仍可用。'
        : `已加载最近 ${items.length} 条聊天记录`
    } else if (!messages.value.length) {
      if (d.degraded) {
        statusText.value =
          '助手当前为降级模式：大模型未就绪。预约管理、模拟门禁可照常演示。'
        messages.value = [{ role: 'assistant', content: statusText.value }]
      } else {
        statusText.value = '助手预热中，稍后再提问会更快出第一个字'
        messages.value = [{ role: 'assistant', content: '你好。我正在准备模型连接，你可以直接提问。' }]
        warmupAgent()
          .then((w) => {
            statusText.value = w.warm
              ? '助手已预热。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
              : '助手可用。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
          })
          .catch(() => {
            statusText.value = '助手可用。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
          })
      }
    } else if (!d.degraded) {
      warmupAgent().catch(() => {})
      statusText.value = '已恢复本会话聊天记录'
    }
  } catch {
    degraded.value = true
    statusText.value = '无法连接助手接口；主业务菜单不受影响。'
    if (!messages.value.length) {
      messages.value = [{ role: 'assistant', content: statusText.value }]
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
    degraded.value = true
    ElMessage.error(getErrorMessage(e, '助手暂不可用'))
    reply.content = reply.content || '助手调用失败。请改用「预约管理 / 模拟门禁」完成操作。'
  } finally {
    loading.value = false
    saveLocalChat(messages.value)
    scrollBottom()
  }
}

onMounted(loadStatus)
onActivated(() => {
  scrollBottom()
})
</script>

<template>
  <div class="wrap">
    <h2>智能助手</h2>
    <el-alert
      :type="degraded ? 'warning' : 'success'"
      :closable="false"
      :title="statusText"
      description="回答经 LangGraph messages 流式推送；前端按 token 背压出字，不是先拿全文再 setInterval。"
      style="margin-bottom: 12px"
    />
    <div ref="chatEl" class="chat">
      <div class="chat-inner">
        <div v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
          <span class="tag">{{ m.role === 'user' ? '我' : '助手' }}</span>
          <span class="plain"
            >{{ m.content
            }}<span
              v-if="loading && i === messages.length - 1 && m.role === 'assistant'"
              class="cursor"
              >|</span
            ></span
          >
        </div>
      </div>
    </div>
    <el-input
      v-model="input"
      type="textarea"
      :rows="3"
      placeholder="例如：明天下午有哪些实验室可以预约？"
    />
    <el-button type="primary" :loading="loading" style="margin-top: 8px" @click="send">
      发送
    </el-button>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 860px;
}
.chat {
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  min-height: 320px;
  max-height: 52vh;
  overflow-y: auto;
  margin-bottom: 12px;
}
.chat-inner {
  margin-top: auto;
  width: 100%;
}
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  line-height: 1.55;
}
.row.user .plain {
  background: #ecf5ff;
}
.tag {
  flex: 0 0 36px;
  color: #909399;
  font-size: 13px;
}
.plain {
  flex: 1;
  white-space: pre-wrap;
  background: #fff;
  border-radius: 6px;
  padding: 8px 10px;
  border: 1px solid #ebeef5;
}
.cursor {
  color: #409eff;
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
