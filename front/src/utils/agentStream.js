/**
 * 助手 SSE：token 进队列，渲染层按字弹出（加快演示节奏）。
 * 上游一次吐整段时也不会整块贴上；句末标点略停。
 */

const CHAR_MS = 8
const PUNCT_MS = 28
const CHARS_PER_TICK = 2

function createCharQueue(onFrame) {
  const queue = []
  let timer = null
  let text = ''
  let resolveIdle = null

  const notifyIdle = () => {
    if (resolveIdle) {
      resolveIdle()
      resolveIdle = null
    }
  }

  const step = () => {
    timer = null
    if (!queue.length) {
      onFrame(text, true)
      notifyIdle()
      return
    }
    let pause = CHAR_MS
    let n = Math.min(CHARS_PER_TICK, queue.length)
    let chunk = ''
    for (let i = 0; i < n; i++) {
      const ch = queue.shift()
      chunk += ch
      if ('。！？!?；;'.includes(ch)) {
        pause = PUNCT_MS
        break
      }
    }
    text += chunk
    onFrame(text, false)
    timer = setTimeout(step, pause)
  }

  return {
    enqueue(piece) {
      if (!piece) return
      for (const ch of piece) queue.push(ch)
      if (!timer) timer = setTimeout(step, CHAR_MS)
    },
    /** 用整段最终稿替换（避免「正在办理…」与正文拼接） */
    replace(piece) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      queue.length = 0
      text = ''
      notifyIdle()
      if (!piece) {
        onFrame('', true)
        return
      }
      for (const ch of piece) queue.push(ch)
      timer = setTimeout(step, CHAR_MS)
    },
    setInstant(piece) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      queue.length = 0
      text = piece || ''
      onFrame(text, true)
      notifyIdle()
    },
    getText: () => text,
    whenIdle() {
      if (!timer && !queue.length) return Promise.resolve()
      return new Promise((resolve) => {
        resolveIdle = resolve
      })
    }
  }
}

/**
 * @param {string} message
 * @param {{ onDelta: (fullText: string, idle: boolean) => void, onMeta?: (meta: object) => void }} handlers
 */
/** 每用户固定线程，跨登录复用（聊天落库 + MemorySaver 同 thread）。 */
export function getAgentThreadId() {
  let uid = 'anon'
  try {
    uid = JSON.parse(localStorage.getItem('userInfo') || '{}').id || 'anon'
  } catch {
    /* ignore */
  }
  const key = `agent_thread_id:u${uid}`
  let id = localStorage.getItem(key)
  if (!id) {
    id = 'main'
    localStorage.setItem(key, id)
  }
  return id
}

/** 进入助手页时调用，不阻塞输入。超时放宽，避免全局 10 秒把预热掐断。 */
export function warmupAgent() {
  const token = localStorage.getItem('token') || ''
  return fetch('/api/agent/warmup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : ''
    },
    body: '{}'
  }).then(async (res) => {
    if (!res.ok) return { warm: false }
    const body = await res.json().catch(() => ({}))
    return body.data || { warm: false }
  })
}

export async function askAgentStream(message, handlers = {}) {
  const { onDelta, onMeta, threadId } = handlers
  const token = localStorage.getItem('token') || ''
  const tid = threadId || getAgentThreadId()
  const ctrl = new AbortController()
  const watchdog = setTimeout(() => ctrl.abort(), 100000)

  let res
  try {
    res = await fetch('/api/agent/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({ message, thread_id: tid }),
      signal: ctrl.signal
    })
  } catch (e) {
    clearTimeout(watchdog)
    if (e?.name === 'AbortError') throw new Error('助手响应超时，请重试或改用预约页')
    throw e
  }

  if (res.status === 401) {
    clearTimeout(watchdog)
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    if (!location.pathname.includes('/login')) location.href = '/login'
    throw new Error('登录已失效')
  }
  if (!res.ok) {
    clearTimeout(watchdog)
    const errText = await res.text().catch(() => '')
    if (res.status === 404) {
      throw new Error('流式接口不存在，请重启后端后再试')
    }
    let msg = errText || `流式请求失败 ${res.status}`
    try {
      const j = JSON.parse(errText)
      if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      if (j.message) msg = j.message
    } catch {
      /* keep msg */
    }
    throw new Error(msg)
  }
  if (!res.body) {
    clearTimeout(watchdog)
    throw new Error('浏览器不支持流式响应')
  }

  const queue = createCharQueue((full, idle) => {
    if (onDelta) onDelta(full, idle)
  })

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let degraded = false

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let idx
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        let eventName = 'message'
        const dataLines = []
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (eventName === 'done') continue
        const body = dataLines.join('\n')
        if (!body) continue
        let payload
        try {
          payload = JSON.parse(body)
        } catch {
          continue
        }
        if (payload.degraded) degraded = true
        if (onMeta) onMeta(payload)
        if (!payload.t) continue
        if (payload.pending) queue.setInstant(payload.t)
        else queue.replace(payload.t)
      }
    }
  } finally {
    clearTimeout(watchdog)
  }

  await queue.whenIdle()
  return { text: queue.getText(), degraded }
}
