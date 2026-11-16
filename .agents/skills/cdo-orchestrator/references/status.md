# Capability: Status Brief

The Operator's at-a-glance answer to "where are we." Compose from `flow-ledger.yaml` + `alignment-checklist.md` + `handover.md` — these files are the org's state; you're rendering them, not re-deriving anything.

## What a brief contains

- **Batch** — id, progress (done/dispatched/queued/blocked), burn vs `{batch_budget}`
- **In-flight** — per-story workers: key, step, elapsed vs `{stall_timeout_minutes}` (one linear drain at a time)
- **Delivered pending** — `delivered_pending` count: terminal stories not yet given Marshal's fresh-eyes briefing
- **Wave** — `wave_pending`: batch drained but no holistic read filed yet
- **Intent drift** — `intent_stale`: doctrine moved past intent.md's stamp (the gates are judging off a stale position)
- **Confidence honesty** — `review_flag_rate_by_conf`: flag-rate per confidence band — whether the conf% on cards actually predicts clean delivery
- **Pool** — confirmed depth vs `{alignment_buffer_min}`, quarantined count with one-line reasons
- **Operator items** — pending checklist entries (alignment drafts + confidence, escalations, pre-deploy + deploy sign-offs, requisitions)
- **Signals** — open watchdog/LINE_STOP events
- **Next action** — the single thing that happens next

## Since last visit

When the Operator returns after an absence, the brief leads with a **delta**: what changed since the last handover — stories completed, kills, new escalations, items added to their checklist. The Operator shouldn't have to diff the org in their head.

## Rendering

When wiretext MCP is registered, render the board — kanban-style columns map to ledger states (queued / in-flight / blocked / done). Otherwise a compact markdown table. The brief is dense on purpose: the Operator skims it, asks nothing, or taps one row. Chat-length — if the brief needs scrolling, split: headline + detail on request.

## Headless contract

`-H:status` emits the digest fields as JSON: `batch`, `pool`, `in_flight`, `stalled_stories`, `delivered_pending`, `wave_pending`, `intent_stale`, `review_flag_rate_by_conf`, `signals_open`, `operator_items_pending`, `autonomy`, `integrity_anomalies` — the same fields `state-digest.py` produces. Scripted callers never parse prose.

## Discipline

Numbers from `state-digest.py`, not memory. If ledger and reality disagree (a stale entry, a missing session), say the ledger disagrees — that's a state-integrity finding for `cdo-watch`, not something to paper over.
