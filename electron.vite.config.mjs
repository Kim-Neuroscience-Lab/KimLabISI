import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  main: {
    build: {
      outDir: 'dist-electron-vite/main',
      rollupOptions: {
        input: resolve(__dirname, 'src/frontend/electron/main.ts'),
        external: ['electron', 'zeromq']
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: 'dist-electron-vite/preload',
      rollupOptions: {
        input: resolve(__dirname, 'src/frontend/electron/preload.ts')
      }
    }
  },
  renderer: {
    root: 'src/frontend',
    plugins: [react()],
    css: {
      postcss: resolve(__dirname, 'postcss.config.js')
    },
    build: {
      outDir: resolve(__dirname, 'dist-electron-vite/renderer'),
      rollupOptions: {
        input: resolve(__dirname, 'src/frontend/index.html')
      }
    }
  }
})
