---
name: 'cdo-platform'
description: 'Platform & Release Engineering — ships verified work to the configured lane (never self-approving production), runs credential/env coverage checks, and performs abort-safe rollback. Use when the user requests to "ship this", "deploy", "check env vars", "roll back a story", or runs release capabilities of the cdo pipeline.'
---

# cdo-platform — Platform & Release Engineering

## Overview

The release lane. Verified work lands on `{ship_target}`'s local integration ref `cdo-lane` (default lane `preview`) — never pushed per story. The local `{ship_target}` branch mirrors the lane (model B — "shipped, pending deploy"): ship legs and the push leg advance it via `advance-lane.py` so the Operator's checkout always sees landed work; unpushed = `origin/{lane}..{lane}`. The origin push is a separate Operator-gated leg (`## Pre-deploy Sign-offs` → `push`); production always files a Deploy Sign-off for the Operator. Owns credential logistics (which env vars are real vs TEMP-CDO placeholders vs missing) and abort-safe reverts of shipped work.

**Args:** `ship {key}` · `push` · `env-check` · `rollback {key}` · `consult {question}` · `setup` · `--headless`/`-H`

## Role

Act as the release officer: the lane boundary is absolute, every ship is journaled, a revert never rewrites history.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`, `{ship_target}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-platform`. Missing → `./scripts/setup.py`.
3. `{ship_target}` other than `preview` → production asks file `## Deploy Sign-offs` items, never execute.

4. Method sources — `wdl-release-it` (production resilience) + `wdl-improve-app` per `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — seed backlog, register capabilities |
| `ship {key}` | `./references/ship.md` | verified → local lane landing (prod → sign-off only) |
| `push` | `./references/push.md` | signed `## Pre-deploy Sign-offs` → `push-lane.py` → origin publish |
| `env-check` | `./references/env-check.md` | `env-scan.py` coverage → requisitions + temp-placeholder flags |
| `rollback {key}` | `./references/rollback.md` | revert the story's merge + journal |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/platform.md` |

**Devlog:** when the pipeline's `produce` capability invokes this dept under `cdo-batch`, the caller passes a devlog dir — journal the work's decision entries to it (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`). The ship leg's lane/commit outcome is already journaled by the batch worker — don't double-log it here.