// 通用格式化与排序辅助（从旧单页逐字搬来，保持口径一致）

// 元为单位：>=1亿 显示亿，>=1万 显示万
export function fmtYuan(v) {
  v = Number(v) || 0
  const abs = Math.abs(v)
  if (abs >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (abs >= 1e4) return Math.round(v / 1e4) + '万'
  return v.toString()
}

// 万为单位（竞价净额/竞额）：>=1万万=亿
export function fmtWanUnit(v) {
  v = Number(v) || 0
  const abs = Math.abs(v)
  if (abs >= 1e4) return (v / 1e4).toFixed(1) + '亿'
  return Math.round(v) + '万'
}

// 20260605 -> 06-05
export function fmtDate(s) {
  s = String(s || '')
  return s.length === 8 ? s.slice(4, 6) + '-' + s.slice(6, 8) : s
}

// 排序取值：非数字归为 -Infinity，沉底
export function sortKey(s, key) {
  const v = s[key]
  if (v === 'none' || v === null || v === undefined || v === '') return -Infinity
  const n = Number(v)
  return isNaN(n) ? -Infinity : n
}

// 涨跌幅着色类名
export function moneyClass(v) {
  const n = Number(v)
  return n > 0 ? 'money-up' : n < 0 ? 'money-down' : ''
}

export function tempColor(t) {
  if (t >= 65) return '#e74c3c'
  if (t <= 35) return '#27ae60'
  return '#f39c12'
}
