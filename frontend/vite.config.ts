import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "../", "");
  const runtimeEnv = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  return {
    // 生产部署在 /shengya/ 子路径下，构建时必须带上，否则产物会引用 /assets/ 而 404。
    base: runtimeEnv?.VITE_BASE_PATH || env.VITE_BASE_PATH || "/",
    envDir: "../",
    plugins: [react()],
    server: {
      port: 5173
    },
    test: {
      environment: "jsdom",
      environmentOptions: {
        jsdom: {
          url: "http://localhost/"
        }
      },
      restoreMocks: true,
      setupFiles: "./src/test/setup.ts"
    }
  };
});
