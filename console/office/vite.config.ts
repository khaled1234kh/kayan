import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  cacheDir: '.vite',
  server: { port: 5173 },
  // Use the installed version's public source entry so Rollup can split pure
  // shader strings from executable engine code. Every bare Three import shares
  // this alias; do not ship a second engine instance or raise the warning limit.
  resolve: { alias: [{ find: /^three$/, replacement: fileURLToPath(new URL('./node_modules/three/src/Three.js', import.meta.url)) }] },
  build: { rollupOptions: { output: { manualChunks(id) {
    const module = id.replace(/\\/g,'/');
    if (module.includes('/three/src/renderers/shaders/') && module.endsWith('.glsl.js')) return 'three-shaders';
    if (module.includes('/three/src/math/') || module.endsWith('/three/src/constants.js')) return 'three-math';
    if (module.includes('/node_modules/three/')) return 'three-engine';
    if (/\/node_modules\/(react|react-dom|scheduler)\//.test(module)) return 'react';
    if (module.includes('/node_modules/')) return 'office-runtime';
  } } } },
});
