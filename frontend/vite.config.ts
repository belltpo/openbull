import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Pre-bundle the Plotly CJS bundles so dev and prod see identical default-
  // export shapes — without this Vite occasionally returns the namespace
  // object instead of the default function and the chart fails to mount.
  optimizeDeps: {
    // Pre-bundle ALL heavy / lazily-discovered deps up front so Vite does a
    // single optimize pass at startup. Without this, navigating to a lazy
    // route (charts, Base UI parts) triggers a mid-session re-optimize that
    // 504s the in-flight import ("Outdated Optimize Dep").
    include: [
      "react-plotly.js/factory",
      "plotly.js-cartesian-dist-min",
      "lightweight-charts",
      "@base-ui/react",
      "@base-ui/react/tabs",
      "@base-ui/react/switch",
      "@base-ui/react/separator",
      "@base-ui/react/select",
      "@base-ui/react/scroll-area",
      "@base-ui/react/input",
      "@base-ui/react/menu",
      "@base-ui/react/dialog",
      "@base-ui/react/button",
      "@base-ui/react/merge-props",
      "@base-ui/react/use-render",
      "@base-ui/react/avatar",
    ],
  },
  server: {
    host: "127.0.0.1", // force IPv4 loopback — Node on Windows binds "localhost" to ::1-only
    port: 5173,
    strictPort: true,
    proxy: {
      // Trailing slashes prevent accidental prefix matches — e.g. the bare
      // "/web" rule used to swallow "/websocket/test" because it starts with
      // "/web" — causing the browser to hit FastAPI instead of Vite's SPA.
      "/api/": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/auth/": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/web/": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/upstox/": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/zerodha/": { target: "http://127.0.0.1:8000", changeOrigin: true },
      // Strategy module WebSocket — proxied with ws:true so the upgrade
      // handshake is forwarded to the backend. Without this Vite serves
      // the SPA's index.html for /ws/strategy/{id} and the browser sees
      // an immediate close (or just hangs at opening) — which was the
      // whole reason live PnL never streamed in dev.
      "/ws/": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
