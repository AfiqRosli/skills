---
name: 'cdo-academy'
description: 'Learning & Capability — dissects shipped work into knowledge chains (fundamentals through advanced), gap-checks coverage against the academy catalog, and authors curriculum modules for confirmed gaps. Use when the user requests "extract knowledge", "check curriculum gaps", "author a course", or runs the learning leg of the cdo pipeline.'
---

# cdo-academy — Learning & Capability

## Overview

The L&D office: shipped work is evidence of what the org needed to know. This
department dissects each delivered story into the full knowledge chain a
zero-IT person would need to produce it — fundamentals through advanced —
diffs that against the academy's curriculum map (`docs/academy/catalog.yaml`),
and turns confirmed gaps into course modules. The org's own Coursera, fed by
its own work, growing toward beginner-to-expert coverage of every technology
the product touches.

**Args:** `extract {key}` · `gap-check` · `produce {key}` · `consult {question}` · `setup` · `--headless`/`-H`

## Role

Act as the curriculum lead: knowledge is what was *needed to produce the
output*, not what was produced; the prerequisite chain is the gold; a thin
extraction is honest — manufacturing curriculum is not.

## Layout

| Where | What |
|---|---|
| `docs/academy/` | the public platform — `catalog.yaml`, `{track}/{course}/NN-module.md`, index pages |
| `{orchestration_dir}/learning/knowledge/` | per-story concept extractions (ops evidence) |
| `{orchestration_dir}/learning/cases/` | continuity's forensic files — not the academy's |
| `{orchestration_dir}/backlogs/curriculum.md` | the education queue |

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section →
   `{orchestration_dir}`, `{academy_dir}` default `{project-root}/docs/academy`).
   Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-academy`.
   Missing → `./scripts/setup.py`.
3. Curriculum backbone — synced wdl-* frameworks are pre-validated course
   sources for gap-check/produce (`delegates_probe` lists which exist).

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — academy tree, knowledge dir, curriculum backlog, manifest |
| `extract {key}` | `./references/extract.md` | story → concept chain → `learning/knowledge/{key}.yaml` |
| `gap-check` | `./references/gap-check.md` | coverage pass vs `academy/catalog.yaml` → `catalog.py file-gap` → curriculum backlog |
| `produce {key}` | `./references/produce.md` | confirmed item → `academy/{track}/{course}/NN-module.md` + `catalog.py add` |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/academy.md` |
