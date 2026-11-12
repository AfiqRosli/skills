import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";

// Crawl policy — PUBLIC_PATHS feeds every robots group (search engines,
// AI crawlers, catch-all). Adding a path here makes it visible to AI
// crawlers (GEO signaling); Allow is additive to the default-allow
// baseline. Keep it in sync with routeRules sitemap metadata below.
const AI_BOTS = [
  "GPTBot",
  "OAI-SearchBot",
  "ChatGPT-User",
  "ClaudeBot",
  "Claude-SearchBot",
  "Claude-User",
  "anthropic-ai",
  "cohere-ai",
  "PerplexityBot",
  "Perplexity-User",
  "Google-Extended",
  "Applebot-Extended",
  "Bytespider",
  "CCBot",
  "DeepSeekBot",
  "Meta-ExternalAgent",
  "Meta-ExternalFetcher",
];

const PUBLIC_PATHS = ["/"];

export default defineNuxtConfig({
  modules: [
    "@pinia/nuxt",
    "@nuxt/eslint",
    "nuxt-elysia",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (_options: any, nuxt: any) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nuxt.hooks.hook("vite:extendConfig", (config: any) => {
        if (config.plugins) {
          config.plugins.push(
            vuetify({
              autoImport: true,
              // Per-component Sass via the settings layer.
              styles: { configFile: "./assets/styles/settings.scss" },
            }),
          );
        }
      });
    },
    "@nuxtjs/color-mode",
    "@nuxt/fonts",
    "@nuxt/a11y",
    // @flag sentry
    "@sentry/nuxt/module",
    // @endflag sentry
    // @flag seo
    "@nuxtjs/robots",
    "@nuxtjs/sitemap",
    // Canonicals + default OG meta are generated from the `site` block
    // below for every page. Default meta registers at tagPriority 'low',
    // so authored useSeoMeta calls always win.
    "nuxt-seo-utils",
    // Dynamic og:image/twitter:image generation. Per-page opt-in via
    // defineOgImage(). Generated images serve under /_og/**.
    "nuxt-og-image",
    // @endflag seo
  ],
  pages: true,
  devtools: { enabled: true },
  app: {
    head: {
      title: "{{PROJECT_NAME}}",
      titleTemplate: "%s",
      htmlAttrs: {
        lang: "en",
      },
      meta: [
        {
          name: "viewport",
          content: "width=device-width, initial-scale=1",
        },
        {
          charset: "utf-8",
        },
        {
          name: "apple-mobile-web-app-title",
          content: "{{PROJECT_NAME}}",
        },
        // theme-color per scheme so browser chrome matches the active
        // theme. Values mirror theme/index.ts `background`.
        {
          name: "theme-color",
          media: "(prefers-color-scheme: light)",
          content: "#fcfcfc",
        },
        {
          name: "theme-color",
          media: "(prefers-color-scheme: dark)",
          content: "#121212",
        },
      ],
      link: [
        { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
        { rel: "shortcut icon", href: "/favicon.ico" },
        { rel: "manifest", href: "/site.webmanifest" },
      ],
    },
  },
  css: ["@/assets/styles/global.scss"],
  colorMode: {
    preference: "light",
    fallback: "light",
    storage: "localStorage",
    storageKey: "nuxt-color-mode",
  },
  runtimeConfig: {
    public: {
      // Public app origin — dev/preview builds link back to their own
      // environment.
      appUrl: process.env.NUXT_PUBLIC_APP_URL || "{{SITE_URL}}",
      appVersion: process.env.npm_package_version || "0.0.0",
      // @flag sentry
      // Sentry DSN. Public by design — ingest keys are meant to ship in
      // client bundles.
      sentry: {
        dsn: process.env.SENTRY_DSN || "",
      },
      // @endflag sentry
    },
  },
  build: {
    transpile: ["vuetify"],
  },
  experimental: {
    componentIslands: true,
    buildCache: true,
  },
  compatibilityDate: "2025-07-15",
  typescript: {
    tsConfig: {
      // .agents holds agent skills whose asset templates contain raw
      // .ts/.vue files — keep them out of `nuxt typecheck`.
      exclude: ["../.agents/**"],
    },
  },
  // Disable server source maps in production — they generate 180+ extra
  // files and add significant I/O time to the Nitro build.
  sourcemap: { server: false, client: false },
  // @flag seo
  // Edge-cache public pages. `swr` emits CDN SWR headers so cached routes
  // don't touch the SSR function; swr is purged per deploy (unlike isr's
  // durable cache, which would keep stale marketing copy alive).
  //
  // `robots: false` emits X-Robots-Tag noindex + removes the route from
  // the generated sitemap — use it for app/auth routes (crawlable, never
  // indexable). `sitemap:` keys carry per-route metadata merged onto
  // auto-discovered URLs.
  //
  // Deliberately uncached (no rule): auth-flow pages (auth middleware
  // redirects would leak across users) and per-user app routes.
  routeRules: {
    "/": { swr: 300, sitemap: { changefreq: "weekly", priority: 1.0 } },
    "/robots.txt": { swr: 86400 },
    "/sitemap.xml": { swr: 86400 },
    "/_og/**": { swr: 86400 },
    // App/auth routes — crawlable, never indexable.
    "/sign-in": { robots: false },
    "/register": { robots: false },
    "/forgot-password": { robots: false },
    "/reset-password": { robots: false },
    "/verify-email": { robots: false },
  },
  // Shared site identity consumed by the Nuxt SEO modules. `indexable`
  // is wired to Netlify's CONTEXT at build time — production context
  // indexable, deploy previews not. When CONTEXT is unset the module's
  // own env check decides.
  site: {
    url: "{{SITE_URL}}",
    name: "{{PROJECT_NAME}}",
    description: "{{PROJECT_NAME}} — describe the product in one sentence.",
    ...(process.env.CONTEXT
      ? { indexable: process.env.CONTEXT === "production" }
      : {}),
  },
  // robots.txt generated from AI_BOTS/PUBLIC_PATHS above. The `Sitemap:`
  // line is auto-wired by @nuxtjs/sitemap — do NOT re-add a manual
  // sitemap key or the line duplicates. mergeWithRobotsTxtPath: false
  // guarantees no stray static file can resurrect dropped rules.
  robots: {
    mergeWithRobotsTxtPath: false,
    groups: [
      {
        userAgent: ["Googlebot", "Bingbot"],
        allow: ["/"],
        disallow: ["/api/"],
      },
      {
        userAgent: AI_BOTS,
        allow: PUBLIC_PATHS,
        disallow: ["/api/"],
      },
      {
        userAgent: ["*"],
        allow: PUBLIC_PATHS,
        disallow: ["/api/"],
      },
    ],
  },
  sitemap: {
    defaults: { changefreq: "weekly", priority: 0.8 },
  },
  // Module-level defaults merge into every defineOgImage() call site.
  ogImage: {
    defaults: {
      height: 630,
      alt: "{{PROJECT_NAME}}",
    },
  },
  // @endflag seo
  // @flag deploy
  nitro: {
    preset: "netlify",
    sourceMap: false,
    // Bundle all dependencies into the server output instead of copying
    // thousands of node_modules files to the serverless function dir —
    // on Windows each copy is scanned by Defender real-time protection
    // and dominates build time. Implemented via a catch-all inline
    // matcher rather than noExternals so the Sentry/OTel subtree stays
    // external (bundling import-in-the-middle breaks dual ESM/CJS
    // interop and crashes function invocations on cold start).
    // Scoped to production: in dev, inlining everything recreates
    // circular-import TDZ errors and breaks the dev server.
    ...(process.env.NODE_ENV === "production"
      ? {
          externals: {
            external: [
              Object.assign(
                (id: string) =>
                  /^@(sentry|opentelemetry|prisma)\//.test(id)
                  || /node_modules[/\\](@sentry|@opentelemetry|@prisma)[/\\]/.test(id)
                  || /(^|[/\\])(import-in-the-middle|require-in-the-middle|shimmer|acorn|acorn-import-attributes|cjs-module-lexer|debug|semver)([/\\]|$)/.test(id),
                { score: 1e5 },
              ),
            ],
            inline: [(id: string) => id.includes("node_modules")],
          },
        }
      : {}),
  },
  // @endflag deploy
  vite: {
    css: {
      // Parallelize SASS compilation across worker threads — Vuetify's
      // per-component SASS extraction produces hundreds of small style
      // chunks; single-threaded SASS dominates build time without this.
      preprocessorMaxWorkers: true,
    },
    build: {
      chunkSizeWarningLimit: 1500,
      // lightningcss instead of esbuild for CSS minification — esbuild's
      // CSS parser doesn't understand SASS BEM nesting syntax
      // (&--modifier, &__element) and warns on every component.
      cssMinify: "lightningcss",
    },
    vue: {
      template: {
        transformAssetUrls,
      },
    },
  },
  a11y: {},
  eslint: {
    config: {
      stylistic: {
        semi: true,
        quotes: "double",
      },
    },
  },
  fonts: {
    families: [
      { name: "Poppins", provider: "google", weights: [400, 500, 600, 700] },
      { name: "Roboto", provider: "google", weights: [400, 500, 700] },
    ],
  },
  // nuxt-elysia prepends `path` to every Elysia route — do NOT include
  // /api in route prefixes or paths become /api/api/*.
  nuxtElysia: {
    module: "~/server/api.ts",
    path: "/api",
  },
  pinia: {
    storesDirs: ["./stores/**"],
  },
});
