import { defineConfig, configDefaults } from "vitest/config";
import { resolve } from "path";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  // Cast guards against type mismatches when vitest bundles a different
  // vite version than @vitejs/plugin-vue (structurally identical Plugin
  // types).
  plugins: [vue() as never],
  test: {
    globals: true,
    environment: "jsdom",
    css: true,
    // tests/e2e is Playwright's directory — vitest must not pick up its
    // specs (they use @playwright/test APIs).
    exclude: [...configDefaults.exclude, "tests/e2e/**", ".agents/**"],
    server: {
      deps: {
        inline: ["vuetify"],
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
});
