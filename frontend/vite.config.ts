import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

const backend = process.env.ASTEROID_BACKEND ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../asteroid/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: backend, changeOrigin: false } },
  },
});
