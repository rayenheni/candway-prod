import path from "path";
import { fileURLToPath } from "url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },

  // ── Build Output ──────────────────────────────────────────
  // Built assets go into ../static/app/ which FastAPI and nginx serve.
  // Absolute paths — FastAPI mounts Vite assets at /assets/
  base: "/",
  build: {
    outDir: path.resolve(__dirname, "../static/app"),
    emptyOutDir: true,
    // Chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks — cached independently of app code
          "vendor-react": ["react", "react-dom"],
          "vendor-router": ["react-router"],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-ui": ["framer-motion", "lucide-react", "recharts"],
          "vendor-form": ["react-hook-form", "@hookform/resolvers", "zod"],
          "vendor-radix": [
            "@radix-ui/react-avatar",
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-select",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-tooltip",
          ],
        },
      },
    },
  },

  // ── Dev Server ────────────────────────────────────────────
  // Proxy API and WebSocket calls to the local FastAPI backend during development.
  // This avoids CORS issues in development — all requests appear same-origin.
  server: {
    port: 5173,
    proxy: {
      // REST API
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      // WebSocket
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
