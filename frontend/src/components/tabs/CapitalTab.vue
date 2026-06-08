<script setup>
import { computed } from 'vue'
import { useMarketStore } from '../../stores/market'
import { fmtYuan, moneyClass } from '../../composables/format'
import TempGauge from '../TempGauge.vue'
import RollNumber from '../RollNumber.vue'

const store = useMarketStore()
const cs = computed(() => store.capitalSignals || {})
const hasData = computed(() => store.topVolume.length > 0 && cs.value.temp != null)

const up = computed(() => cs.value.up_count || 0)
const down = computed(() => cs.value.down_count || 0)
const flat = computed(() => cs.value.flat_count || 0)
const ratio = computed(() => (down.value > 0 ? (up.value / down.value).toFixed(2) : up.value ? '∞' : '0'))
const avg = computed(() => cs.value.avg_zf ?? 0)
const sumZhuli = computed(() => cs.value.sum_zhuli || 0)
const verifiedCount = computed(() => cs.value.verified_count ?? 0)
const totalCount = computed(() => cs.value.total_count ?? store.topVolume.length)
const allVerified = computed(() => totalCount.value > 0 && verifiedCount.value === totalCount.value)
</script>

<template>
  <div class="card" v-reveal>
    <div class="capital-hero">
      <TempGauge :temp="cs.temp" :has-data="hasData" />
      <div class="capital-stats">
        <div class="stat">
          <span class="label">红绿比</span>
          <span class="val">
            <span class="money-up"><RollNumber :value="up" :duration="0.7" />红</span> / <span class="money-down"><RollNumber :value="down" :duration="0.7" />绿</span><span v-if="flat"> · {{ flat }}平</span>
            <span style="color:var(--txt-3);font-weight:400;font-size:0.78rem"> ({{ ratio }})</span>
          </span>
        </div>
        <div class="stat">
          <span class="label">平均涨幅</span>
          <span class="val"><span :class="moneyClass(avg)"><RollNumber :value="Number(avg)" :decimals="2" :prefix="avg > 0 ? '+' : ''" suffix="%" /></span></span>
        </div>
        <div class="stat">
          <span class="label">合计成交</span>
          <span class="val">{{ fmtYuan(cs.sum_turnover || 0) }}</span>
        </div>
        <div class="stat">
          <span class="label">主力净额</span>
          <span class="val"><span :class="moneyClass(sumZhuli)">{{ sumZhuli >= 0 ? '+' : '-' }}{{ fmtYuan(Math.abs(sumZhuli)) }}</span></span>
        </div>
      </div>
    </div>

    <div class="signals">
      <span v-for="(s, i) in cs.signals || []" :key="i" class="signal" :class="s.type">
        {{ s.label }}<span v-if="s.tip" class="tip">{{ s.tip }}</span>
      </span>
    </div>

    <div v-if="hasData" class="data-quality" :class="{ ok: allVerified }">
      {{ allVerified ? '✓' : '⚠' }} 东财×腾讯交叉验证 {{ verifiedCount }}/{{ totalCount }} 通过<span v-if="!allVerified">（存疑行主力净额已剔除出情绪聚合）</span>
    </div>

    <div v-if="!store.topVolume.length" class="empty">暂无数据（盘前/休市时段或抓取失败）</div>
    <table v-else class="top-volume-table">
      <thead><tr>
        <th>股票</th><th>涨幅</th><th>成交额</th><th>主力净额</th>
        <th class="col-hsl">换手</th><th class="col-amp">振幅</th><th>行业</th>
      </tr></thead>
      <tbody v-reveal="{ children: 'tr', stagger: 0.03, y: 8 }">
        <tr v-for="(s, i) in store.topVolume" :key="s.code" :class="{ unverified: s.verified === false }">
          <td>
            <span class="rank">{{ i + 1 }}</span><span class="stock-name">{{ s.name }}</span>
            <span v-if="s.verified === false" class="doubt" :title="(s.flags || []).join('；')">存疑</span>
            <div class="stock-code">{{ s.code }}</div>
          </td>
          <td><span :class="moneyClass(s.zf)">{{ Number(s.zf) > 0 ? '+' : '' }}{{ Number(s.zf) || 0 }}%</span></td>
          <td>{{ fmtYuan(s.turnover) }}</td>
          <td>
            <span v-if="s.zhuli == null" class="doubt" title="净额>成交额，物理不可能，已判废">判废</span>
            <span v-else :class="moneyClass(s.zhuli)">{{ Number(s.zhuli) ? (Number(s.zhuli) >= 0 ? '+' : '-') + fmtYuan(Math.abs(Number(s.zhuli))) : '--' }}</span>
          </td>
          <td class="col-hsl">{{ s.hsl != null ? s.hsl + '%' : '--' }}</td>
          <td class="col-amp">{{ s.amp != null ? s.amp + '%' : '--' }}</td>
          <td><div class="industry">{{ s.industry || '' }}</div></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
