# Stage 1 — Intake

**Prerequisite:** `./references/spine-manifest.md` read.

Lock down the render inputs before touching anything:

- **Target directory** — where the project goes (default: current working directory). If it's non-empty, surface that — scaffolding into a populated tree needs an explicit `--force` decision from the user.
- **Project name** — display name (drives `{{PROJECT_NAME}}` and slugifies into `{{PROJECT_SLUG}}` for package.json). Default: target directory name.
- **Site URL** — canonical origin for `site.url`, CORS, trusted origins. Default: `http://localhost:3000` for dev scaffolds.
- **Module set** — the full spine by default. Apply `--minimal` or `--skip-<module>` per the user's ask; resolve implications with `./references/flags.md` (auth needs db; billing needs auth — disabling a requirement cascades to its dependents).

Preview the resolution deterministically before confirming:

```bash
python3 ./scripts/scaffold.py <target> --name "<name>" --site-url "<url>" [--minimal] [--skip <mod>...] --dry-run
```

Present the module split (enabled / disabled / auto-disabled) and the target directory state, then confirm with the user — unless headless flags were given, in which case proceed.

**Progression:** inputs confirmed → `./references/02-scaffold.md`.
