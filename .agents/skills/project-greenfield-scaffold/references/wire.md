# Stage 3 — Wire

**Prerequisite:** template rendered in the target.

Turn the file tree into a working repo, inside `<target>`:

1. `bun install` — resolve the pinned manifest. If `bun` is absent, use `npm install` and note it (the spine assumes bun: lockfile and netlify build command).
2. `python3 scripts/scaffold.py <target> --init-env` — creates `.env` from `.env.example` with a generated `BETTER_AUTH_SECRET` when the auth module is on (skips if `.env` exists). Leave all other vars at their placeholders unless the user provides real values. Placeholder env is the intended dev baseline — the app must boot and serve pages + non-DB routes on it. That only holds while external clients construct lazily: a `new X(apiKey)` at module load that throws on missing env is a template bug, not a config gap — fix the client, never mask it by requiring env.
   - `DATABASE_URL` placeholder is boot-safe (queries fail at request time only). `neon-http` needs a Neon-compatible endpoint — plain local Postgres won't work; a real Neon URL goes here when the user has one.
3. `git init` + first commit if the user wants version control — and only then `bunx husky` (or `bun run prepare`) to install git hooks. Skip husky when there's no git repo; it has nothing to hook into. In headless mode, do it — init + commit + husky is the default. One guard first: `git rev-parse --show-toplevel` inside `<target>` — a resolved root that isn't `<target>` means an enclosing repo already tracks it; skip init + husky, note it in the health report, and in headless `--record` it under `adaptations` instead of nesting a repo.
4. `bunx nuxt prepare` — generates `.nuxt` types; also the first real compatibility probe.

**Version-drift adaptation — this is where your judgment matters.** The manifest pins versions that were latest-stable at `resolved_at` in `versions.json`, but majors move. When a failure smells like a pinned-major problem, `python3 scripts/scaffold.py <target> --check-drift` emits pinned vs latest per dep as JSON — judge against that, not memory. Watch for:

- `nuxt-elysia` vs Nuxt 4 compatibility (it was authored for Nuxt 3 — if prepare/dev fails on it, check for a newer release or shim the module).
- Renamed/broken imports across the pinned majors (Vuetify 4 plugin API, Pinia 4, Vitest 5, better-auth surface, `@polar-sh/sdk` dated import path — the versioned subpath may have rolled past `2026-10`).
- Deprecated config keys in `nuxt.config.ts` flagged by prepare warnings.

Fix what's broken the way the spine intends — patterns live in `references/spine-manifest.md` — rather than deleting modules to make errors go away. Only fall back to disabling a module with the user's consent; in headless mode there is no user — never disable, attempt the spine-intended fix, and if none exists mark the run blocked and say so in the health report. Record each via `python3 scripts/scaffold.py <target> --record '{"adaptations": ["…"]}'` — the script owns that JSON write; a hand-edit can corrupt the resume artifact, and those calls were made without the user so they need a durable audit trail.

If Python can't run the script calls: `.env` by hand = copy `.env.example` → `.env` and substitute a generated hex for `generate-a-long-random-string`; drift check = compare `assets/versions.json` pins against the registry yourself; report records = append keys to `.scaffold-report.json` preserving the shape (lists append, scalars set) — the script only enforces that shape.

**Progression:** install clean, `.env` present, `.nuxt` prepared → `references/verify.md`.
