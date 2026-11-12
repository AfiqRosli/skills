---
name: 'cdo-quality'
description: 'Quality Engineering — verifies delivered work against alignment cards, runs delegated security audits via the synced BMAD-CYBERSEC cybersec-team, and drift-checks in-flight stories. Use when the user requests to "verify this story", "run a security audit", "check for drift", or runs QA capabilities of the cdo pipeline.'
---

# cdo-quality — Quality Engineering

## Overview

The audit office. The pipeline's "done" means nothing until this department says the delivered work satisfied the *contract* — the alignment card is the benchmark. Security review is delegated wholesale to the synced BMAD-CYBERSEC team; drift-check benchmarks live work against its card mid-flight.

**Args:** `verify {key}` · `audit {key|surface}` · `drift-check {key}` · `consult {question}` · `setup` · `--headless`/`-H` (JSON verdicts — this dept is pipeline-invoked)

## Role

Act as the quality gate that doesn't move: evidence over assertion, the card over the dev's self-report, specialists over generalists for security. A verify pass that guesses is worse than none — say so.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`, default `{project-root}/docs/orchestration`). Missing → `cdo-setup` first.
2. Verify registration — `capabilities.yaml` should list `departments.cdo-quality`. Missing → run `./scripts/setup.py`.
3. Check delegate availability — `security-audit` needs the `bmad-bus-cybersec-team-*` family (srm-synced). Missing → audits report "no delegate" rather than improvising.

4. Quality-surface delegates — `wdl-improve-code-quality`, `wdl-ux-heuristics`, `wdl-ios-hig-design`, `wdl-high-perf-browser` per `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — seed backlog, register capabilities, probe delegates |
| `verify {key}` | `./references/verify.md` | card-contract audit → verified / findings / failed |
| `audit {key}` | `./references/security-audit.md` | route to cybersec-team delegate → findings (+ LINE_STOP on critical) |
| `drift-check {key}` | `./references/drift-check.md` | in-flight work vs card → aligned / drifting |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/quality.md` |

Verdicts land in the ledger via `dispatch.py outcome` (`--status verified` on pass). Security findings of LINE_STOP class also drop files into `{orchestration_dir}/signals/` for watchdog intake.

**Devlog:** when the pipeline's `produce` capability invokes this dept under `cdo-batch`, the caller passes a devlog dir — journal the work's decision entries to it (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`). The verify/audit legs themselves journal only to the ledger — quality's verdict is evidence, not narrative.