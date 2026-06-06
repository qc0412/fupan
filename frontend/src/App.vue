<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useMarketStore } from './stores/market'
import LhbTab from './components/tabs/LhbTab.vue'
import ZtTab from './components/tabs/ZtTab.vue'
import JjydTab from './components/tabs/JjydTab.vue'
import CapitalTab from './components/tabs/CapitalTab.vue'

const tabs = [
  { key: 'lhb', label: '多次上榜', comp: LhbTab },
  { key: 'zt', label: '涨停板', comp: ZtTab },
  { key: 'jjyd', label: '竞价净额', comp: JjydTab },
  { key: 'capital', label: '大资金情绪', comp: CapitalTab },
]
const active = ref('lhb')
const store = useMarketStore()

onMounted(() => store.startPolling())
onUnmounted(() => store.stopPolling())
</script>

<template>
  <div class="main">
    <div class="tabs">
      <div
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ active: active === t.key }"
        @click="active = t.key"
      >{{ t.label }}</div>
    </div>

    <div class="meta">
      <span class="dot" :class="{ err: store.error }"></span>
      <template v-if="store.error">数据获取失败：{{ store.error }}</template>
      <template v-else>更新时间：{{ store.updatedAt }} (北京时间)</template>
    </div>

    <component v-for="t in tabs" v-show="active === t.key" :key="t.key" :is="t.comp" />
  </div>
</template>
