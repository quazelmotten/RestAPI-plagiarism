import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const SUBPATH = process.env.VITE_SUBPATH !== undefined ? process.env.VITE_SUBPATH : 'plagitype'

export default defineConfig({
  plugins: [react()],
  base: SUBPATH ? `/${SUBPATH}/` : '/',
  server: {
    proxy: {
      ...(SUBPATH ? { [`/${SUBPATH}`]: { target: 'http://localhost:8000', changeOrigin: true } } : {}),
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/version': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
