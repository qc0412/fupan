<script setup>
import { ref, watch, onMounted } from 'vue'
import gsap from 'gsap'
import { tempColor } from '../composables/format'

const props = defineProps({
  temp: { type: Number, default: null },
  hasData: { type: Boolean, default: false },
})

const ARC = 301.6 // 2 * PI * 48
const target = () => (props.hasData ? Math.max(0, Math.min(100, props.temp)) : 0)

const offset = ref(ARC)          // 圆环 dashoffset
const shown = ref(0)             // 中央数字
const color = ref('#3b475a')

const tweenObj = { v: 0 }
function animate() {
  const to = target()
  color.value = props.hasData ? tempColor(to) : '#3b475a'
  gsap.to(tweenObj, {
    v: to,
    duration: 1.1,
    ease: 'power2.out',
    onUpdate: () => {
      shown.value = tweenObj.v
      offset.value = ARC * (1 - tweenObj.v / 100)
    },
  })
}

onMounted(() => { tweenObj.v = 0; animate() })
watch(() => [props.temp, props.hasData], animate)
</script>

<template>
  <div class="temp-gauge">
    <svg width="116" height="116" viewBox="0 0 116 116">
      <circle cx="58" cy="58" r="48" fill="none" stroke="#e3e7ec" stroke-width="9" />
      <circle
        class="arc-fg"
        cx="58" cy="58" r="48" fill="none" stroke-width="9" stroke-linecap="round"
        :stroke="color" stroke-dasharray="301.6" :stroke-dashoffset="offset"
      />
    </svg>
    <div class="temp-num">
      <div class="v" :style="{ color: hasData ? color : '#5f6b7d' }">{{ hasData ? Math.round(shown) : '--' }}</div>
      <div class="l">情绪温度</div>
    </div>
  </div>
</template>
