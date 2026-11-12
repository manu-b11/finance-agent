import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// El logo vive en public/finly-fox.svg. Se sirve con ?v=<hash> del contenido
// para que el navegador lo vuelva a descargar cada vez que cambias el dibujo,
// sin tener que limpiar la caché a mano.
const FOX = 'finly-fox.svg'
const FOX_FILE = fileURLToPath(new URL(`./public/${FOX}`, import.meta.url))
const VIRTUAL_FOX = 'virtual:finly-fox'
const RESOLVED_FOX = `\0${VIRTUAL_FOX}`

function foxVersion() {
  try {
    return createHash('sha1').update(readFileSync(FOX_FILE)).digest('hex').slice(0, 8)
  } catch {
    return '0'
  }
}

function finlyFox() {
  return {
    name: 'finly-fox',

    // URL del logo para la app (marca del sidebar, login, modal de acceso).
    resolveId(id) {
      if (id === VIRTUAL_FOX) return RESOLVED_FOX
    },
    load(id) {
      if (id === RESOLVED_FOX) {
        return `export default ${JSON.stringify(`/${FOX}?v=${foxVersion()}`)}\n`
      }
    },

    // El favicon apunta al mismo archivo, también con versión.
    transformIndexHtml(html) {
      return html.replaceAll(`href="/${FOX}"`, `href="/${FOX}?v=${foxVersion()}"`)
    },

    configureServer(server) {
      // En desarrollo nunca se cachea: el logo siempre es la última versión.
      server.middlewares.use((req, res, next) => {
        if (req.url?.split('?')[0] === `/${FOX}`) res.setHeader('Cache-Control', 'no-store')
        next()
      })

      server.watcher.add(FOX_FILE)
      server.watcher.on('change', (changed) => {
        if (path.resolve(changed) !== path.resolve(FOX_FILE)) return
        const mod = server.moduleGraph.getModuleById(RESOLVED_FOX)
        if (mod) server.moduleGraph.invalidateModule(mod)
        server.ws.send({ type: 'full-reload' })
      })
    },
  }
}

// El backend (FastAPI) expone /auth, /chat, etc. sin prefijo. En desarrollo el front llama a /api/*
// y el proxy quita el prefijo. En producción define VITE_API_URL con la URL absoluta del backend.
// En Docker Compose usa VITE_PROXY_TARGET=http://backend:8000
export default defineConfig({
  plugins: [react(), tailwindcss(), finlyFox()],
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
