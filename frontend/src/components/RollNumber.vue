<script setup>
import { ref, watch, onMounted } from 'vue'
import gsap from 'gsap'

const props = defineProps({
  value: { type: Number, default: 0 },
  decimals: { type: Number, default: 0 },
  duration: { type: Number, default: 0.9 },
  prefix: { type: String, default: '' },
  suffix: { type: String, default: '' },
})

const shown = ref(props.value)
const obj = { v: props.value }

function animate(to) {
  gsap.to(obj, {
    v: Number(to) || 0,
    duration: props.duration,
    ease: 'power2.out',
    onUpdate: () => { shown.value = obj.v },
  })
}

onMounted(() => { obj.v = 0; animate(props.value) })
watch(() => props.value, (n) => animate(n))
</script>

<template>
  <span class="num">{{ prefix }}{{ Number(shown).toFixed(decimals) }}{{ suffix }}</span>
</template>
