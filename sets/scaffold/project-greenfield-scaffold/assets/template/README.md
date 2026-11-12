# {{PROJECT_NAME}}

Nuxt + Vuetify + Pinia + Elysia + Drizzle scaffold.

## Stack

| Layer | Choice |
| ----- | ------ |
| Framework | Nuxt (Vue 3, Composition API, TypeScript strict) |
| UI | Vuetify via vite-plugin-vuetify + SCSS/BEM |
| State | Pinia — **all API calls go through stores** |
| API | Elysia via `nuxt-elysia` (`server/api.ts`, `/api` auto-prefixed) |
| Database | Drizzle ORM + Neon serverless Postgres |
| Auth | better-auth + optional Polar billing |
| Testing | Vitest (unit) + Playwright (e2e) |
| Lint | ESLint + `@stylistic` (double quotes, semi, 2-space) |
| Deploy | Netlify (nitro `netlify` preset) |
| Docs | VitePress in `docs/` |

## Commands

```bash
bun install
bun run dev         # dev server :3000
bun run lint        # lint
bun run type-check  # nuxt typecheck
bun run test:run    # vitest
bun run test:e2e    # playwright
bun run build       # production build
bun run docs:dev    # docs site
bun run db:generate # drizzle migration files
bun run db:migrate  # apply migrations
```

## Conventions

- Routes: one Elysia router per domain in `server/<domain>.ts`, prefix
  without `/api` — registered in `server/api.ts`.
- Types: `interfaces/`, shared utilities `utils/`, server logic
  `server/lib/`, schema `server/db/schema.ts`.
- Code style rules: `.devin/rules/` (read `code-style-guide.md` first).
