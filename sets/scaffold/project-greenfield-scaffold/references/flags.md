# Module Flags

Modules default ON. `--skip <module>` disables one (repeatable); `--minimal` keeps only `core` + `rules` + `tests`. Disabling a module's requirement cascades: `auth` requires `db`; `billing` requires `auth`. Cascades are reported as `auto_disabled` in the scaffold report.

Three removal mechanisms work together — `scaffold.py` applies all of them:

1. **Excluded paths** — files/dirs deleted from the render (flags.json `excluded_paths`)
2. **Flag blocks** — `// @flag <mod>` … `// @endflag <mod>` regions stripped in place (also `/* */`, `#`, `<!-- -->` comment forms)
3. **Stripped deps + scripts** — `flag_stripped_deps` in `versions.json` removes package.json deps; `excluded_scripts` removes npm scripts

## The modules

| Module | What it adds | When to skip |
| ------ | ------------ | ------------ |
| `core` | Nuxt 4, Vuetify 4, Pinia, Elysia, TS strict, SCSS/BEM, ESLint, husky, layouts, theme, interfaces, utils, example router/store/page | never (always on) |
| `rules` | `.devin/rules/` — the 16-file code-style-guide set | project won't follow the style guide |
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

`--skip db` alone auto-disables `auth` and `billing` (cascade) — listed in the report's `auto_disabled` so the user sees the implication rather than discovering it at build time.

## Outside the flag system

BMad agent modules — **cdo** (Autonomous Delivery Org: `cdo-setup`, Marshal via `cdo-orchestrator`) and **srm** (Skills Repo Manager: `srm-setup`, `srm-sync`) — are deliberately not flags. They're installed post-scaffold by their own setup skills, which track module updates so the scaffold never carries stale copies. Reference them in the verify-stage operator checklist, not here.
