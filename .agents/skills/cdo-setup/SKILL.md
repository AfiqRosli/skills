---
name: 'cdo-setup'
description: 'Installs and configures the Autonomous Delivery Org (cdo) module in a project. Use when the user requests to "install cdo", "setup cdo", "configure the delivery org", or "upgrade cdo".'
---

# cdo-setup

## Overview

Installs, configures, and upgrades the `cdo` module — the orchestration layer of the Autonomous Delivery Org family. Department modules (`cdo-product`, `cdo-growth`, `cdo-academy`, `cdo-continuity`, …) install separately; this skill registers whichever it finds.

**Scaffold-first, then adapt:** the module creates the `docs/orchestration/` tree it expects rather than reshaping itself per repo — consistent behavior across every project, with detected conventions filling in config. A second run detects the prior install and repairs/upgrades instead of duplicating.

Act as an infrastructure installer with an ops mindset: verify prerequisites honestly, leave the project better-organized than found, and report exactly what happened.

**Args:**
- `--headless` / `-H` — detected defaults, no prompting; halts on missing hard prerequisites
- `upgrade` — force the upgrade path
- `--set key=value` (repeatable) — set a module config value directly; inline prose (`orchestration_dir is docs/ops`) also accepted

**Your output:** a ready-to-run orchestration home, a `cdo` section in `{project-root}/_bmad/config.yaml`, help-system registration, and a setup report — created / configured / registered / gaps.

## On Activation

Before anything else, two lines of orientation for first-timers: *"This scaffolds the orchestration tree under `docs/orchestration/`, writes a `cdo` config section into `{project-root}/_bmad/config.yaml`, and registers capabilities with the help system — takes about a minute."* Then invite questions about any row of the upcoming config table.

Run these together in one pass:

1. Read `./assets/module.yaml` for module identity and variable definitions.
2. Run the deterministic pre-pass — it emits one JSON blob: hard prerequisites, soft deps, detected conventions, prior-install state, ship-lane branch topology (`git_lane`), **the stored `cdo:` config section verbatim** (`prior_cdo_config`), and a `gate` verdict:

   ```bash
   uv run ./scripts/detect.py --project-root "{project-root-resolved}" -o {temp}/detect.json
   ```

   If `uv`/`python` is unavailable, perform the equivalent checks by hand (see `detect.py --help` for what it scans) — batch the probes, don't serialize them.

3. **Prerequisite gate.** Hard requirements: a git repo AND an official BMAD install (`{project-root}/_bmad/config.yaml` with real module sections — a stub file fails). Missing either → halt and report what must exist first; in `--headless` emit `{"status": "blocked", "missing": [...]}`. Soft deps (`cdo-code-e2e`, other owner skills, wiretext MCP, `cdo-*` dept modules) → warn and continue, registering each as a gap. Surface any `warnings` from detection (stub config, dual TOML/YAML ambiguity).
4. **Fresh install vs upgrade.** `prior_install` or `orchestration_trees_found` → upgrade: stored values and detected state become the proposal defaults; repair only what's missing. Otherwise fresh install. State the decision before proceeding.

## Collect Configuration

Build the proposed config **with the script**, not by hand — it layers `--set` overrides > stored prior config > detected values > `module.yaml` defaults, derives `backlog_map` from detected dept modules, and emits both a human table and the answers JSON:

```bash
uv run ./scripts/propose-config.py --detect {temp}/detect.json --module-yaml ./assets/module.yaml -o {temp}/answers.json
```

Present the `proposed` table to the user — one amendable summary ("all fine" or a list of changes). Never interview variable-by-variable. If they amend, re-run with `--set key=value` per change. In `--headless`, the proposal IS the answers (still honor any `--set` args).

Notes:
- Core config keys (`user_name`, `communication_language`, `document_output_language`, `output_folder`) already in `{project-root}/_bmad/config.yaml` are protected automatically — `detect` reports them as `core_keys_present` and `propose-config` omits the core block (pass `--core-set` to deliberately change one). `--no-core` remains as an explicit override.
- `ship_target` default is `preview` — intentional; production stays Operator-gated. Don't offer to change it silently.
- If detection found no sprint yaml / story dir / devlog dir, say so on the row rather than letting a silent default hide it.

## Write & Scaffold

Resolve `{project-root}` to the real path in every path argument — the token stays literal only inside config *values*.

1. **Scaffold** the orchestration tree — idempotent; existing files are never overwritten; dept backlogs seed only for installed dept modules. These three calls write to disjoint targets and may run in parallel:

   ```bash
   uv run ./scripts/scaffold.py --project-root "{project-root-resolved}" --orchestration-dir "{orchestration_dir-resolved}" --dept-modules "{comma-separated dept modules from detection}" --version "0.1.0" --mode "{fresh-install|upgrade}"
   uv run ./scripts/merge-config.py --config-path "{project-root}/_bmad/config.yaml" --user-config-path "{project-root}/_bmad/config.user.yaml" --module-yaml ./assets/module.yaml --answers {temp}/answers.json --legacy-dir "{project-root}/_bmad"
   uv run ./scripts/merge-help-csv.py --target "{project-root}/_bmad/module-help.csv" --source ./assets/module-help.csv --legacy-dir "{project-root}/_bmad" --module-code cdo --installed-dirs "{project-root}/.agents/skills,{project-root}/skills,{project-root}/.devin/skills"
   ```

   `merge-config.py` preserves stored keys the answers don't redefine — an upgrade repairs, never deletes a hand-tuned value. `merge-help-csv.py` with `--installed-dirs` registers only skills that exist on disk — unbuilt siblings aren't advertised. All emit JSON; on non-zero exit, surface the error and stop.

2. **Create configured directories** that don't exist yet — resolve `{project-root}` for filesystem paths only; the stored config keeps the literal token.

3. **Lane setup** — make the `ship_target` branch real. Run once config is resolved:

   ```bash
   uv run ./scripts/ensure-lane.py --project-root "{project-root-resolved}" --lane "{ship_target}"
   ```

   The org's ship model needs the lane to exist: automation commits land on `ship_target` (default `preview`), production refs stay Operator-gated. Interpret the JSON status:

   - `created_and_switched` — the checkout now sits on the lane (or a local branch tracking the single remote lane). The common path on a repo sitting on `main`.
   - `created_not_switched` — lane created at the default branch (or remote lane) but the checkout stays put: user was mid-feature on another branch, or `--no-switch` was passed. Ship work still lands correctly — lanes are pushed, not sat on.
   - `already_on_lane` / `exists_not_checked_out` — nothing to do; report which.
   - `deferred` — zero-commit repo; a branch can't point at an unborn HEAD. Record a gap: create the lane after the first commit (the greenfield scaffold's wire stage is the usual producer of it).

   Never force-create over an existing lane and never switch the user's checkout when they're mid-feature.

## Report

Close with a setup report:

- **Created** — directories and seeded files
- **Configured** — the written config table (or what changed on upgrade — call out preserved values)
- **Registered** — help rows actually written + department modules discovered with their backlog files
- **Lane** — ship-lane result (`created_and_switched` / `exists` / `deferred` with reason)
- **Gaps** — missing soft deps with how to fill them (e.g., install `cdo-code-e2e` before code batches; register wiretext MCP for rendered Operator surfaces; create the `{ship_target}` lane after the first commit when deferred)
- **Next** — "Talk to `cdo-orchestrator` to run your first batch" — or a readiness checklist when the gate was partial
- **Commit** — offer to `git add` the orchestration tree + config (git is a hard prereq, so it's always available)

In `--headless`, emit the same report as JSON with `status` of `"installed"`, `"upgraded"`, or `"blocked"`.

## No Python/uv Fallback

The scripts are the preferred path, but a missing interpreter must not dead-end the install. Manual equivalents:

- **Detection** — the checks in `detect.py --help` done by glob/read.
- **Scaffold** — `mkdir -p` the tree; copy each seed from `./assets/seeds/` only when the target is absent.
- **Config write** — replace the `cdo:` section in `{project-root}/_bmad/config.yaml` wholesale, but first carry any existing keys into the new section (preserve what you don't recognize); write `user_name`/`communication_language` to `config.user.yaml` instead.
- **Help CSV** — append rows from `./assets/module-help.csv` for installed skills only; remove stale `cdo` rows first.
- **Lane** — `git switch -c {ship_target}` when the repo has commits, the lane is missing, and the checkout sits on the default branch; `git branch {ship_target} {default-branch}` when mid-feature on another branch; skip entirely on a zero-commit repo.

State clearly that the manual path was used — it's the exception, not the norm.

## Design Notes

- **Why gated:** the module's whole model assumes BMAD conventions (config, sprint artifacts, owner skills). Rather than silently degrading, setup refuses when the foundation isn't there.
- **Why scaffold-first:** predictable paths let `cdo-batch`, `cdo-watch`, and `cdo-handoff` make hard guarantees about state files — and every install behaves identically, so doctrine and ledgers port across projects.
- **Why detect-everything-then-confirm:** twelve questions is tedium; one proposed table the user amends is one touchpoint. Detection does the homework; the Operator signs off.
- **Why `propose-config.py`:** layering four value sources (overrides > stored > detected > defaults) is deterministic merge work — a script does it losslessly; a prompt would eventually drop a stored value.
