import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@crawfish/ui": path.resolve(__dirname, "../../ui"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:7882",
    },
  },
});
