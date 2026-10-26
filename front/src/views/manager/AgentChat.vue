<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'
import { askAgentStream, warmupAgent } from '@/utils/agentStream'

const input = ref('')
const loading = ref(false)
const degraded = ref(true)
const statusText = ref('检查助手状态…')
const messages = ref([])
const chatEl = ref(null)

const scrollBottom = async () => {
  await nextTick()
  if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
}

const pushAssistant = (content) => {
  messages.value.push({ role: 'assistant', content })
  scrollBottom()
}

const loadStatus = async () => {
  try {
    const res = await request.get('/api/agent/status')
    const d = res.data?.data || {}
    degraded.value = !!d.degraded
    if (d.degraded) {
      statusText.value =
        '助手当前为降级模式：大模型未就绪。预约管理、模拟门禁可照常演示。'
      pushAssistant(statusText.value)
    } else {
      statusText.value = '助手预热中，稍后再提问会更快出第一个字'
      pushAssistant('你好。我正在准备模型连接，你可以直接提问。')
      warmupAgent()
        .then((d) => {
          statusText.value = d.warm
            ? '助手已预热。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
            : '助手可用。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
        })
        .catch(() => {
          statusText.value = '助手可用。核心 Tool：查实验室 / 预约 / 我的预约 / 通行码'
        })
    }
  } catch {
    degraded.value = true
    statusText.value = '无法连接助手接口；主业务菜单不受影响。'
    pushAssistant(statusText.value)
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
    degraded.value = true
    ElMessage.error(getErrorMessage(e, '助手暂不可用'))
    reply.content = reply.content || '助手调用失败。请改用「预约管理 / 模拟门禁」完成操作。'
  } finally {
    loading.value = false
    scrollBottom()
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="wrap">
    <h2>智能助手</h2>
    <el-alert
      :type="degraded ? 'warning' : 'success'"
      :closable="false"
      :title="statusText"
      description="回答经 LangGraph messages 流式推送；前端按 token 背压出字，不是先拿全文再 setInterval。"
      show-icon
      style="margin-bottom: 12px"
    />
    <div ref="chatEl" class="chat">
      <div v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
        <span class="tag">{{ m.role === 'user' ? '我' : '助手' }}</span>
        <span class="plain">{{ m.content }}<span v-if="loading && i === messages.length - 1 && m.role === 'assistant'" class="cursor">|</span></span>
      </div>
    </div>
    <div class="composer">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        placeholder="例如：明天下午有哪些实验室可以预约？"
        @keydown.ctrl.enter="send"
      />
      <el-button type="primary" :loading="loading" style="margin-top: 8px" @click="send">
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat {
  background: #fff;
  border: 1px solid #ebeef5;
  min-height: 320px;
  max-height: 480px;
  overflow-y: auto;
  padding: 12px;
  margin-bottom: 12px;
}
.row {
  margin-bottom: 10px;
  line-height: 1.5;
}
.row.user {
  text-align: right;
}
.tag {
  display: inline-block;
  margin-right: 6px;
  color: #909399;
  font-size: 12px;
}
.plain {
  white-space: pre-wrap;
  word-break: break-word;
}
.cursor {
  display: inline-block;
  margin-left: 1px;
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
.composer {
  max-width: 720px;
}
</style>
