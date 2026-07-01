import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '입고자재 송장관리',
        short_name: '송장관리',
        start_url: '.',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#1f6feb',
        icons: [],
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
  },
})
