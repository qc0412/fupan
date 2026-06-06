<script setup>
import { ref, computed } from 'vue'
import { useMarketStore } from '../../stores/market'
import { fmtWanUnit, sortKey, moneyClass } from '../../composables/format'

const store = useMarketStore()
const sort = ref('zhuli')
const sortOptions = [
  { key: 'zhuli', label: '竞价净额' },
  { key: 'jje', label: '竞额' },
  { key: 'jjzf', label: '竞涨' },
  { key: 'zf', label: '涨幅' },
  { key: 'jjhs', label: '竞价换手' },
]
const sortLabels = { zhuli: '竞价净额', jje: '竞额', jjzf: '竞价涨幅', zf: '涨幅', jjhs: '竞价换手' }

const list = computed(() =>
  store.jjyd.slice().sort((a, b) => sortKey(b, sort.value) - sortKey(a, sort.value))
)
const summary = computed(() =>
  list.value.length ? `共 ${list.value.length} 只，按${sortLabels[sort.value]}降序` : ''
)
const conceptHtml = (c) => (c || '').replace(/\|/g, '<br>')
</script>

<template>
  <div class="card">
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
        <th>股票</th><th>竞价/现价</th><th>竞价净额</th><th>竞额</th>
        <th>竞价换手</th><th class="col-ltsz">流通</th><th>概念</th>
      </tr></thead>
      <tbody>
        <tr v-for="s in list" :key="s.code">
          <td><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></td>
          <td>
            <div v-if="!isNaN(Number(s.jjzf))" class="pct-jj">竞{{ Number(s.jjzf) > 0 ? '+' : '' }}{{ s.jjzf }}%</div>
            <div :class="moneyClass(s.zf)">{{ Number(s.zf) > 0 ? '+' : '' }}{{ s.zf }}%</div>
          </td>
          <td><span :class="moneyClass(s.zhuli)" style="font-weight:600">{{ s.zhuli ? fmtWanUnit(s.zhuli) : '--' }}</span></td>
          <td>{{ fmtWanUnit(s.jje) }}</td>
          <td>{{ Number(s.jjhs) }}%</td>
          <td class="col-ltsz">{{ Number(s.ltsz).toFixed(0) }}亿</td>
          <td><div class="concept" v-html="conceptHtml(s.concept)"></div></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
