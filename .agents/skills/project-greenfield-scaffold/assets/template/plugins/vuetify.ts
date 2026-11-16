// plugins/vuetify.ts
// `vuetify/styles` emits ONLY the generic/elements/utilities layers
// (reset, font-family, spacing/text utility classes); component styles
// arrive per-import via vite-plugin-vuetify styles.configFile
// (assets/styles/settings.scss) — no double-emit.
import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import { createVuetify } from "vuetify/framework";
import { themeConfig } from "~/theme";

export default defineNuxtPlugin((nuxtApp) => {
  const vuetify = createVuetify({
    ssr: true,
    theme: {
      defaultTheme: "light",
      themes: {
        light: themeConfig.light,
        dark: themeConfig.dark,
      },
    },
  });

  nuxtApp.vueApp.use(vuetify);
});
