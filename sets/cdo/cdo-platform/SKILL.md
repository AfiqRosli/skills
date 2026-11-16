---
name: 'cdo-platform'
description: 'Release engineering for the cdo pipeline. Use when the user requests to "ship this", "deploy", "check env vars", "roll back a story", "start a new sprint", "bump version", or runs release capabilities of the cdo pipeline.'
---

# cdo-platform — Platform & Release Engineering

## Overview

The release lane. Verified work lands on `{ship_target}`'s local integration ref `cdo-lane` — never pushed per story. The origin push is a separate Operator-gated leg (`## Pre-deploy Sign-offs` → `push`); production always files a Deploy Sign-off for the Operator. Owns credential logistics (real vs TEMP-CDO placeholders vs missing) and abort-safe reverts of shipped work.

**Args:** `ship {key}` · `push` · `env-check` · `rollback {key}` · `version-upgrade` · `produce {key}` · `consult {question}` · `setup` · `--headless`/`-H` — emits the invoked capability's output JSON verbatim; gates hold as machine-readable refusals (unverified ship, unsigned push, prod asks → `blocked` + reason, never prompt). `consult -H` is presentation-only.

## Role

Act as the release officer: the lane boundary is absolute, every ship is journaled, a revert never rewrites history.

## Resolution rules

- Bare paths and `{skill-root}` resolve from this skill's installed directory.
- `{project-root}` → the project working directory.
- `{orchestration_dir}` / `{orch}` → the cdo state dir (`{project-root}/docs/orchestration` unless `cdo:` config overrides).

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`, `{ship_target}`). Missing → `cdo-setup`.
2. Verify registration — `scripts/setup.py --check` reports `{registered}`. Missing → `scripts/setup.py`.
3. `{ship_target}` other than `preview` → production asks file `## Deploy Sign-offs` items, never execute.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `scripts/setup.py` | install — seed backlog, register capabilities |
| `ship {key}` | `references/ship.md` | verified → local lane landing (prod → sign-off only) |
| `push` | `references/push.md` | signed `## Pre-deploy Sign-offs` → `push-lane.py` → origin publish |
| `env-check` | `references/env-check.md` | `env-scan.py` coverage → requisitions + temp-placeholder flags |
| `rollback {key}` | `references/rollback.md` | revert the story's commit + journal |
| `version-upgrade` | `references/version-upgrade.md` | Operator sprint-start → delegate to `cdo-version-upgrade` (migrate non-done stories, archive sprint artifacts) |
| `produce {key}` | `references/produce.md` | execute the confirmed platform item + journal |
| `consult {…}` / no args | `references/consult.md` | office-hours — advisory, read-only, notes → `consult/platform.md` (method sources: `wdl-release-it`, `wdl-improve-app`) |

**Devlog:** when the pipeline's `produce` capability invokes this dept under `cdo-batch`, the caller passes a devlog dir — journal the work's decision entries to it (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`). The ship leg's lane/commit outcome is already journaled by the batch worker — don't double-log it here.