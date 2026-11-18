---
name: 'cdo-setup'
description: 'Installs and configures the Autonomous Delivery Org (cdo) module in a project. Use when the user requests to "install cdo", "setup cdo", "configure the delivery org", or "upgrade cdo".'
---

# cdo-setup

## Overview

Installs, configures, and upgrades the `cdo` module — the orchestration layer of the Autonomous Delivery Org family. Department modules (`cdo-product`, `cdo-growth`, `cdo-academy`, `cdo-continuity`, …) install separately; this skill registers whichever it finds.

Every deterministic step runs through `scripts/` — same inputs, same outputs. Your judgment is reserved for what the scripts cannot decide: presenting the detected state and the proposal table, and resolving values the project can't supply itself.

Act as an infrastructure installer with an ops mindset: verify prerequisites honestly, leave the project better-organized than found, and report exactly what happened.

## Resolution rules

- Bare paths and `{skill-root}` (e.g. `scripts/detect.py`, `assets/module.yaml`) resolve from this skill's installed directory — including bare path values inside `customize.toml`.
- `{project-root}` → the project working directory. Resolve it in every filesystem **argument**; inside config **values** it stays a literal token (`merge-config.py` expands it).
- `{name}-resolved` → that value with `{project-root}` substituted for the real path.
- `{temp}` → a scratch dir you create (`mktemp -d` or equivalent) for detect/answers/report JSON.
- `{workflow.<name>}` → the resolved `customize.toml` value for `<name>`.

**Args:**
- `--headless` / `-H` — proposal accepted as-is, no prompts; every assumed value is memlogged
- `upgrade` — force the upgrade branch regardless of detection
- `--set key=value` / `--core-set key=value` (repeatable) — override a config value; unknown keys refuse

**Your output:** a ready-to-run orchestration home, a `cdo` section in `{project-root}/_bmad/config.yaml`, help-system registration, and a setup report.

## On Activation

1. Resolve customization: `uv run {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --project-root {project-root} --key workflow` → `{workflow.*}` values. No resolver → read `customize.toml` directly.
2. Read `assets/module.yaml` for module identity and variable definitions. It is the cdo module's install manifest — its values land in `{project-root}/_bmad/config.yaml`; it is not this skill's customization surface (`customize.toml` is).
3. Run the deterministic pre-pass — it emits one JSON blob: hard prerequisites, soft deps, detected conventions, prior-install state, ship-lane topology (`git_lane`), the stored `cdo:` config verbatim (`prior_cdo_config`), and a `gate` verdict:

   ```bash
   uv run scripts/detect.py --project-root "{project-root-resolved}" -o {temp}/detect.json
   ```

   If `uv`/`python` is unavailable, perform the equivalent checks by hand (see `detect.py --help`) — batch the probes, don't serialize them.

4. **Prerequisite gate.** Hard requirements: a git repo AND an official BMAD install (`{project-root}/_bmad/config.yaml` with real module sections — a stub fails). The module's whole model assumes BMAD conventions, so setup refuses rather than silently degrades when the foundation isn't there: halt, report what must exist first; in `--headless` emit `{"status": "blocked", "reason": "...", "missing": [...]}`. Soft deps (`cdo-code-e2e`, wiretext MCP, `cdo-*` dept modules) → warn and continue, registering each as a gap. Surface detection `warnings`.

5. **Mode.** `upgrade` when detection finds a prior install — or whenever the `upgrade` arg is passed, even with no prior install (a fresh tree under upgrade mode just repairs/scaffolds; note it, don't refuse). Otherwise `fresh-install`. State the decision before proceeding.

Open with one breath of orientation — what this writes (orchestration tree, config section, help CSV, ship lane) and roughly how long — then move to the proposal table.

## Collect Configuration

Build the proposed config **with the script**, not by hand — it layers `--set` overrides > stored prior config > detected values > `module.yaml` defaults, derives `backlog_map` from detected dept modules, and emits both a human table and the answers JSON (plus `answers.json.report.json` — the per-value source trail):

```bash
uv run scripts/propose-config.py --detect {temp}/detect.json --module-yaml assets/module.yaml [--set key=value] [--core-set key=value] -o {temp}/answers.json
```

Present the `proposed` table — one amendable summary ("all fine" or a list of changes). Never interview variable-by-variable. If they amend, re-run with `--set` per change. In `--headless`, the proposal IS the answers — append an `assumption` memlog entry per defaulted value via `{project-root}/_bmad/scripts/memlog.py`.

Notes:
- Core config keys (`user_name`, `communication_language`, `document_output_language`, `output_folder`) already in `{project-root}/_bmad/config.yaml` are protected automatically — `detect` reports them as `core_keys_present` and `propose-config` omits the core block (pass `--core-set` to deliberately change one).
- `ship_target` default is `preview` — intentional; production stays Operator-gated. Don't offer to change it silently.
- If detection found no sprint yaml / story dir / devlog dir, say so on the row rather than letting a silent default hide it.

## Write & Scaffold

**Scaffold** the orchestration tree — idempotent; existing files are never overwritten; `--answers` supplies the orchestration dir, the dept `backlog_map`, and the configured directories to create. These three calls write to disjoint targets and may run in parallel:

```bash
uv run scripts/scaffold.py --project-root "{project-root-resolved}" --answers {temp}/answers.json --module-yaml assets/module.yaml --report {temp}/answers.json.report.json --mode "{mode}" --seeds "{workflow.seeds_dir}"
uv run scripts/merge-config.py --config-path "{project-root}/_bmad/config.yaml" --user-config-path "{project-root}/_bmad/config.user.yaml" --module-yaml assets/module.yaml --answers {temp}/answers.json --legacy-dir "{project-root}/_bmad"
uv run scripts/merge-help-csv.py --target "{project-root}/_bmad/module-help.csv" --source "{workflow.module_help_source}" --legacy-dir "{project-root}/_bmad" --module-code cdo --detect {temp}/detect.json
```

`merge-config.py` preserves stored keys the answers don't redefine — an upgrade repairs, never deletes a hand-tuned value. `merge-help-csv.py` registers only skills detection actually found — unbuilt siblings aren't advertised. `scaffold.py` also copies the proposal report to `setup-report.json` beside the setup log — which values were overridden, stored, detected, or defaulted stays recoverable after `{temp}` is gone. All emit JSON; on non-zero exit, surface the error and stop.

**Lane setup** — make the `ship_target` branch real:

```bash
uv run scripts/ensure-lane.py --project-root "{project-root-resolved}" --answers {temp}/answers.json
```

Every status is a successful outcome, not an error — ship work lands on the lane via push, so an unswitched checkout is fine. On `deferred` (zero-commit repo), record a gap: create the lane after the first commit.

## Report

Close with a setup report:

- **Created** — directories and seeded files
- **Configured** — the written config table (or what changed on upgrade — call out preserved values)
- **Registered** — help rows actually written + department modules discovered with their backlog files
- **Lane** — ship-lane result (`created_and_switched` / `exists` / `deferred` with reason)
- **Gaps** — missing soft deps with how to fill them (e.g., install `cdo-code-e2e` before code batches; create the `{ship_target}` lane after the first commit when deferred)
- **Next** — "Talk to `cdo-orchestrator` to run your first batch" — or a readiness checklist when the gate was partial
- **Commit** — offer to `git add` the orchestration tree + config

When `{workflow.on_complete}` is set, execute it now.

**Headless contract.** Never commit in `--headless` — report `"commit": "pending"` and let the caller decide. Memlog every assumption made without the user (mode, defaulted values, lane action, registered gaps) through `{project-root}/_bmad/scripts/memlog.py` as it happens. Return minimal JSON:

```json
{"status": "complete|blocked", "mode": "installed|upgraded", "commit": "pending",
 "paths": {"orchestration": "…", "setup_log": "…/setup-log.md",
          "setup_report": "…/setup-report.json", "memlog": "…/memlog.md"}}
```

On `blocked`, include a one-line `reason` and still return the memlog path.

## No Python/uv Fallback

The scripts are the preferred path; a missing interpreter gets a **partial** install, not an equivalent one — the merge contract (result templates, metadata keys, legacy fallback, core-key migration, user-setting split) lives in the scripts and is not reproduced here. Do:

- **Detection** — the checks in `detect.py --help` done by glob/read.
- **Scaffold** — `mkdir -p` the tree; copy each seed from `assets/seeds/` only when the target is absent.
- **Config write** — replace the `cdo:` section in `{project-root}/_bmad/config.yaml` wholesale, but first carry any existing keys into the new section (preserve what you don't recognize); write `user_name`/`communication_language` to `config.user.yaml` instead.
- **Help CSV** — append rows from `assets/module-help.csv` for installed skills only; remove stale `cdo` rows first.
- **Lane** — `git switch -c {ship_target}` when the repo has commits, the lane is missing, and the checkout sits on the default branch; `git branch {ship_target} {default-branch}` when mid-feature; skip entirely on a zero-commit repo.

Then report the install **incomplete** — the full config merge and lane bookkeeping still owe a Python run (`merge-config.py`, `merge-help-csv.py`, `ensure-lane.py`). Do not claim a finished install.
