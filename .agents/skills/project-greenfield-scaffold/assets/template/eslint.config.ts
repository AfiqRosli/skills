import js from "@eslint/js";
import stylistic from "@stylistic/eslint-plugin";
import withNuxt from "./.nuxt/eslint.config.mjs";

export default withNuxt(
  {
    ...js.configs.recommended,
    plugins: {
      "@stylistic": stylistic,
    },
    rules: {
      ...js.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@stylistic/indent": [
        "error", 2,
      ],
      // Vue-specific rules for better consistency
      "vue/component-name-in-template-casing": ["error", "PascalCase"],
      "vue/custom-event-name-casing": ["error", "camelCase"],
      "vue/define-macros-order": ["error", {
        order: ["defineProps", "defineEmits"],
      }],
      "vue/no-unused-vars": "error",
      "vue/padding-line-between-blocks": ["error", "always"],
      "vue/html-self-closing": ["error", {
        html: {
          void: "never",
          normal: "always",
          component: "always",
        },
        svg: "always",
        math: "always",
      }],
      "vue/max-attributes-per-line": ["error", {
        singleline: 3,
        multiline: 1,
      }],
      "vue/html-indent": ["error", 2],
      "vue/no-v-html": "error",
      // Vuetify data-table slots use dotted names (#item.field) — the dot
      // is a slot-name segment, not a modifier.
      "vue/valid-v-slot": ["error", { allowModifiers: true }],
      "vue/require-default-prop": "error",
      "vue/require-prop-types": "error",
    },
  },
).prepend(
  {
    ignores: [
      "docs/.vitepress/cache/**",
      "docs/.vitepress/dist/**",
      "**/cache/**",
      "**/deps/**",
      "node_modules/**",
      ".nuxt/**",
      ".output/**",
      "dist/**",
      "nuxt.config.ts",
      ".agents/**",
    ],
  },
).append(
  {
    rules: {
      "no-unused-vars": [
        "error",
        {
          args: "all",
          argsIgnorePattern: "^_",
          caughtErrors: "none",
        },
      ],
      "prefer-const": "error",
    },
  },
);
