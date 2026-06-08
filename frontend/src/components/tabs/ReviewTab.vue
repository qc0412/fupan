<script setup>
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'

// 复盘报告独立于 /api/data 轮询：只在打开 Tab 时按需拉取。
const reviews = ref([])      // [{date, types:[{type,label}]}]
const activeDate = ref('')
const activeType = ref('')
const markdown = ref('')
const loading = ref(false)
const error = ref('')

const current = computed(() => reviews.value.find(r => r.date === activeDate.value))
const html = computed(() => (markdown.value ? marked.parse(markdown.value) : ''))

async function loadList() {
  try {
    const res = await fetch('/api/reviews', { cache: 'no-store' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    reviews.value = (await res.json()).reviews || []
    if (reviews.value.length) {
      const first = reviews.value[0]
      activeDate.value = first.date
      activeType.value = first.types[0]?.type || ''
      await loadReport()
    }
  } catch (e) {
    error.value = String(e.message || e)
  }
}

async function loadReport() {
  if (!activeDate.value || !activeType.value) return
  loading.value = true
  markdown.value = ''
  try {
    const res = await fetch(`/api/review/${activeDate.value}/${activeType.value}`, { cache: 'no-store' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    markdown.value = (await res.json()).markdown || ''
    error.value = ''
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

function pickDate(date) {
  activeDate.value = date
  const r = reviews.value.find(x => x.date === date)
  // 切日期后若当前类型不存在，回退到该日第一个类型
  if (r && !r.types.some(t => t.type === activeType.value)) {
    activeType.value = r.types[0]?.type || ''
  }
  loadReport()
}

function pickType(type) {
  activeType.value = type
  loadReport()
}

onMounted(loadList)
</script>

<template>
  <div class="card review-card" v-reveal>
    <div v-if="!reviews.length && !error" class="empty">暂无复盘报告</div>
    <div v-else-if="error && !reviews.length" class="empty">复盘列表加载失败：{{ error }}</div>

    <template v-else>
      <div class="review-bar">
        <select class="review-date" :value="activeDate" @change="pickDate($event.target.value)">
          <option v-for="r in reviews" :key="r.date" :value="r.date">{{ r.date }}</option>
        </select>
        <div class="review-types">
          <button
            v-for="t in (current?.types || [])"
            :key="t.type"
            class="review-type"
            :class="{ active: activeType === t.type }"
            @click="pickType(t.type)"
          >{{ t.label }}</button>
        </div>
      </div>

      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="error" class="empty">报告加载失败：{{ error }}</div>
      <div v-else class="markdown-body" v-html="html"></div>
    </template>
  </div>
</template>
