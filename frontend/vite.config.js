import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// El backend (FastAPI) expone /auth, /chat, etc. sin prefijo. En desarrollo el front llama a /api/*
// y el proxy quita el prefijo. En producción define VITE_API_URL con la URL absoluta del backend.
// En Docker Compose usa VITE_PROXY_TARGET=http://backend:8000
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
