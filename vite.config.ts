import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: { port: 1420, strictPort: true,
    watch: { ignored: ['**/target/**', '**/src-tauri/**', '**/crates/**', '**/test-results/**', '**/playwright-report/**'] },
  },
  clearScreen: false,
  test: { include: ['src/**/*.test.ts'] },
});
