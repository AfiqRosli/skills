# Module Flags

Modules default ON. `--skip <module>` disables one (repeatable); `--minimal` keeps only `core` + `rules` + `tests`. Disabling a module's requirement cascades: `auth` requires `db`; `billing` requires `auth`. Cascades are reported as `auto_disabled` in the scaffold report.

`scaffold.py` applies three removal mechanisms:

- **Excluded paths** — files/dirs deleted from the render (flags.json `excluded_paths`)
- **Flag blocks** — `// @flag <mod>` … `// @endflag <mod>` regions stripped in place (also `/* */`, `#`, `<!-- -->` comment forms)
- **Stripped deps + scripts** — `flag_stripped_deps` in `versions.json` removes package.json deps; `excluded_scripts` removes npm scripts

## The modules

| Module | What it adds | When to skip |
| ------ | ------------ | ------------ |
| `core` | Nuxt 4, Vuetify 4, Pinia, Elysia, TS strict, SCSS/BEM, ESLint, husky, layouts, theme, interfaces, utils, example router/store/page | never (always on) |
| `rules` | `docs/rules/` — the 16-file code-style-guide set (passive docs) + the `AGENTS.md` Code Style pointer | project won't follow the style guide |
| `tests` | `vitest.config.ts`, `playwright.config.ts`, `tests/`, test scripts, vitest+playwright deps | throwaway prototype |
| `db` | `server/db/` (neon-http client + withDbTx), `drizzle.config.ts`, drizzle deps, db:* scripts | no database |
| `auth` | `auth.ts`, `auth-schema.ts`, `lib/auth-client.ts`, `middleware/auth.global.ts`, `server/auth.ts`, `AuthStore`, sign-in/register pages, better-auth deps | public-only site |
| `billing` | Polar plugin in auth.ts, `polar-webhook.ts`, `BillingStore`, polar deps | no payments |
| `email` | `server/lib/email.ts` (Resend), `server/email.ts` router, resend dep | no transactional email |
| `redis` | `server/lib/redis.ts`, ioredis dep | no rate-limit/cache need |
| `sentry` | `@sentry/nuxt` module, sentry config files, DSN in runtimeConfig | no error tracking yet |
| `seo` | robots+sitemap+seo-utils+og-image modules, routeRules/site/robots/sitemap/ogImage config blocks | app behind login, no public pages |
| `docs` | `docs/` VitePress site, docs:* scripts, vitepress dep | no docs site |
| `deploy` | `netlify.toml`, nitro netlify preset + externals matcher, netlify deps | different host |

Candidate, not yet a module: **Better Auth infra** (`dash` control plane + `sentinel` abuse protection, `@better-auth/infra`). If the user asks for admin/audit or abuse protection on a scaffolded project, `references/auth-infra.md` carries the full porting spec — plugin pairing (server `sentinel()` is broken without client `sentinelClient()`), the three blocking layers `withAdminBypass` must cover, the env contract (`SENTINEL_ENABLED`, `BETTER_AUTH_API_KEY`, `NUXT_ADMIN_EMAILS`), and the verify-stage check.

## Outside the flag system

BMad agent modules — **cdo** (Autonomous Delivery Org: `cdo-setup`, Marshal via `cdo-orchestrator`) and **srm** (Skills Repo Manager: `srm-setup`, `srm-sync`) — are deliberately not flags. They're installed post-scaffold by their own setup skills, which track module updates so the scaffold never carries stale copies. Reference them in the verify-stage operator checklist, not here.
