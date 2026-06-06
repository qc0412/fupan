<script setup>
import { ref, computed } from 'vue'
import { useMarketStore } from '../../stores/market'

const store = useMarketStore()
const activeDays = ref(3)
const dayOptions = [3, 7, 10]

const filtered = computed(() => {
  const win = store.tradingDays.slice(0, activeDays.value)
  const latest = win[0]
  return store.data
    .map((s) => {
      const zfMap = new Map(s.appearances.map((a) => [a.date, a.zf]))
      const streak = []
      for (const day of win) {
        if (!zfMap.has(day)) break
        streak.push({ date: day, zf: zfMap.get(day) })
      }
      return { ...s, appearances: streak }
    })
    .filter((s) => s.appearances.length >= 2 && s.appearances[0].date === latest)
    .sort((a, b) => b.appearances.length - a.appearances.length)
})

const datesLabel = computed(() => {
  const days = [...new Set(filtered.value.flatMap((s) => s.appearances.map((a) => a.date)))].sort()
  return days.length ? '统计区间：' + days.join(' / ') : ''
})

function zfClass(zf) {
  const v = parseFloat(zf)
  return v > 0 ? 'zf-pos' : v < 0 ? 'zf-neg' : 'zf-zero'
}
function zfText(zf) {
  const v = parseFloat(zf)
  return (v > 0 ? '+' : '') + zf + '%'
}
</script>

<template>
  <div class="card">
    <div class="filters">
      <button
        v-for="d in dayOptions" :key="d"
        class="filter-btn" :class="{ active: activeDays === d }"
        @click="activeDays = d"
      >近{{ d }}交易日</button>
    </div>
    <div class="dates">{{ datesLabel }}</div>
    <div v-if="!filtered.length" class="empty">暂无数据</div>
    <table v-else>
      <thead><tr><th>股票</th><th>连续上榜</th><th>连续涨跌幅</th></tr></thead>
      <tbody>
        <tr v-for="s in filtered" :key="s.code">
          <td><div class="stock-name">{{ s.name }}</div><div class="stock-code">{{ s.code }}</div></td>
          <td><span class="count-badge">连{{ s.appearances.length }}天</span></td>
          <td>
            <div class="appearances">
              <span v-for="a in s.appearances" :key="a.date" class="day-tag">
                <span class="date">{{ a.date.slice(5) }}</span>
                <span :class="zfClass(a.zf)">{{ zfText(a.zf) }}</span>
              </span>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
