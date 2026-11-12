# Stage 1 — Intake

**Prerequisite:** `references/spine-manifest.md` read.

Lock down the render inputs before touching anything:

- **Target directory** — where the project goes (default: current working directory). If it's non-empty, surface that — scaffolding into a populated tree needs an explicit `--force` decision from the user.
- **Project name** — display name (drives `{{PROJECT_NAME}}` and slugifies into `{{PROJECT_SLUG}}` for package.json). Default: target directory name.
- **Site URL** — canonical origin for `site.url`, CORS, trusted origins. Default: `http://localhost:3000` for dev scaffolds.
- **Module set** — the full spine by default. If the user hasn't specified, ask what kind of project this is (public site, app with login, prototype) and propose the `--skip`/`--minimal` set from the answer — a landing page needs none of auth/db/billing/email/redis. The `--dry-run` output's `enabled`/`disabled`/`auto_disabled` lists are the authoritative cascade resolution — present them verbatim rather than resolving `requires` chains by hand from `references/flags.md`.

Preview the resolution deterministically before confirming:

```bash
python3 scripts/scaffold.py <target> --name "<name>" --site-url "<url>" [--minimal] [--skip <mod>...] --dry-run
```

Present the module split (enabled / disabled / auto-disabled) and the target directory state, then confirm with the user — unless headless flags were given, in which case proceed.

**Progression:** inputs confirmed → `references/scaffold.md`.
