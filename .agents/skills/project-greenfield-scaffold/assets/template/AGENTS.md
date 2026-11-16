# AGENTS.md

## Project

{{PROJECT_NAME}} — Nuxt 4 + TypeScript strict, Vuetify 4, Pinia setup stores,
Elysia API (`nuxt-elysia`), bun package manager.

<!-- @flag rules -->
## Code Style

The full code style guide lives at `docs/rules/` — passive reference docs,
read on demand (nothing auto-injects them). Read
`docs/rules/code-style-guide.md` first, then the topic file relevant to the
work — e.g. `code-style-guide-vuejs-patterns.md`, `-typescript-patterns.md`,
`-store-patterns-pinia.md`, `-api-development-elysia.md` — before writing code.

<!-- @endflag rules -->
## Commands

- `bun run dev` · `bun run type-check` · `bun run lint` · `bun run build`
<!-- @flag tests -->
- `bun run test:run` (Vitest) · `bun run test:e2e` (Playwright)
<!-- @endflag tests -->
<!-- @flag docs -->
- Docs site: `bun run docs:dev` (VitePress, source in `docs/`)
<!-- @endflag docs -->
<!-- @flag db -->
- Database: `bun run db:generate` · `bun run db:push` · `bun run db:migrate` · `bun run db:studio`
<!-- @endflag db -->

## Rules

- All API calls go through Pinia stores, never components/composables directly.
- Never prefix Elysia routes with `/api` — `nuxtElysia.path` adds it.
- Types in `interfaces/`, server helpers in `server/lib/`, shared utils in `utils/`.
- Secrets in `.env` only; external-service clients construct lazily.
