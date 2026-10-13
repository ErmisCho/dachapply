import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000', '/admin': 'http://127.0.0.1:8000', '/static/admin': 'http://127.0.0.1:8000' } }, 
}));
