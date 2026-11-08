/** 前端展示用中文标签（库内仍存英文枚举） */

const RESERVATION_STATUS = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  cancelled: '已取消',
  canceled: '已取消',
  in_use: '使用中',
  completed: '已完成',
  expired: '已过期'
}

const PASSCODE_STATUS = {
  active: '有效',
  revoked: '已作废',
  used: '已使用',
  expired: '已过期'
}

const LAB_STATUS = {
  open: '开放',
  closed: '关闭'
}

const DEVICE_STATUS = {
  active: '在线',
  inactive: '停用',
  offline: '离线'
}

export function reservationStatusLabel(s) {
  if (s == null || s === '') return '-'
  return RESERVATION_STATUS[s] || String(s)
}

export function passcodeStatusLabel(s) {
  if (s == null || s === '') return '-'
  return PASSCODE_STATUS[s] || String(s)
}

export function labStatusLabel(s) {
  if (s == null || s === '') return '-'
  return LAB_STATUS[s] || String(s)
}

export function deviceStatusLabel(s) {
  if (s == null || s === '') return '-'
  return DEVICE_STATUS[s] || String(s)
}

/** 2026-11-07T17:43:19 → 2026-11-07 17:43 */
export function formatDateTime(v) {
  if (v == null || v === '') return '-'
  const s = String(v).replace('T', ' ')
  return s.length >= 16 ? s.slice(0, 16) : s
}
