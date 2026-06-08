<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import gsap from 'gsap'
import { useMarketStore } from './stores/market'
import LhbTab from './components/tabs/LhbTab.vue'
import JjydTab from './components/tabs/JjydTab.vue'
import CapitalTab from './components/tabs/CapitalTab.vue'
import ReviewTab from './components/tabs/ReviewTab.vue'

const tabs = [
  { key: 'capital', label: '大资金情绪', comp: CapitalTab },
  { key: 'lhb', label: '多次上榜', comp: LhbTab },
  { key: 'jjyd', label: '竞价净额', comp: JjydTab },
  { key: 'review', label: '复盘', comp: ReviewTab },
]
const active = ref('capital')
const store = useMarketStore()

const tabsEl = ref(null)
const indicatorEl = ref(null)

function moveIndicator(animate = true) {
  const wrap = tabsEl.value
  const ind = indicatorEl.value
  if (!wrap || !ind) return
  const el = wrap.querySelector('.tab.active')
  if (!el) return
  const x = el.offsetLeft
  const w = el.offsetWidth
  if (animate) {
    gsap.to(ind, { x, width: w, duration: 0.42, ease: 'power3.out' })
  } else {
    gsap.set(ind, { x, width: w })
  }
}

function pick(key) {
  if (key === active.value) return
  active.value = key
}

watch(active, () => nextTick(() => moveIndicator(true)))

onMounted(() => {
  store.startPolling()
  nextTick(() => moveIndicator(false))
  window.addEventListener('resize', () => moveIndicator(false))
})
onUnmounted(() => store.stopPolling())
</script>

<template>
  <div class="main">
    <div class="tabs" ref="tabsEl">
      <div class="tab-indicator" ref="indicatorEl"></div>
      <div
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ active: active === t.key }"
        @click="pick(t.key)"
      >{{ t.label }}</div>
    </div>

    <div class="meta">
      <span class="dot" :class="{ err: store.error }"></span>
      <template v-if="store.error">数据获取失败：{{ store.error }}</template>
      <template v-else>更新时间：{{ store.updatedAt }} (北京时间)</template>
    </div>

    <template v-for="t in tabs" :key="t.key">
      <component v-if="active === t.key" :is="t.comp" />
    </template>
  </div>
</template>
