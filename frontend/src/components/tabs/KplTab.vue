<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMarketStore, isTradingHours } from '../../stores/market'
import { fmtYuan, moneyClass } from '../../composables/format'

const store = useMarketStore()
const view = ref('stocks') // 个股/板块子视图：数据一次拉取，只拆展示
const viewOptions = [
  { key: 'stocks', label: '个股' },
  { key: 'sectors', label: '板块' },
]
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
const rangeDays = ref(3)
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
const seriesAllowed = computed(() => rangeSpanDays.value <= SERIES_MAX_DAYS)

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
  { label: '近14天', days: 14, extra: true },
  { label: '近30天', days: 30, extra: true },
]
const showMoreRanges = ref(false)
// 长区间折叠在「更多」里；已选中的长区间收起后仍保留显示，避免激活态凭空消失
const visibleQuickRanges = computed(() =>
  quickRanges.filter(q => !q.extra || showMoreRanges.value || (Number(rangeDays.value) === q.days && endDate.value === today))
)

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
// 首屏 /api/data 捎带的是后端默认区间（近一周），和「近3天」高亮不符时主动拉一次。
// 判断依据是「上次成功请求的区间」而非返回的 range——后端会把非交易日端点改写成交易日，
// 拿返回值判断会导致每次切回本 tab 都重复请求。
onMounted(() => {
  const r = store.kplRequested
  if (!r || r.start !== startDate.value || r.end !== endDate.value) fetchRange()
  scheduleAutoRefresh()
})
onUnmounted(() => {
  clearTimeout(refreshTimer)
  if (fetchCtrl) fetchCtrl.abort()
})
// 自动刷新：store 轮询不再覆盖本 tab 的数据（避免盖掉用户手选区间），
// 所以盘中的新鲜度由这里自己负责，按当前选中的区间重拉
let refreshTimer = null
function scheduleAutoRefresh() {
  clearTimeout(refreshTimer)
  refreshTimer = setTimeout(() => {
    if (document.visibilityState === 'visible' && !loading.value) fetchRange()
    scheduleAutoRefresh()
  }, isTradingHours() ? 60000 : 600000)
}
let fetchCtrl = null
async function fetchRange() {
  // 连点快捷区间/拖滑块时取消上一次在途请求，保证"最新请求胜出"，旧响应不会倒灌覆盖
  if (fetchCtrl) fetchCtrl.abort()
  const ctrl = new AbortController()
  fetchCtrl = ctrl
  loading.value = true
  error.value = ''
  const reqStart = startDate.value
  const reqEnd = endDate.value
  try {
    const qs = new URLSearchParams({ start: reqStart, end: reqEnd })
    if (seriesOn.value && seriesAllowed.value) qs.set('series', '1')
    const res = await fetch(`/api/kpl_interval?${qs}`, { cache: 'no-store', signal: ctrl.signal })
    const d = await res.json()
    if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`)
    store.kplInterval = d
    store.kplRequested = { start: reqStart, end: reqEnd }
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
          v-for="q in visibleQuickRanges"
          :key="q.days"
          class="filter-btn"
          :class="{ active: Number(rangeDays) === q.days && endDate === today }"
          @click="setQuick(q.days)"
        >{{ q.label }}</button>
        <button class="filter-btn" @click="showMoreRanges = !showMoreRanges">{{ showMoreRanges ? '收起' : '更多 ▾' }}</button>
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
      <div v-if="stocksMasked && view === 'stocks'" class="data-quality">⚠️ 该区间不含最新交易日，开盘啦把个股数值脱敏了——个股只有排名可信，板块数据不受影响</div>
      <div v-if="error" class="data-quality">{{ error }}</div>
    </div>

    <div class="filters kpl-sort-filters">
      <button v-for="v in viewOptions" :key="v.key" class="filter-btn kpl-view-btn" :class="{ active: view === v.key }" @click="view = v.key">{{ v.label }}</button>
      <span class="kpl-filter-divider"></span>
      <template v-if="view === 'stocks'">
        <span class="filter-label">排序</span>
        <button v-for="opt in stockSortOptions" :key="opt.key" class="filter-btn sort-btn" :class="{ active: stockSort === opt.key }" @click="stockSort = opt.key">{{ opt.label }}</button>
      </template>
      <template v-else>
        <span class="filter-label">排序</span>
        <button v-for="opt in sectorSortOptions" :key="opt.key" class="filter-btn sort-btn" :class="{ active: sectorSort === opt.key }" @click="sectorSort = opt.key">{{ opt.label }}</button>
      </template>
      <span class="kpl-filter-divider"></span>
      <button
        class="filter-btn"
        :class="{ active: seriesOn }"
        :disabled="!seriesAllowed"
        :title="seriesAllowed ? '' : `区间不超过 ${SERIES_MAX_DAYS} 个自然日才能逐日拆解`"
        @click="toggleSeries"
      >逐日演变</button>
    </div>

    <div v-if="!stocks.length && !sectors.length" class="empty">暂无开盘啦区间榜数据</div>

    <div v-else class="kpl-grid">
      <section v-if="view === 'stocks'" class="kpl-mobile-summary">
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
      </section>
      <section v-else class="kpl-mobile-summary">
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
        <div class="kpl-panel-head"><div><div class="kpl-panel-title">逐日演变</div><div class="kpl-panel-sub">{{ view === 'stocks' ? '每个交易日的个股吸金榜——历史日个股数值被接口脱敏，只展示排名' : '每个交易日的板块强度榜——板块榜接口只留最近两个交易日' }}</div></div></div>
        <div class="kpl-timeline">
          <div v-for="d in seriesDays" :key="d.date" class="kpl-timeline-day">
            <div class="kpl-timeline-date">{{ d.date }}<span v-if="view === 'stocks' && d.stocks_masked" class="kpl-masked-tag">仅排名</span></div>
            <div class="kpl-timeline-row" v-if="view === 'stocks'">
              <span class="kpl-timeline-label">吸金</span>
              <span v-for="(s, i) in d.net_stocks" :key="s.code" class="kpl-chip">
                #{{ i + 1 }} {{ s.name }}<template v-if="s.net_interval != null"> {{ fmtRawAmount(s.net_interval) }}</template>
              </span>
            </div>
            <div class="kpl-timeline-row" v-if="view === 'sectors' && d.strength_sectors.length">
              <span class="kpl-timeline-label">强度</span>
              <span v-for="s in d.strength_sectors" :key="s.code" class="kpl-chip kpl-chip-sector">
                {{ s.name }} {{ s.strength ?? '--' }}<template v-if="s.net_interval != null">｜净{{ fmtRawAmount(s.net_interval) }}</template>
              </span>
            </div>
            <div class="kpl-timeline-row" v-if="view === 'sectors' && !d.strength_sectors.length">
              <span class="kpl-timeline-label">强度</span>
              <span class="kpl-chip">—（板块榜仅覆盖最近两个交易日）</span>
            </div>
          </div>
        </div>
      </section>

      <section v-if="view === 'stocks'" class="kpl-panel">
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

      <section v-else class="kpl-panel">
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
