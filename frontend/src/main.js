import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles.css'
import { registerAnim } from './composables/anim'

const app = createApp(App).use(createPinia())
registerAnim(app)
app.mount('#app')
