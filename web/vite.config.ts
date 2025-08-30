import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Vite passes env via import.meta.env at runtime, and here via "mode"-based env injection.
  // However, the cleanest is to use import.meta.env in code and let Vite inject the base at build.
  // For base here, we can read from process.env in Node context if types are available, or simply rely on default.
  // To avoid Node types, we leave base to default to '/static/' and allow overriding via define if needed.
  // Asset base (served by Django/WhiteNoise under /static/). We place SPA assets under /static/app/
  // In development, keep base at '/' to avoid dev-server redirects that conflict with Router basename '/app'.
  // In production builds, default to '/static/app/' so Django serves assets under /static/app/.
  const envBase = (globalThis as any)?.process?.env?.VITE_BASE_URL
  const base = mode === 'development' ? (envBase || '/') : (envBase || '/static/app/')
  return {
    plugins: [react()],
    base,
    esbuild: {
      drop: ['console', 'debugger'],
      legalComments: 'none',
    },
    build: {
      sourcemap: false,
      minify: 'esbuild',
      rollupOptions: {
        output: {
          // Avoid exposing module/asset names in chunks where possible
          entryFileNames: 'assets/[name]-[hash].js',
          chunkFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash][extname]',
        },
      },
    },
    css: {
      devSourcemap: false,
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        // Proxy API calls to the Django server during dev
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
        // Proxy media (export downloads, uploads) to Django
        '/media': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})