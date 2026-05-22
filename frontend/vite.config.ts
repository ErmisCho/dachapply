import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000', '/admin': 'http://localhost:8000', '/static/admin': 'http://localhost:8000' } }, 
}));
