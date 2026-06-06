<script setup>
import { computed } from 'vue'
import { tempColor } from '../composables/format'

const props = defineProps({
  temp: { type: Number, default: null },
  hasData: { type: Boolean, default: false },
})

const ARC = 301.6 // 2 * PI * 48
const t = computed(() => (props.hasData ? props.temp : 50))
const color = computed(() => (props.hasData ? tempColor(t.value) : '#ddd'))
const offset = computed(() => (props.hasData ? ARC * (1 - t.value / 100) : ARC))
</script>

<template>
  <div class="temp-gauge">
    <svg width="110" height="110" viewBox="0 0 110 110">
      <circle cx="55" cy="55" r="48" fill="none" stroke="#f0f0f0" stroke-width="9" />
      <circle
        cx="55" cy="55" r="48" fill="none" stroke-width="9" stroke-linecap="round"
        :stroke="color" stroke-dasharray="301.6" :stroke-dashoffset="offset"
      />
    </svg>
    <div class="temp-num">
      <div class="v" :style="{ color: hasData ? tempColor(t) : '#bbb' }">{{ hasData ? t : '--' }}</div>
      <div class="l">情绪温度</div>
    </div>
  </div>
</template>
