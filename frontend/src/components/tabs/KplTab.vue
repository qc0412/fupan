<script setup>
import { computed, ref } from 'vue'
import { useMarketStore } from '../../stores/market'
import { fmtYuan, moneyClass } from '../../composables/format'

const store = useMarketStore()
const stockSort = ref('rank_rise')
const sectorSort = ref('rank_strength')
const loading = ref(false)
const error = ref('')
const seriesOn = ref(false)
const SERIES_MAX_DAYS = 14

function iso(d) {
  return d.toISOString().slice(0, 10)
}
function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return iso(d)
}
const today = iso(new Date())
const rangeDays = ref(7)
const startDate = ref(daysAgo(rangeDays.value))
const endDate = ref(today)

const payload = computed(() => store.kplInterval || {})
const stocks = computed(() => payload.value.stocks || [])
const sectors = computed(() => payload.value.sectors || [])
const stocksMasked = computed(() => Boolean(payload.value.stocks_masked))
const seriesDays = computed(() => payload.value.series?.days || [])
const rangeLabel = computed(() => {
  const range = payload.value.range || {}
  return range.start && range.end ? `${range.start} ~ ${range.end}` : ''
})
const rangeSpanDays = computed(() => {
  const a = new Date(startDate.value)
  const b = new Date(endDate.value)
  const diff = Math.round((b - a) / 86400000)
  return Number.isFinite(diff) ? diff : 0
})
const seriesAllowed = computed(() => rangeSpanDays.value < SERIES_MAX_DAYS)

const stockSortOptions = [
  { key: 'rank_rise', label: '领涨' },
  { key: 'rank_net', label: '吸金' },
]
const sectorSortOptions = [
  { key: 'rank_strength', label: '强度' },
  { key: 'rank_rise', label: '涨幅' },
  { key: 'rank_net', label: '净额' },
]
const quickRanges = [
  { label: '近3天', days: 3 },
  { label: '近7天', days: 7 },
  { label: '近14天', days: 14 },
  { label: '近30天', days: 30 },
]

function rankValue(row, key) {
  const value = Number(row?.[key])
  return Number.isFinite(value) && value > 0 ? value : Number.MAX_SAFE_INTEGER
}
function byRank(list, key) {
  return [...list].sort((a, b) => rankValue(a, key) - rankValue(b, key))
}
const sortedStocks = computed(() => byRank(stocks.value, stockSort.value))
const sortedSectors = computed(() => byRank(sectors.value, sectorSort.value))
const riseLeaders = computed(() => byRank(stocks.value, 'rank_rise').slice(0, 5))
const netLeaders = computed(() => byRank(stocks.value, 'rank_net').slice(0, 5))
const sectorLeaders = computed(() => byRank(sectors.value, 'rank_strength').slice(0, 5))
const sectorNetLeaders = computed(() => byRank(sectors.value, 'rank_net').slice(0, 5))

function rankText(row, key) {
  const v = Number(row?.[key])
  return Number.isFinite(v) && v > 0 ? `#${v}` : '--'
}
function fmtRawAmount(v) {
  if (v == null) return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return fmtYuan(n)
}
function fmtPct(v) {
  if (v == null || !Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  return (n > 0 ? '+' : '') + n + '%'
}
function fmtPrice(v) {
  return v == null ? '--' : String(v)
}
function setQuick(days) {
  rangeDays.value = days
  endDate.value = today
  startDate.value = daysAgo(days)
  fetchRange()
}
function onSlider() {
  startDate.value = daysAgo(Number(rangeDays.value))
  endDate.value = today
}
function toggleSeries() {
  seriesOn.value = !seriesOn.value
  if (seriesOn.value && !seriesDays.value.length) fetchRange()
}
let fetchCtrl = null
async function fetchRange() {
  // 连点快捷区间/拖滑块时取消上一次在途请求，保证"最新请求胜出"，旧响应不会倒灌覆盖
  if (fetchCtrl) fetchCtrl.abort()
  const ctrl = new AbortController()
  fetchCtrl = ctrl
  loading.value = true
  error.value = ''
  try {
    const qs = new URLSearchParams({ start: startDate.value, end: endDate.value })
    if (seriesOn.value && seriesAllowed.value) qs.set('series', '1')
    const res = await fetch(`/api/kpl_interval?${qs}`, { cache: 'no-store', signal: ctrl.signal })
    const d = await res.json()
    if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`)
    store.kplInterval = d
  } catch (e) {
    if (e.name !== 'AbortError') error.value = String(e.message || e)
  } finally {
    if (fetchCtrl === ctrl) {
      loading.value = false
      fetchCtrl = null
    }
  }
}
</script>

<template>
  <div class="card kpl-card" v-reveal>
    <div class="kpl-range-box">
      <div class="kpl-range-head">
        <div>
          <div class="kpl-range-title">开盘啦区间榜</div>
          <div class="kpl-range-sub">自己选区间，看领涨、吸金和板块强度（日粒度时间轴）</div>
        </div>
        <button class="filter-btn active" :disabled="loading" @click="fetchRange">{{ loading ? '刷新中…' : '刷新' }}</button>
      </div>

      <div class="kpl-quick-row">
        <button
          v-for="q in quickRanges"
          :key="q.days"
          class="filter-btn"
          :class="{ active: Number(rangeDays) === q.days && endDate === today }"
          @click="setQuick(q.days)"
        >{{ q.label }}</button>
        <button
          class="filter-btn"
          :class="{ active: seriesOn }"
          :disabled="!seriesAllowed"
          :title="seriesAllowed ? '' : `区间不超过 ${SERIES_MAX_DAYS} 个自然日才能逐日拆解`"
          @click="toggleSeries"
        >逐日演变</button>
      </div>

      <div class="kpl-slider-row">
        <span>近 {{ rangeDays }} 天</span>
        <input v-model="rangeDays" type="range" min="3" max="60" step="1" @input="onSlider" @change="fetchRange" />
      </div>

      <div class="kpl-date-row">
        <label>开始 <input v-model="startDate" type="date" /></label>
        <label>结束 <input v-model="endDate" type="date" /></label>
      </div>

      <div class="dates kpl-range-meta">
        <span v-if="payload.source">{{ payload.source }}</span>
        <span v-if="rangeLabel"> · 当前：{{ rangeLabel }}</span>
      </div>
      <div v-if="stocksMasked" class="data-quality">⚠️ 该区间不含最新交易日，开盘啦把个股数值脱敏了——个股只有排名可信，板块数据不受影响</div>
      <div v-if="error" class="data-quality">{{ error }}</div>
    </div>

    <div class="filters kpl-sort-filters">
      <span class="filter-label">个股</span>
      <button v-for="opt in stockSortOptions" :key="opt.key" class="filter-btn sort-btn" :class="{ active: stockSort === opt.key }" @click="stockSort = opt.key">{{ opt.label }}</button>
      <span class="filter-label sector-label">板块</span>
      <button v-for="opt in sectorSortOptions" :key="opt.key" class="filter-btn sort-btn" :class="{ active: sectorSort === opt.key }" @click="sectorSort = opt.key">{{ opt.label }}</button>
    </div>

    <div v-if="!stocks.length && !sectors.length" class="empty">暂无开盘啦区间榜数据</div>

    <div v-else class="kpl-grid">
      <section class="kpl-mobile-summary">
        <div class="kpl-summary-card">
          <div class="kpl-summary-title">区间领涨</div>
          <div class="kpl-summary-list">
            <div v-for="s in riseLeaders" :key="`rise-${s.code}`" class="kpl-summary-item">
              <div><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></div>
              <div class="kpl-summary-metrics"><span class="kpl-rank-pill">{{ rankText(s, 'rank_rise') }}</span><span :class="moneyClass(s.zf_interval)">{{ fmtPct(s.zf_interval) }}</span></div>
            </div>
          </div>
        </div>
        <div class="kpl-summary-card">
          <div class="kpl-summary-title">区间吸金（主力净额）</div>
          <div class="kpl-summary-list">
            <div v-for="s in netLeaders" :key="`net-${s.code}`" class="kpl-summary-item">
              <div><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></div>
              <div class="kpl-summary-metrics"><span class="kpl-rank-pill">{{ rankText(s, 'rank_net') }}</span><span :class="moneyClass(s.net_interval)">{{ fmtRawAmount(s.net_interval) }}</span></div>
            </div>
          </div>
        </div>
        <div class="kpl-summary-card">
          <div class="kpl-summary-title">板块强度</div>
          <div class="kpl-summary-list">
            <div v-for="s in sectorLeaders" :key="`sector-${s.code}`" class="kpl-summary-item">
              <div><div class="stock-name">{{ s.name }}</div><div class="stock-code">强度 {{ s.strength ?? '--' }}</div></div>
              <div class="kpl-summary-metrics"><span class="kpl-rank-pill">{{ rankText(s, 'rank_strength') }}</span><span :class="moneyClass(s.zf_interval)">{{ fmtPct(s.zf_interval) }}</span></div>
            </div>
          </div>
        </div>
        <div class="kpl-summary-card">
          <div class="kpl-summary-title">板块吸金</div>
          <div class="kpl-summary-list">
            <div v-for="s in sectorNetLeaders" :key="`sector-net-${s.code}`" class="kpl-summary-item">
              <div><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></div>
              <div class="kpl-summary-metrics"><span class="kpl-rank-pill">{{ rankText(s, 'rank_net') }}</span><span :class="moneyClass(s.net_interval)">{{ fmtRawAmount(s.net_interval) }}</span></div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="seriesOn && seriesDays.length" class="kpl-panel">
        <div class="kpl-panel-head"><div><div class="kpl-panel-title">逐日演变</div><div class="kpl-panel-sub">每个交易日的吸金榜与板块强度榜——历史日个股数值被接口脱敏，只展示排名；板块榜接口只留最近两个交易日</div></div></div>
        <div class="kpl-timeline">
          <div v-for="d in seriesDays" :key="d.date" class="kpl-timeline-day">
            <div class="kpl-timeline-date">{{ d.date }}<span v-if="d.stocks_masked" class="kpl-masked-tag">仅排名</span></div>
            <div class="kpl-timeline-row">
              <span class="kpl-timeline-label">吸金</span>
              <span v-for="(s, i) in d.net_stocks" :key="s.code" class="kpl-chip">
                #{{ i + 1 }} {{ s.name }}<template v-if="s.net_interval != null"> {{ fmtRawAmount(s.net_interval) }}</template>
              </span>
            </div>
            <div class="kpl-timeline-row" v-if="d.strength_sectors.length">
              <span class="kpl-timeline-label">强度</span>
              <span v-for="s in d.strength_sectors" :key="s.code" class="kpl-chip kpl-chip-sector">
                {{ s.name }} {{ s.strength ?? '--' }}<template v-if="s.net_interval != null">｜净{{ fmtRawAmount(s.net_interval) }}</template>
              </span>
            </div>
          </div>
        </div>
      </section>

      <section class="kpl-panel">
        <div class="kpl-panel-head"><div><div class="kpl-panel-title">个股明细</div><div class="kpl-panel-sub">领涨榜 + 吸金榜合并去重，横滑看完整数据；主力净额 = 主力买入 − 主力卖出</div></div></div>
        <div class="kpl-table-wrap">
          <table class="kpl-table">
            <thead><tr><th>股票</th><th>领涨</th><th>吸金</th><th>现价</th><th>区间涨幅</th><th>主力净额</th><th>主力买入</th><th>成交额</th><th>换手</th><th>实际流通</th></tr></thead>
            <tbody v-reveal="{ children: 'tr', stagger: 0.03, y: 8 }">
              <tr v-for="s in sortedStocks" :key="s.code">
                <td>
                  <div class="stock-name">{{ s.name }}<span v-if="s.main_tag" class="kpl-main-tag">{{ s.main_tag }}</span></div>
                  <div class="stock-code">{{ s.code }}</div>
                  <div v-if="s.concept" class="concept">{{ s.concept }}</div>
                </td>
                <td>{{ rankText(s, 'rank_rise') }}</td><td>{{ rankText(s, 'rank_net') }}</td>
                <td>{{ fmtPrice(s.price) }}</td>
                <td><span :class="moneyClass(s.zf_interval)">{{ fmtPct(s.zf_interval) }}</span></td>
                <td><span :class="moneyClass(s.net_interval)">{{ fmtRawAmount(s.net_interval) }}</span></td>
                <td>{{ fmtRawAmount(s.buy_interval) }}</td>
                <td>{{ fmtRawAmount(s.amount_interval) }}</td>
                <td>{{ s.hsl_interval != null ? s.hsl_interval + '%' : '--' }}</td>
                <td>{{ fmtRawAmount(s.float_mv) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="kpl-panel">
        <div class="kpl-panel-head"><div><div class="kpl-panel-title">板块明细</div><div class="kpl-panel-sub">强度 / 涨幅 / 净额三榜合并去重</div></div></div>
        <div class="kpl-table-wrap">
          <table class="kpl-table">
            <thead><tr><th>板块</th><th>强度</th><th>涨幅</th><th>净额</th><th>强度值</th><th>区间涨幅</th><th>区间净额</th><th>成交额</th></tr></thead>
            <tbody v-reveal="{ children: 'tr', stagger: 0.03, y: 8 }">
              <tr v-for="s in sortedSectors" :key="s.code">
                <td><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></td>
                <td>{{ rankText(s, 'rank_strength') }}</td><td>{{ rankText(s, 'rank_rise') }}</td><td>{{ rankText(s, 'rank_net') }}</td><td>{{ s.strength ?? '--' }}</td>
                <td><span :class="moneyClass(s.zf_interval)">{{ fmtPct(s.zf_interval) }}</span></td><td><span :class="moneyClass(s.net_interval)">{{ fmtRawAmount(s.net_interval) }}</span></td><td>{{ fmtRawAmount(s.amount_interval) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>
