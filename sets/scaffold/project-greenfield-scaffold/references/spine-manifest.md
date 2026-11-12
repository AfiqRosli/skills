# Spine Manifest

What "the house stack" actually is — distilled from a production codebase and genericized. This is the architecture the template encodes; use it to make adaptation calls when versions drift or a module doesn't fit a project cleanly.

## Stack

| Layer | Choice | Pinned at scaffold time |
| ----- | ------ | ----------------------- |
| Package manager | bun | — |
| Framework | Nuxt, `pages: true`, Composition API + `<script setup>` | ^4.x |
| Language | TypeScript strict (`extends .nuxt/tsconfig.json`) | ^7 |
| UI | Vuetify via vite-plugin-vuetify `autoImport` + per-component Sass (`<target>/assets/styles/settings.scss`) | ^4.x |
| Styling | SCSS, BEM naming in scoped `<style>` blocks | sass ^1 |
| State | Pinia setup stores, `storesDirs: ["./stores/**"]` | pinia ^4, @pinia/nuxt ^1 |
| API | Elysia via `nuxt-elysia`; `server/api.ts` is the root app, `nuxtElysia.path: "/api"` auto-prefixes | elysia ^1, nuxt-elysia |
| Validation | `t.Object` schemas per route on the Elysia route options | — |
| Database | Drizzle ORM; default client `drizzle-orm/neon-http` (Neon serverless); migrations via drizzle-kit → `drizzle/` | ^0.45 |
| Transactions | `server/db/tx.ts` `withDbTx` — dedicated `pg` Client + `drizzle-orm/node-postgres` per call. neon-http has NO `db.transaction()` — never fake it with ordered writes | pg ^8 |
| Auth | better-auth (`auth.ts` root) + drizzle adapter; client `lib/auth-client.ts` (`better-auth/vue`); tables `auth-schema.ts` re-exported by `server/db/schema.ts` | ^1.7 |
| Billing | `@polar-sh/better-auth` plugin (checkout + portal) inside `auth.ts`; webhook at `POST /api/auth/polar/webhooks` registered BEFORE `.mount(auth.handler)` with `parse: "none"` | adapter ^2, sdk ^1 |
| Email | Resend via `server/lib/email.ts` — lazy client + fail-safe (log, never throw): a lost email must not fail the request that triggered it | ^6 |
| Cache/rate-limit | `server/lib/redis.ts` — lazy ioredis client, `getRedis()` returns null without `REDIS_URL` | ^6 |
| Observability | `@sentry/nuxt` module; DSN via `runtimeConfig.public.sentry.dsn` (public by design) | ^11 |
| SEO | `@nuxtjs/robots` + `@nuxtjs/sitemap` + `nuxt-seo-utils` + `nuxt-og-image`; `AI_BOTS`/`PUBLIC_PATHS` constants in nuxt.config feed robots groups; `site.indexable` wired to Netlify `CONTEXT` | latest |
| Testing | Vitest (jsdom, `deps.inline: ["vuetify"]`, excludes `tests/e2e/**`) + Playwright (`tests/e2e`, `webServer` boots `npm run dev`) | ^5, ^1.6x |
| Lint | ESLint flat + `@stylistic` — double quotes, semicolons, 2-space indent, `@typescript-eslint/no-explicit-any: error`, Vue ruleset in `eslint.config.ts` | eslint ^10 |
| Hooks | husky — pre-commit `bun run lint:js`, pre-push `<target>/scripts/pre-push-build-validation.sh` (typecheck + unit tests) | ^9 |
| Deploy | Netlify — nitro `preset: "netlify"`, `netlify.toml` (bun build, `netlify-plugin-cache`, lighthouse plugin), production-only externals inline/external matcher (see nuxt.config comment — Sentry/OTel MUST stay external) | @netlify/nuxt ^1 |
| Docs | VitePress in `docs/` | ^1.6 |

## Directory map

```
app.vue  auth.ts  auth-schema.ts  drizzle.config.ts  eslint.config.ts
netlify.toml  nuxt.config.ts  playwright.config.ts  vitest.config.ts
assets/styles/      global.scss, settings.scss
components/         Common/NotificationSnackbar.vue …
composables/        useTheme.ts …
constants/          app-wide constants (add as needed)
interfaces/         all shared types (app, api, elysia, auth, common …)
layouts/            app.vue (full chrome) | blank.vue (bare) | minimal.vue (bar only)
lib/                client-side libs (auth-client.ts)
middleware/         auth.global.ts — session sync + guest/protected redirects
pages/              index, sign-in, register …
plugins/            vuetify.ts (createVuetify + theme wiring)
public/             favicon set, static files
scripts/            project scripts (pre-push validation …)
server/             api.ts, errors.ts, <domain>.ts routers, db/, lib/, middleware/
stores/             Pinia stores — one per domain
tests/              vitest specs + e2e/
utils/              logger.ts, error-handlers.ts, email.ts …
.devin/rules/       the code-style-guide set (16 files)
```

## Invariants — don't break these when adapting

1. **All API calls go through Pinia stores**, never directly in components/composables. Stores own loading/error state and surface failures through NotificationStore.
2. **Never prefix Elysia routes with `/api`** — `nuxtElysia.path` does it. `/api` in a prefix yields `/api/api/…`.
3. **One router file per domain** (`server/<domain>.ts`, `new Elysia({ prefix: "/domain" })`), registered in `server/api.ts`.
4. **ApiError family** (`server/errors.ts`) — errors carry status + machine `code`; clients branch on code, not message.
5. **Security headers + CSRF-by-Origin** in `server/api.ts` onRequest — state-changing methods need an Origin in `CORS_ORIGINS`; webhook paths are CSRF-exempt because Origin is a browser-only header (they authenticate by signature).
6. **Polar webhook before `.mount(auth.handler)`, `parse: "none"`** — signature validation needs raw body bytes; JSON parsing would consume the stream.
7. **Route vocabulary in `interfaces/app.ts`** — `GUEST_ROUTES`/`APP_ROUTES`/`PROTECTED_ROUTES` feed both the layout chooser (AppStore) and the auth guard.
8. **Layout is dynamic** — `app.vue` binds `NuxtLayout :name="appStore.layout"`; the single snackbar mounts at root so every layout reaches it.
9. **`robots: false` routeRules** express noindex (X-Robots-Tag + sitemap exclusion); public content gets `swr` + `sitemap:` keys. Never cache auth-flow pages — a cached redirect leaks across users.
10. **Types live in `interfaces/`**, server helpers in `server/lib/`, shared utilities in `utils/`. Structured logging via `utils/logger.ts` — never log secrets or credential-bearing payloads.
11. **neon-http for reads/simple writes; `withDbTx` for multi-write transactions.** No pool, per-invocation pg client — serverless-shaped.
12. **Secrets in `.env` only; `.env.example` ships var names, never values.** Server-only keys stay out of `runtimeConfig.public`.
13. **External-service clients construct lazily, never at module load.** `new X(apiKey)` that throws on missing env (the Resend constructor did) 500s every route — pages, API, everything — because the import graph loads it once. Follow `getRedis()`: missing config returns null, callers log and no-op. This is what makes placeholder env a valid dev baseline.

## Deliberately excluded from the template (source-domain, not spine)

Domain routers/stores, E2EE crypto (libsodium, wrapped keys), competitor OAuth imports, referral/creator/onboarding systems, email automations (Resend segment sync), analytics extras, release-train versioning, rate-limit subsystem, IndexNow, markdown content twins + llms.txt, `@nuxt/a11y` axe overrides beyond the defaults, `.cdo-work` watcher ignores. Reach for these from the source repo the spine was distilled from if a greenfield project needs them — they're domain modules, not spine.

## Agent tooling modules (installed post-scaffold, not rendered)

Two BMad module families ride alongside the spine but are NOT part of the render — they install into the target's own skills tree afterward via their setup skills:

- **cdo — Autonomous Delivery Org** (`cdo-setup` to install; `cdo-orchestrator`/Marshal to run): batch dispatch, alignment cards, delivery ops. Its `.cdo-work/` worktree dir is why the source project's nuxt.config carried watcher ignores — only port that ignore block if the project will actually run cdo batches.
- **srm — Skills Repo Manager** (`srm-setup` to install, `srm-sync` to sync): maps external skill repos into the project as prefixed BMad-structured skills.

Mention these in the operator checklist when the user wants agent tooling in the new repo — don't bake them into the template; their setup skills own the install and stay current when the modules update.
