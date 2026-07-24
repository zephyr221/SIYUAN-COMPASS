import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
export default defineConfig(function (_a) {
    var _b;
    var mode = _a.mode;
    var env = loadEnv(mode, "../", "");
    var runtimeEnv = (_b = globalThis.process) === null || _b === void 0 ? void 0 : _b.env;
    return {
        base: (runtimeEnv === null || runtimeEnv === void 0 ? void 0 : runtimeEnv.VITE_BASE_PATH) || env.VITE_BASE_PATH || "/",
        envDir: "../",
        plugins: [react()],
        server: {
            port: 5173
        }
    };
});
