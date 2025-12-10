import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:5001',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_API_URL || 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // 将 React 相关库单独打包
          'react-vendor': ['react', 'react-dom'],
          // 将 Ant Design 单独打包（较大的 UI 库）
          'antd-vendor': ['antd', '@ant-design/icons'],
          // 将地图相关库单独打包
          'map-vendor': ['leaflet', 'react-leaflet'],
          // 将其他工具库打包
          'utils-vendor': ['axios', 'zustand', 'recharts'],
        },
      },
    },
    // 提高 chunk 大小警告阈值（可选，如果不想看到警告）
    // chunkSizeWarningLimit: 1000,
  },
})

