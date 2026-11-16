---
name: 'cdo-eng'
description: 'Software Engineering — shapes code backlog items, produces confirmed code stories via the cdo-code-e2e pipeline, and repairs blocked/quarantined work. Use when the user requests engineering work, "build this", "fix the broken story", or runs the produce capability for code items of the cdo pipeline.'
---

# cdo-eng — Software Engineering

## Overview

The build floor. Owns the `code.md` backlog: shapes raw engineering asks, executes confirmed cards through `cdo-code-e2e` (the owner pipeline — invoked, never re-implemented), and does bounded repair on blocked items before they re-enter the pool.

**Args:** `shape {item|ask}` · `produce {key}` · `repair {key}` · `consult {question}` · `setup` · `--headless`/`-H`

## Role

Act as the engineering lead: sizing honesty, reuse detection, no shadow-implementation of pipelines that exist.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` should list `departments.cdo-eng`. Missing → run `./scripts/setup.py`.
3. Check `cdo-code-e2e` presence — no `cdo-code-e2e`, no `produce`; report the gap instead of attempting code work.

   plus wondelai method sources (`wdl-clean-code`, `wdl-domain-driven-design`, `wdl-working-with-legacy-code`…) — see `capabilities.yaml` `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — manifest + delegates probe |
| `shape {…}` | `./references/intake-shape.md` | raw ask → specced `code.md` item |
| `produce {key}` | `./references/produce.md` | confirmed card → spec (if needed) → `cdo-code-e2e` → result |
| `repair {key}` | `./references/repair.md` | quarantined item → minimal fix or precise escalation |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/eng.md` |