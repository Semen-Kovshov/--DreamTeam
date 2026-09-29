import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  server: {
    port: 5176,
    // Бэкенд: uvicorn app.main:app --port 8030 --app-dir backend.
    // 8000/8010/8021 и 5173–5175 заняты соседними проектами репозитория.
    proxy: { "/api": { target: "http://127.0.0.1:8030", changeOrigin: true } },
  },
});
