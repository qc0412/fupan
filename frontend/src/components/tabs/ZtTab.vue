<script setup>
import { ref, computed } from 'vue'
import { useMarketStore } from '../../stores/market'
import { fmtYuan, fmtDate } from '../../composables/format'

const store = useMarketStore()
const mode = ref('all')
const sort = ref('boards')
const sortOptions = [
  { key: 'boards', label: '连板高度' },
  { key: 'turnover', label: '成交额' },
  { key: 'fund', label: '封单' },
  { key: 'zbc', label: '炸板' },
]

const list = computed(() => {
  let arr = store.ztPool.slice()
  if (mode.value === 'lianban') arr = arr.filter((s) => (s.boards || 0) >= 2)
  return arr.sort((a, b) => (Number(b[sort.value]) || 0) - (Number(a[sort.value]) || 0))
})

const summary = computed(() => {
  if (!store.ztPool.length) return ''
  const maxB = store.ztPool.reduce((m, s) => Math.max(m, s.boards || 0), 0)
  const lb = store.ztPool.filter((s) => (s.boards || 0) >= 2).length
  const d = store.ztDate ? fmtDate(store.ztDate) + ' · ' : ''
  return `${d}涨停 ${store.ztPool.length} 只 · 连板 ${lb} 只 · 最高 ${maxB} 板`
})

function ladder(s) {
  const boards = s.boards || 0, days = s.days || 0
  if (boards < 2) return '首板'
  return days === boards ? `${boards}连板` : `${days}天${boards}板`
}
</script>

<template>
  <div class="card">
    <div class="filters">
      <button class="filter-btn" :class="{ active: mode === 'all' }" @click="mode = 'all'">全部</button>
      <button class="filter-btn" :class="{ active: mode === 'lianban' }" @click="mode = 'lianban'">仅连板</button>
      <div class="filter-sep"></div>
      <span class="filter-label">排序</span>
      <button
        v-for="o in sortOptions" :key="o.key"
        class="filter-btn sort-btn" :class="{ active: sort === o.key }"
        @click="sort = o.key"
      >{{ o.label }}</button>
    </div>
    <div class="dates">{{ summary }}</div>
    <div v-if="!list.length" class="empty">暂无涨停数据</div>
    <table v-else class="jjyd-table">
      <thead><tr>
        <th>股票</th><th>连板</th><th>涨幅</th><th>成交额</th><th>封单</th>
        <th class="col-amp">炸板</th><th class="col-ltsz">换手</th><th>题材</th>
      </tr></thead>
      <tbody>
        <tr v-for="s in list" :key="s.code">
          <td><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></td>
          <td><span class="ban-tag" :class="(s.boards || 0) >= 2 ? 'lianban' : 'first'">{{ ladder(s) }}</span></td>
          <td><div class="money-up">+{{ s.zf }}%</div></td>
          <td>{{ fmtYuan(s.turnover) }}</td>
          <td><span :class="{ 'money-up': s.fund }">{{ s.fund ? fmtYuan(s.fund) : '--' }}</span></td>
          <td class="col-amp">{{ s.zbc ? s.zbc + '次' : '0' }}</td>
          <td class="col-ltsz">{{ s.hsl }}%</td>
          <td><div class="concept">{{ s.hybk || '' }}</div></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
