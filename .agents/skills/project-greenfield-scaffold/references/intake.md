# Stage 1 — Intake

**Prerequisite:** `references/spine-manifest.md` read.

Lock down the render inputs before touching anything — and first, spine fit: if the request isn't a Nuxt 4 + Elysia full-stack web app (a CLI tool, a service on another framework, a static site), say so and stop; the spine doesn't adapt into a different platform.

- **Target directory** — where the project goes (default: current working directory). If it's non-empty, surface that — scaffolding into a populated tree needs an explicit `--force` decision from the user. `--force` re-renders and overwrites colliding files — it is not a merge; adding a module to an existing scaffold is a manual port (`references/flags.md` + flag blocks), not a re-run.
- **Project name** — display name (drives `{{PROJECT_NAME}}` and slugifies into `{{PROJECT_SLUG}}` for package.json). Default: target directory name.
- **Site URL** — canonical origin for `site.url`, CORS, trusted origins. Default: `http://localhost:3000` for dev scaffolds.
- **Module set** — the full spine by default. If the user hasn't specified, ask what kind of project this is (public site, app with login, prototype) and propose the `--skip`/`--minimal` set from the answer — a landing page needs none of auth/db/billing/email/redis. The `--dry-run` output's `enabled`/`disabled`/`auto_disabled` lists are the authoritative cascade resolution — present them verbatim rather than resolving `requires` chains by hand from `references/flags.md`.

Preview the resolution deterministically before confirming:

```bash
python3 scripts/scaffold.py <target> --name "<name>" --site-url "<url>" [--minimal] [--skip <mod>...] --dry-run
```

No Python? Resolve the cascade by hand from `references/flags.md` and present the split flagged as manually resolved — the render re-confirms the real cascade anyway (or is manual too, per `references/scaffold.md`'s fallback).

Present what the spine is — Nuxt 4 + Vuetify + Pinia + Elysia + Drizzle/better-auth on Netlify — alongside the module split (enabled / disabled / auto-disabled) and the target directory state, then confirm with the user — unless headless flags were given, in which case proceed.

**Progression:** inputs confirmed → `references/scaffold.md`.
