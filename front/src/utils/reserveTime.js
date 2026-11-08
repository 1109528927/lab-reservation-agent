/** 预约时段：禁止过去时间；并按课表/已约计算可预约空闲段 */

export function padTime(t) {
  return t && t.length === 5 ? `${t}:00` : t || ''
}

export function todayStr(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Element Plus：禁用今天之前的日期 */
export function disablePastDate(date) {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  return date.getTime() < start.getTime()
}

/** 单次预约最长（小时）；更久可另约下一段续约 */
export const MAX_RESERVE_HOURS = 2

/**
 * @returns {{ ok: true, range: [string, string] } | { ok: false, message: string }}
 */
export function validateReserveRange({ date, start, end, busy = [] } = {}) {
  if (!date || !start || !end) {
    return { ok: false, message: '请选择日期与起止时间' }
  }
  const range = [`${date}T${padTime(start)}`, `${date}T${padTime(end)}`]
  if (range[1] <= range[0]) {
    return { ok: false, message: '结束时间须晚于开始时间' }
  }
  if (new Date(range[0]).getTime() < Date.now()) {
    return { ok: false, message: '不能预约已过去的时段，请选择当前时间之后的开始时间' }
  }
  const hours =
    (new Date(range[1]).getTime() - new Date(range[0]).getTime()) / 3600000
  if (hours > MAX_RESERVE_HOURS + 1e-6) {
    return {
      ok: false,
      message: `单次预约最长 ${MAX_RESERVE_HOURS} 小时；若需更久，可再约下一段续约`
    }
  }
  const a = toMin(start)
  const b = toMin(end)
  if (Number.isFinite(a) && Number.isFinite(b) && busy?.length) {
    const hit = busy.find((x) => overlaps(a, b, x.start, x.end))
    if (hit) {
      return {
        ok: false,
        message: `该时段与已占用冲突（${hit.display || hit.label || `${fromMin(hit.start)}-${fromMin(hit.end)}`}）`
      }
    }
  }
  return { ok: true, range }
}

/** 开始时间变更时，默认结束为开始 + 最长时长（可再改） */
export function defaultEndAfterStart(start, maxHours = MAX_RESERVE_HOURS) {
  const a = toMin(start)
  if (!Number.isFinite(a)) return ''
  return fromMin(Math.min(a + maxHours * 60, toMin('22:00')))
}

function toMin(hhmm) {
  const s = String(hhmm || '')
  const m = s.match(/(\d{1,2}):(\d{2})/)
  if (!m) return NaN
  return Number(m[1]) * 60 + Number(m[2])
}

function fromMin(mins) {
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** 兼容 2026-11-06T08:00:00 / 2026-11-06 08:00:00 / 08:00 */
function extractHHMM(v) {
  const s = String(v || '')
  const m = s.match(/(\d{1,2}):(\d{2})/)
  if (!m) return ''
  return `${String(m[1]).padStart(2, '0')}:${m[2]}`
}

function parseItemRange(item) {
  const start = toMin(extractHHMM(item.start_time))
  const end = toMin(extractHHMM(item.end_time))
  return {
    start,
    end,
    title: item.title || item.note || '',
    kind: item.kind || 'busy'
  }
}

function overlaps(a0, a1, b0, b1) {
  return a0 < b1 && a1 > b0
}

function mergeBusy(ranges) {
  if (!ranges.length) return []
  const sorted = [...ranges].sort((a, b) => a.start - b.start)
  const out = [{ ...sorted[0] }]
  for (let i = 1; i < sorted.length; i++) {
    const cur = sorted[i]
    const last = out[out.length - 1]
    if (cur.start <= last.end) {
      last.end = Math.max(last.end, cur.end)
      if (cur.title && !last.title.includes(cur.title)) {
        last.title = last.title ? `${last.title}/${cur.title}` : cur.title
      }
    } else {
      out.push({ ...cur })
    }
  }
  return out
}

const MAX_SLOT_MIN = MAX_RESERVE_HOURS * 60

/**
 * 根据当日课表 + 活跃预约，算出可点选的空闲时段。
 * @returns {{ busy: Array, free: Array<{start,end,label,kind}> }}
 */
export function computeFreeSlots({
  date,
  schedule = [],
  reservations = [],
  dayStart = '08:00',
  dayEnd = '22:00',
  minMinutes = 30,
  now = new Date()
} = {}) {
  const day0 = toMin(dayStart)
  const day1 = toMin(dayEnd)
  const busyRaw = [...schedule, ...reservations]
    .map(parseItemRange)
    .filter((x) => Number.isFinite(x.start) && Number.isFinite(x.end) && x.end > x.start)

  let floor = day0
  if (date === todayStr(now)) {
    const nm = now.getHours() * 60 + now.getMinutes()
    // 向上取整到 10 分钟，避免卡在已过分钟
    floor = Math.max(day0, Math.ceil(nm / 10) * 10)
  }

  const busy = mergeBusy(busyRaw)
    .sort((a, b) => a.start - b.start)
    .map((b) => ({
      ...b,
      label: `${fromMin(b.start)}-${fromMin(b.end)}`,
      display: b.title
        ? `${fromMin(b.start)}-${fromMin(b.end)} ${b.title}`
        : `${fromMin(b.start)}-${fromMin(b.end)}`
    }))

  const gaps = []
  let cursor = floor
  for (const b of busy) {
    if (b.end <= floor) continue
    const bs = Math.max(b.start, floor)
    if (bs > cursor && bs - cursor >= minMinutes) {
      gaps.push({ start: cursor, end: Math.min(bs, day1) })
    }
    cursor = Math.max(cursor, b.end)
  }
  if (day1 - cursor >= minMinutes) {
    gaps.push({ start: cursor, end: day1 })
  }

  /** 当日连续空闲窗（可在窗内自由选 ≤2h 起止） */
  const windows = gaps
    .filter((g) => g.end - g.start >= minMinutes)
    .map((g) => ({
      start: fromMin(g.start),
      end: fromMin(g.end),
      label: `${fromMin(g.start)}-${fromMin(g.end)}`,
      startMin: g.start,
      endMin: g.end
    }))

  // 兼容旧快捷点选：窗内按 30 分钟步进拆 ≤2h（每窗最多 4 段）
  const free = []
  const seen = new Set()
  for (const g of gaps) {
    if (g.end <= g.start) continue
    let t = g.start
    let n = 0
    while (t + minMinutes <= g.end && n < 4) {
      const end = Math.min(t + MAX_SLOT_MIN, g.end)
      if (end - t >= minMinutes) {
        const label = `${fromMin(t)}-${fromMin(end)}`
        if (!seen.has(label)) {
          free.push({
            start: fromMin(t),
            end: fromMin(end),
            label,
            kind: 'gap'
          })
          seen.add(label)
          n += 1
        }
      }
      t += 30
      if (t + MAX_SLOT_MIN > g.end && end === g.end) break
    }
  }
  free.sort((x, y) => {
    const ds = toMin(x.start) - toMin(y.start)
    if (ds !== 0) return ds
    return toMin(x.end) - toMin(y.end)
  })

  return { busy, free, windows, freeGaps: free }
}
