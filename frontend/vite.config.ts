import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { TanStackRouterVite } from '@tanstack/router-vite-plugin'
import tsConfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [
    TanStackRouterVite(),
    tsConfigPaths(),
    react(),
  ],
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
    host: true,
  },
})

