import { fileURLToPath } from "node:url";
import { configDefaults, defineConfig } from "vitest/config";

// Mirrors the "@/*" alias in tsconfig.json so component tests can import app code.
// e2e/ holds Playwright specs (`npm run test:e2e`), which vitest must not try to run.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { exclude: [...configDefaults.exclude, "e2e/**"] },
});
