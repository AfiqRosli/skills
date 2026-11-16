# Stage 2 — Scaffold

**Prerequisite:** intake inputs confirmed.

Render the template into the target:

```bash
python3 scripts/scaffold.py <target> --name "<name>" --site-url "<url>" [--minimal] [--skip <mod>...] [--force] --verbose
```

The script is the single source of truth for the render — `scripts/scaffold.py --help` documents the mechanics; `references/flags.md` and `assets/flags.json` hold them for the manual fallback.

**Graceful degradation:** if Python cannot run, do the same job by hand — read `assets/flags.json` for the excluded-path/dep maps, substitute tokens yourself, and delete flag-marked regions. The outcome is identical; the script is just faster and exact.

Review the JSON report: `files_written`, `files_excluded`, `flag_lines_removed`, `warnings`, and `residue` — the script scans every written file for surviving `{{…}}` tokens or `@flag` markers and fails loudly (status `warning`) if any leak through. Investigate residue before proceeding; it means a template bug or typo'd marker.

The same report is persisted into `<target>/.scaffold-report.json` — the state artifact a later session or pipeline step uses to resume. `python3 scripts/scaffold.py <target> --status` reads it back plus key files and reports where the run stands.

**Progression:** report clean → `references/wire.md`.
