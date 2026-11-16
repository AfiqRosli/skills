---
name: 'cdo-handoff'
description: 'Writes and reads the shift handover — the file that lets a fresh Marshal instance cold-start mid-operation without devlog archeology. Use when the user requests to "write the handover", "end the shift", "resume the operation", or when closing any cdo session with live state.'
---

# cdo-handoff

## Overview

Sessions end; operations don't. `handover.md` is the single artifact that carries a running operation across Marshal instances — what's in flight, what's pending, what happened, what happens next. Write it at every batch boundary, story end, and session close; read it before anything else at wake.

**Args:** `write [--summary "..."] [--next-action "..."]` · `read` — one invocation does one direction

**Your output:** on write — a regenerated `handover.md` from live state. On read — a JSON resume payload with freshness + integrity checks.

## On Activation

Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}` default `{project-root}/docs/orchestration`). Missing → `cdo-setup`.

## Write

```bash
uv run ./scripts/handover.py --orchestration-dir "{orch}" write \
    --summary "{one-line session narrative}" --next-action "{the next right move}"
```

The script rebuilds `handover.md` from live state — batch snapshot, pool counts, quarantined + open signals under Open Escalations, unchecked checklist items under Pending Operator Items. `--next-action` is optional; omitting it infers from state (in-flight → monitor, confirmed pending → dispatch, empty pool → align).

**Write it when state changes materially:** dispatch claimed, story outcome recorded, escalation raised, batch ended, session closing. A stale handover is worse than none — it actively misinforms the next shift.

## Read

```bash
uv run ./scripts/handover.py --orchestration-dir "{orch}" read
```

Returns `{status, age_minutes, in_flight, escalations, pending_ceo, next_action, integrity_anomalies}`. `integrity_anomalies` non-empty means the handover claims state the ledger disagrees with — treat the ledger as truth and regenerate rather than trusting the stale story.

## Rules

- **The handover serves a stranger.** The next Marshal instance knows only this file — write for someone with zero context, in ops-crisp language.
- **Read before you act, always.** Marshal's activation reads this first; a skipped read is a blind resume.
- **Narrative is your layer, state is the script's.** `--summary` carries the why; the script carries the facts. Don't paste the ledger into the summary.
