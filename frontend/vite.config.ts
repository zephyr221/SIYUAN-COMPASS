import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "../", "");
  const runtimeEnv = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  return {
    base: runtimeEnv?.VITE_BASE_PATH || env.VITE_BASE_PATH || "/",
    envDir: "../",
    plugins: [react()],
    server: {
      port: 5173
    }
  };
});
