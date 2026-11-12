import { useTheme as useVuetifyTheme } from "vuetify";
import { defaultTheme, toggleTheme, type ThemeName } from "@/theme";

/**
 * Theme composable — bridges @nuxtjs/color-mode and the Vuetify theme
 * instance. Components call toggle() and never touch the Vuetify theme
 * object directly, keeping a single place to change the mechanism.
 */
export function useTheme() {
  const vuetifyTheme = useVuetifyTheme();
  const colorMode = useColorMode();

  const current = computed<ThemeName>(() =>
    (colorMode.value as ThemeName) || defaultTheme,
  );

  const isDark = computed(() => current.value === "dark");

  const toggle = () => {
    const next = toggleTheme(current.value);
    colorMode.preference = next;
    vuetifyTheme.change(next);
  };

  return { current, isDark, toggle };
}
