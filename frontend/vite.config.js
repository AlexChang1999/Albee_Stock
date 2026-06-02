import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // 把「第三方套件」(node_modules) 跟「自己寫的程式」分成不同檔案。
        // 好處：MUI、React 這類套件很少改，瀏覽器可以長期快取那一塊；
        //       之後你只改自己的程式碼時，使用者只需重新下載小小的那塊，
        //       不必每次都重抓幾百 KB 的 MUI。
        manualChunks(id) {
          if (id.includes('node_modules')) {
            return 'vendor'
          }
        },
      },
    },
    // 主因是 MUI 本來就大、且儀表板一進來就要用，無法靠延遲載入縮小。
    // 把警告門檻調到 700KB，避免每次 build 都跳那條其實不影響使用的提醒。
    chunkSizeWarningLimit: 700,
  },
  // Vitest 測試設定（跑 npm run test 時用）
  test: {
    globals: true, // 讓 describe/it/expect 不必每個檔案 import
    environment: 'jsdom', // 模擬瀏覽器環境（元件才有 document 可用）
    setupFiles: './src/test/setup.js', // 每個測試檔跑之前先載入的設定
  },
})
