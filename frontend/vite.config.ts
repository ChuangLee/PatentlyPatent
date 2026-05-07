import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => ({
  base: '/patent/',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    sourcemap: mode === 'staging',
    chunkSizeWarningLimit: 1500,
  },
  server: { port: 5173, host: '127.0.0.1' },
}));
