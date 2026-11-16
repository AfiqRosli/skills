---
name: 'cdo-delivery'
description: 'Agile Delivery Office — builds topo-ordered batch manifests from the confirmed pool and computes takt metrics (throughput, cycle time, attempt burn, quarantine rate). Use when the user requests to "plan the batch", "reorder the manifest", "delivery metrics", or Marshal invokes planning on FRAGO events.'
---

# cdo-delivery — Agile Delivery Office

## Overview

The planning desk. Turns the confirmed pool into an ordered batch manifest (`deps:` aware, cycle-detecting) and keeps the org's honest scoreboard — takt metrics derived from the ledger, never hand-tallied.

**Args:** `plan [--batch-id {id}] [--replan]` · `metrics` · `consult {question}` · `setup` · `--headless`/`-H` (pure JSON — pipeline-invoked)

## Role

Act as the agile lead: ordering is evidence (`deps:`) not opinion; a cycle is a report, not a guess; metrics are derived, never vibes.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-delivery`. Missing → `./scripts/setup.py`.

4. Method sources — `wdl-lean-analytics`, `wdl-traction-eos`, `wdl-high-output-management`, `wdl-team-topologies` per `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — seed backlog, register capabilities |
| `plan` | `./references/plan.md` | confirmed pool → `batch.manifest` (topo, cycle-safe, replan-aware) |
| `metrics` | `./references/metrics.md` | ledger → takt digest (cycle, attempts, quarantine rate, throughput) |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/delivery.md` |

**Devlog:** when the pipeline's `produce` capability invokes this dept under `cdo-batch`, the caller passes a devlog dir — journal the work's decision entries to it (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`).