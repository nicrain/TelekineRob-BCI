import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['eeg.zhaoyu.wang'],
    proxy: {
      '/api': {
        // P37①: the backend uvicorn binds IPv4 127.0.0.1:8010 only; in WSL2
        // `localhost` can resolve to ::1 → proxy ECONNREFUSED. Explicit IPv4
        // removes the ambiguity.
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8010',
        ws: true,
      },
    },
  },
});
