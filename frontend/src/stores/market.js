import { defineStore } from 'pinia'

// 北京时间交易时段判断（容器跑 UTC 也准）
export function isTradingHours() {
  const now = new Date()
  const cn = new Date(now.getTime() + (now.getTimezoneOffset() + 480) * 60000)
  const day = cn.getDay()
  if (day === 0 || day === 6) return false
  const hm = cn.getHours() * 100 + cn.getMinutes()
  return hm >= 900 && hm <= 1530
}

export const useMarketStore = defineStore('market', {
  state: () => ({
    updatedAt: '',
    data: [],            // 龙虎榜多次上榜
    tradingDays: [],
    jjyd: [],            // 竞价净额
    topVolume: [],       // 大资金情绪明细
    capitalSignals: {},
    kplInterval: null,
    kplRequested: null,  // KplTab 最近一次成功请求的 {start,end}（后端会改写返回的 range，不能拿它判断）
    ztPool: [],          // 涨停板
    ztDate: '',
    loading: false,
    error: '',
    _timer: null,
    _onVisible: null,
  }),
  actions: {
    async fetchData() {
      this.loading = true
      try {
        const res = await fetch('/api/data', { cache: 'no-store' })
        if (!res.ok) throw new Error('HTTP ' + res.status)
        const d = await res.json()
        this.updatedAt = d.updated_at || ''
        this.data = d.data || []
        this.tradingDays = d.trading_days || []
        this.jjyd = d.jjyd || []
        this.topVolume = d.top_volume || []
        this.capitalSignals = d.capital_signals || {}
        // 仅首次兜底注入；之后 KplTab 自管区间，轮询不许把用户选的区间盖回默认值
        if (!this.kplInterval) this.kplInterval = d.kpl_interval || null
        this.ztPool = d.zt_pool || []
        this.ztDate = d.zt_date || ''
        this.error = ''
      } catch (e) {
        this.error = String(e.message || e)
      } finally {
        this.loading = false
      }
    },
    // 轮询：交易时段 30 秒，否则 5 分钟；页面隐藏时暂停
    startPolling() {
      const tick = () => {
        if (document.visibilityState === 'visible') this.fetchData()
        this._timer = setTimeout(tick, isTradingHours() ? 30000 : 300000)
      }
      this.fetchData()
      this._timer = setTimeout(tick, isTradingHours() ? 30000 : 300000)
      this._onVisible = () => {
        if (document.visibilityState === 'visible') this.fetchData()
      }
      document.addEventListener('visibilitychange', this._onVisible)
    },
    stopPolling() {
      if (this._timer) clearTimeout(this._timer)
      this._timer = null
      if (this._onVisible) {
        document.removeEventListener('visibilitychange', this._onVisible)
        this._onVisible = null
      }
    },
  },
})
