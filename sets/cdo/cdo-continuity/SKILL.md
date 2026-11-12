---
name: 'cdo-continuity'
description: 'Continuity & Recovery Office — assembles forensic case files for killed/failed work, reconciles operational state after crashes, and coordinates incident response via the synced cybersec IR team. Use when the user requests "what happened to story X", "recover state", "declare an incident", or runs recovery capabilities of the cdo pipeline.'
---

# cdo-continuity — Continuity & Recovery Office

## Overview

The office that exists for the bad days: forensics that assemble evidence instead of relying on memory, recovery that repairs state without resuming work it wasn't asked to, and incident response delegated wholesale to the cybersec IR family.

**Args:** `forensic {key}` · `recover` · `incident {scope}` · `consult {question}` · `setup` · `--headless`/`-H`

## Role

Act as the continuity officer: assemble before you analyze, journal before you close, and never improvise incident response.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-continuity`. Missing → `./scripts/setup.py`.
3. IR delegates (`bmad-bus-cybersec-team-incident-*`) absent → `incident` escalates straight to Operator rather than faking a response.

4. Recovery method sources — `wdl-release-it`, `wdl-working-with-legacy-code` per `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — cases dir, backlog, manifest, IR probe |
| `forensic {key}` | `./references/forensic.md` | `case-file.py` assembles evidence → `learning/cases/` → doctrine update |
| `recover` | `./references/recover.md` | integrity scan → repair orphaned state → journaled report |
| `incident` | `./references/incident.md` | declare + route to IR delegates (or escalate if absent) |
| `produce {key}` | `./references/produce.md` | execute the confirmed continuity item (runbook/drill/hardening) + journal |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/continuity.md` |

**Devlog:** when the pipeline's `produce` capability invokes this dept under `cdo-batch`, the caller passes a devlog dir — journal the work's decision entries to it (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`).