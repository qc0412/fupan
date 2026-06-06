import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 生产构建产物输出到 dist/，由 nginx 托管；/api 在 dev 时代理到 Flask
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5002',
      '/healthz': 'http://127.0.0.1:5002',
    },
  },
})
