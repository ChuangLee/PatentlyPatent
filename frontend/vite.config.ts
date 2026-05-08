import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import Components from 'unplugin-vue-components/vite';
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => ({
  base: '/patent/',
  plugins: [
    vue(),
    Components({
      // reset.css is already imported globally in main.ts -> set importStyle:false
      // to avoid double css and let resolver only do auto-import of components
      resolvers: [AntDesignVueResolver({ importStyle: false })],
      dts: false,
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    sourcemap: mode === 'staging',
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts';
          if (id.includes('@ant-design/icons-vue')) return 'vendor-antd-icons';
          if (id.includes('ant-design-vue')) return 'vendor-antd';
          if (id.includes('mammoth')) return 'vendor-mammoth';
          if (id.includes('vue-router') || id.includes('pinia') || /[\\/]vue[\\/]/.test(id)) return 'vendor-vue';
          if (id.includes('axios') || id.includes('msw')) return 'vendor-net';
          return 'vendor';
        },
      },
    },
  },
  server: { port: 5173, host: '127.0.0.1' },
}));
