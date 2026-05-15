import { defineConfig } from 'vite'

export default defineConfig({
  // Expose all VITE_* env vars to the browser bundle
  envPrefix: 'VITE_',

  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },

  server: {
    port: 5173,
    // Proxy API calls to local backend during development
    // so you never need to touch CORS while coding locally
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
