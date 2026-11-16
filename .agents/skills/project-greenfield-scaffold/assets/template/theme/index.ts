// Theme configuration — brand colors and semantic tokens.
// Both palettes carry matching keys; `on-*` colors are the text/icon
// colors rendered ON the named surface. Keep contrast >=4.5:1 for
// *-text tokens against their surface (WCAG AA).
export const themeConfig = {
  light: {
    dark: false,
    colors: {
      "primary": "#5ca3ff",
      "primary-text": "#1d56b5",
      "accent": "#5adda4",
      "secondary": "#b3d4ff",
      "background": "#fcfcfc",
      "surface": "#ebf2f7",
      "surface-variant": "#f5f5f5",
      "success": "#8ddb97",
      "warning": "#ffc067",
      "error": "#f06363",
      "info": "#5ca3ff",
      "divider": "#e0e0e0",
      "outline": "#e0e0e0",
      "black": "#000000",
      "lightBlack": "#292931",
      "gray": "#616161",
      "white": "#ffffff",
      "on-primary": "#ffffff",
      "on-accent": "#000000",
      "on-secondary": "#000000",
      "on-surface": "#000000",
      "on-background": "#000000",
      "on-success": "#000000",
      "on-warning": "#000000",
      "on-error": "#ffffff",
      "on-info": "#ffffff",
    },
  },
  dark: {
    dark: true,
    colors: {
      "primary": "#5ca3ff",
      "primary-text": "#5ca3ff",
      "accent": "#5adda4",
      "secondary": "#1e293b",
      "background": "#121212",
      "surface": "#1e1e1e",
      "surface-variant": "#2a2a2a",
      "success": "#8ddb97",
      "warning": "#ffc067",
      "error": "#f06363",
      "info": "#5ca3ff",
      "divider": "#404040",
      "outline": "#404040",
      "black": "#000000",
      "lightBlack": "#1e1e1e",
      "gray": "#9e9e9e",
      "white": "#ffffff",
      "on-primary": "#000000",
      "on-accent": "#000000",
      "on-secondary": "#ffffff",
      "on-surface": "#ffffff",
      "on-background": "#ffffff",
      "on-success": "#000000",
      "on-warning": "#000000",
      "on-error": "#ffffff",
      "on-info": "#000000",
    },
  },
} as const;

export type ThemeName = keyof typeof themeConfig;

export type ThemeColors = keyof typeof themeConfig.light.colors;

export const defaultTheme: ThemeName = "light";

export const getTheme = (name: ThemeName) => themeConfig[name];

export const toggleTheme = (current: ThemeName): ThemeName =>
  current === "light" ? "dark" : "light";
