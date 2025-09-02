import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

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
    plugins: [
      react(),
      ...( (globalThis as any)?.process?.env?.ANALYZE ? [visualizer({ filename: 'dist/stats.html', open: false, gzipSize: true, brotliSize: true })] : []),
    ],
    base,
    esbuild: {
      drop: ['console', 'debugger'],
      legalComments: 'none',
    },
    build: {
      sourcemap: false,
      minify: 'terser',
      terserOptions: {
        format: {
          // Preserve license and important banners only
          comments: /@license|@preserve|^!/,
        },
        compress: {
          drop_console: true,
          drop_debugger: true,
        },
      },
      rollupOptions: {
        output: {
          // Avoid exposing module/asset names in chunks where possible
          entryFileNames: 'assets/[name]-[hash].js',
          chunkFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash][extname]',
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            // React core in a stable chunk
            if (id.includes('/react/') || id.includes('/react-dom/')) return 'vendor-react'
            // Router in its own stable chunk
            if (id.includes('/react-router') || id.includes('react-router-dom')) return 'vendor-router'
            // Everything else from node_modules
            return 'vendor'
          },
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