# Stage 3 — Wire

**Prerequisite:** template rendered in the target.

Turn the file tree into a working repo, inside `<target>`:

1. `bun install` — resolve the pinned manifest. If `bun` is absent, use `npm install` and note it (the spine assumes bun: lockfile and netlify build command).
2. `cp .env.example .env` — fill only what the enabled modules need for a local dev run (DATABASE_URL if db, BETTER_AUTH_* if auth). Leave the rest empty.
3. `git init` + first commit if the user wants version control — and only then `bunx husky` (or `bun run prepare`) to install git hooks. Skip husky when there's no git repo; it has nothing to hook into.
5. `bunx nuxt prepare` — generates `.nuxt` types; also the first real compatibility probe.

**Version-drift adaptation — this is where your judgment matters.** The manifest pins versions that were latest-stable at `resolved_at` in `versions.json`, but majors move. Watch for:

- `nuxt-elysia` vs Nuxt 4 compatibility (it was authored for Nuxt 3 — if prepare/dev fails on it, check for a newer release or shim the module).
- Renamed/broken imports across the pinned majors (Vuetify 4 plugin API, Pinia 4, Vitest 5, better-auth surface, `@polar-sh/sdk` dated import path — the versioned subpath may have rolled past `2026-10`).
- Deprecated config keys in `nuxt.config.ts` flagged by prepare warnings.

Fix what's broken the way the spine intends — patterns live in `./references/spine-manifest.md` — rather than deleting modules to make errors go away. Only fall back to disabling a module with the user's consent.

**Progression:** install clean, `.env` present, `.nuxt` prepared → `./references/04-verify.md`.
