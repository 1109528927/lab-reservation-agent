/** 助手聊天：本地缓存加速首屏；权威数据在业务库最近 100 条 */

import { getAgentThreadId } from '@/utils/agentStream'

const KEY = 'agent_chat_ui_v1'

function userId() {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}').id || 'anon'
  } catch {
    return 'anon'
  }
}

function storageKey() {
  return `${KEY}:u${userId()}`
}

export function loadLocalChat() {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return null
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.slice(-100) : null
  } catch {
    return null
  }
}

export function saveLocalChat(messages) {
  try {
    const slim = (messages || [])
      .filter((m) => m && m.role && m.content)
      .map((m) => ({ role: m.role, content: m.content }))
      .slice(-100)
    localStorage.setItem(storageKey(), JSON.stringify(slim))
  } catch {
    /* ignore quota */
  }
}

/** 去掉回复里的 Markdown 星号等 */
export function scrubChatText(text) {
  if (!text) return text
  return String(text)
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*\n]+)\*/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/^#{1,6}\s*/gm, '')
    .trim()
}

export function currentThreadId() {
  return getAgentThreadId()
}
