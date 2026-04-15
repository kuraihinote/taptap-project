import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy /chat → FastAPI on 8000 so no CORS issues in dev
      "/chat":     "http://localhost:8000",
      "/health":   "http://localhost:8000",
      "/colleges": "http://localhost:8000",
      "/export":   "http://localhost:8000",
    },
  },
});
