/**
 * 助手 SSE：token 进队列，渲染层固定约 20ms 出一个字。
 * 上游一次吐一串时也不会整段贴上；句末标点多停一拍。
 */

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
    const ch = queue.shift()
    text += ch
    onFrame(text, false)
    const pause = '。！？!?'.includes(ch) ? 120 : 36
    timer = setTimeout(step, pause)
  }

  return {
    enqueue(piece) {
      if (!piece) return
      for (const ch of piece) queue.push(ch)
      if (!timer) timer = setTimeout(step, 36)
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
  const { onDelta, onMeta } = handlers
  const token = localStorage.getItem('token') || ''
  const res = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : ''
    },
    body: JSON.stringify({ message })
  })

  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    if (!location.pathname.includes('/login')) location.href = '/login'
    throw new Error('登录已失效')
  }
  if (!res.ok) {
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
  if (!res.body) throw new Error('浏览器不支持流式响应')

  const queue = createCharQueue((full, idle) => {
    if (onDelta) onDelta(full, idle)
  })

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let degraded = false

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
      if (payload.t) queue.enqueue(payload.t)
    }
  }

  await queue.whenIdle()
  return { text: queue.getText(), degraded }
}
