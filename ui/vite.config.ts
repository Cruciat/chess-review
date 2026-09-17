import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    // Il frontend chiama /api come se fosse sullo stesso host: in sviluppo
    // è Vite a inoltrare al backend, quindi niente URL cablati nel codice.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
