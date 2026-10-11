import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Pendant le développement, les appels au serveur de l'application (FastAPI)
// sont transmis à http://localhost:8000 : l'interface et le serveur peuvent
// tourner séparément sans réglage supplémentaire.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: { outDir: 'dist', sourcemap: true },
});
