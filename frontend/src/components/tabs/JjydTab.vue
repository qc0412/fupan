<script setup>
import { ref, computed } from 'vue'
import { useMarketStore } from '../../stores/market'
import { fmtWanUnit, sortKey, moneyClass } from '../../composables/format'

const store = useMarketStore()
const sort = ref('zhuli')
const sortOptions = [
  { key: 'zhuli', label: '竞价净额' },
  { key: 'jje', label: '竞额' },
  { key: 'ratio', label: '净额占比' },
  { key: 'jjhs', label: '竞价换手' },
]
const sortLabels = { zhuli: '竞价净额', jje: '竞额', ratio: '净额占比', jjhs: '竞价换手' }

const HOT = 45 // 净额占比 ≥45% = 资金坚决，🔥 重点标注

// 净额占比 = 竞价净额 / 竞额（同为万元单位）
function ratioOf(s) {
  const z = Number(s.zhuli), j = Number(s.jje)
  return j > 0 && !isNaN(z) ? (z / j) * 100 : null
}

const list = computed(() =>
  store.jjyd
    .map((s) => ({ ...s, ratio: ratioOf(s) }))    // 先算占比，才能按它排序
    .sort((a, b) => sortKey(b, sort.value) - sortKey(a, sort.value))
)
const hotCount = computed(() => list.value.filter((s) => s.ratio != null && s.ratio >= HOT).length)
const summary = computed(() =>
  list.value.length
    ? `共 ${list.value.length} 只，按${sortLabels[sort.value]}降序` + (hotCount.value ? ` · 🔥 净额占比≥${HOT}% ${hotCount.value} 只` : '')
    : ''
)
// concept 来自第三方接口，先转义 HTML 特殊字符再做 | → <br>，防 XSS 注入
const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
   .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
const conceptHtml = (c) => escapeHtml(String(c || '')).replace(/\|/g, '<br>')
</script>

<template>
  <div class="card" v-reveal>
    <div class="filters">
      <span class="filter-label">排序</span>
      <button
        v-for="o in sortOptions" :key="o.key"
        class="filter-btn sort-btn" :class="{ active: sort === o.key }"
        @click="sort = o.key"
      >{{ o.label }}</button>
    </div>
    <div class="dates">{{ summary }}</div>
    <div v-if="!list.length" class="empty">暂无数据（交易日 09:25 后更新）</div>
    <table v-else class="jjyd-table">
      <thead><tr>
        <th>股票</th><th>竞价/现价</th><th>竞价净额</th><th>竞额</th><th>净额占比</th>
        <th>竞价换手</th><th class="col-ltsz">流通</th><th>概念</th>
      </tr></thead>
      <tbody v-reveal="{ children: 'tr', stagger: 0.025, y: 8 }">
        <tr v-for="s in list" :key="s.code" :class="{ hot: s.ratio != null && s.ratio >= HOT }">
          <td><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></td>
          <td>
            <div v-if="!isNaN(Number(s.jjzf))" class="pct-jj">竞{{ Number(s.jjzf) > 0 ? '+' : '' }}{{ s.jjzf }}%</div>
            <div :class="moneyClass(s.zf)">{{ Number(s.zf) > 0 ? '+' : '' }}{{ s.zf }}%</div>
          </td>
          <td><span :class="moneyClass(s.zhuli)" style="font-weight:600">{{ s.zhuli ? fmtWanUnit(s.zhuli) : '--' }}</span></td>
          <td>{{ fmtWanUnit(s.jje) }}</td>
          <td class="ratio-cell">
            <span v-if="s.ratio != null" :class="{ 'ratio-hot': s.ratio >= HOT }">{{ s.ratio.toFixed(1) }}%</span>
            <span v-else>--</span>
          </td>
          <td>{{ Number(s.jjhs) }}%</td>
          <td class="col-ltsz">{{ Number(s.ltsz).toFixed(0) }}亿</td>
          <td><div class="concept" v-html="conceptHtml(s.concept)"></div></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
