import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // Listen on all interfaces for network access
    port: 3000,
    strictPort: false,
    hmr: {
      host: 'localhost'
    },
    // Proxy only used in development when VITE_API_URL is not set
    // In production builds, VITE_API_URL must be set to point to backend
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  build: {
    rollupOptions: {
      input: {
        main: './index.html',
        learningDashboard: './learning-dashboard.html'
      }
    },
    // Production build configuration
    // Note: VITE_API_URL must be set in .env.production for AWS deployment
    // The proxy is NOT used in production builds - all API calls use VITE_API_URL
  }
})

