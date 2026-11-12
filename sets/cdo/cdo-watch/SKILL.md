---
name: 'cdo-watch'
description: 'The night-shift watchdog — time-based stall detection, LINE_STOP/frontline signal intake, cost-ceiling check, state-integrity audit, and between-batch janitorial. Designed to run headless on a schedule or inside Marshal''s wake. Use when the user requests to "check for stalls", "run the watchdog", "sweep signals", or "clean up the checklist".'
---

# cdo-watch

## Overview

The org's smoke detector and janitor. It *notices* — stalled steps, dropped signals, budget breaches, lying ledgers — and files signals for Marshal's duty-officer triage. It never fixes work; it makes trouble visible and keeps the floor clean between batches.

**Args:** `--mode scan|intake|resolve|janitor` (default `scan`; `resolve` needs `--key`) · `--headless`/`-H` (the native mode — watch is a reporting pass, output is JSON)

**Your output:** a JSON report — `signals` (things to triage), `anomalies` (integrity findings), `actions` (janitorial). Exit code 1 when there's attention-worthy content, 0 when clean.

## Role

Act as the night-shift inspector: you measure, you log, you flag. Judgment of *what the signs mean* belongs to the duty officer — you just guarantee the signs get seen.

## On Activation

Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}` default `{project-root}/docs/orchestration`, `stall_timeout_minutes`, `batch_budget`). Missing `cdo` section → route to `cdo-setup`, stop.

## Modes

```bash
uv run ./scripts/watch.py --orchestration-dir "{orch}" --mode {mode} \
    --stall-timeout-minutes {n} --batch-budget {n|unset}
```

- **`scan`** — the default pass. Stall detection is *purely time-based*: `step_started` vs `stall_timeout_minutes`, nothing fancier — signs get judged downstream. Also runs integrity checks (ledger parses and has its keys, checklist sections intact, each in-flight story holds its own `locks/{key}.lock`, drafts aren't orphaned from the checklist) and the cost ceiling. New signals append to `flow-ledger.yaml`'s `signals` for triage.
- **`intake`** — frontline agents (cdo-code-e2e, dept pipelines) drop LINE_STOP and other signals as files in `{orchestration_dir}/signals/`; this folds them into the ledger and consumes the files. Signal filename convention: `{kind}-{key}.md` (`line-stop-13-08-x.md`, `drift-P2.md`) — the key drives per-item dedupe, so a second LINE_STOP for a different story never wedges behind the first. Bodies archive to `signals/archive/` before removal — evidence survives.
- **`resolve --key K`** — the triage side: marks all open signals for K resolved (duty-officer does this after acting on a signal). Resolved signals stop deduping — a fresh stall re-fires.
- **`janitor`** — between-batch hygiene: prune resolved `- [x]` checklist lines (verdict-dated ones only, older than `--janitor-days` — an undated resolved line could be seconds old), break stale `locks/{key}.lock` files (>2× stall timeout = dead worker session; legacy `dispatch.lock` too), expire `g-*.lock` drain markers on terminal evidence (a pushed `sessions/drain.md` newer than the marker, or every member key already terminal — cloud drains can't remove their local-only lock) or the 24h TTL, sweep dead `.cdo-work/*` worktrees past the TTL (delegates to cdo-platform's `sweep-worktrees.py` — the shared implementation the verdict sweep also uses, without the TTL), drop resolved signals older than `--janitor-days`, leave fresh locks alone. Run when the pool is quiet — not mid-flight.

No Python → do the equivalent by hand: compare timestamps in the ledger, glob the signals dir, prune `[x]` lines — and note the manual pass.

## Reporting

The JSON is the contract — Marshal's `-H` wake and schedulers consume it. In interactive use, translate to one line each: `signal: stall on 13-08-x (78m at 'dev')`, `anomaly: draft 08-03-x not on checklist`, `action: broke stale lock`. Signals found = attention needed, so exit code 1 is a *result*, not a failure.

## Rules

- **Watch doesn't decide.** A stall signal is "elapsed > threshold"; whether it's a dead process or a long test suite is duty-officer judgment — report, don't retry.
- **Integrity findings are findings, not repairs.** If the ledger disagrees with reality, the answer is a surfaced anomaly, not a silent edit.
- **Cronable by design** — every mode is safe to run on a timer; worst case is a duplicate-free signal or a no-op.
