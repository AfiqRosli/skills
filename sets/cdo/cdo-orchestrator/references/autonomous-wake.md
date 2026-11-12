---
name: autonomous-wake
description: Default autonomous wake — runs on --headless/-H with no task; -H:status emits a read-only briefing.
---

# Autonomous Wake

You're running autonomously. No one is watching. Act within the authority envelope, write everything down, and exit.

## Context

- Orchestration home: `{orchestration_dir}/`
- Access boundaries: `./references/access-boundaries.md` (load on every wake — deny zones are load-bearing)
- Org narrative: `{orchestration_dir}/logs/chronology.md`
- Activation time: `{current-time}`

## Named task: `-H:status`

Read-only. Emit a status brief per `./references/status.md` (batch state, pool depth, pending Operator items, signals) and exit. Take no decisions, write no state except the autonomous log.

## Default Wake (`--headless`, no task)

The shift-change protocol:

1. **Resume** — read `handover.md` + `flow-ledger.yaml` + `intent.md`. Know what was in flight when the last shift ended, and what the org currently believes the business wants — if doctrine moved since intent's `Refreshed:` stamp, reconcile intent.md before anything else judges against it.
2. **Inbox** — process any FRAGO directives first (`./references/frago.md`) — Operator input never waits.
3. **Triage** — process watchdog/LINE_STOP signals and escalations per `./references/duty-officer.md`. Stall thresholds from config (`stall_timeout_minutes`).
4. **Advance the batch** — if nothing blocks, act per `./references/batch-supervision.md`: `ready-set.py` → **spawn ONE drain session for the whole `dispatch_now` list** (`--keys` — linear dispatch: one worker on the ship lane, no branches to merge) — unless a fresh drain lock already marks a live worker, in which case watch instead. Check the drain's post-outcome legs (`done`→verify, `verified`→ship, `shipped`→feed — workers drive them; you watch the seams); the drain self-mops reviews, or idles cleanly when the pool is empty — drains never self-align (explicit-command only). The post-ship feeds are `cdo-growth feed` + `cdo-docs feed` (docs candidates land on `backlogs/docs.md` as unaligned proposals, attempt-aware so re-attempted stories re-feed); a missing docs queue is a seam to nudge. Knowledge extraction is a manual leg — never auto-spawned; `pending-extract` tracks the debt (see below).
5. **Mop up delivered reviews** — shipped workers normally trigger their own review session (`r-{key}`, near-real-time). Run `delivery-note.py pending`: each key listed means a review never fired or died. Either `spawn-review {key}` to relaunch the auditor session, or file the assessment yourself — write `{key}.review-{attempt}.md` to the `alignment/reviews/` staging dir (evidence walked / promise vs delivered / findings / cross-story / recommendation — every claim cites a path or commit), then `delivery-note.py file {key} --verdict "sound|flagged:delivery-{x}|flagged:card-{x}|postmortem:{clean|hollow}" --note "{your read}" --doc "{that doc}"` — the doc stays staged; the Operator's verdict graduates it beside the card. Dual-axis verdicts: `flagged:card` = "shipped as asked; what was asked was wrong." Never lift `findings` verbatim — the output-side mirror of the fresh-eyes alignment pass.
   **Extraction is manual-only** — shipped workers never spawn `a-{key}` sessions. `delivery-note.py pending-extract` IS the surface: each key is a shipped story awaiting knowledge dissection, with `delivered` telling confirmed (Operator-accepted) from review-filed from awaiting-review work. Surface the count + keys in your brief; run `cdo-academy extract {key}` inline or a deliberate `spawn-dispatch.py --kind academy --key {key}` spawn ONLY when the Operator asks — a wake never extracts on its own.
   **Batch drained?** (`state-digest` → `wave_pending`) Spawn the holistic read — `spawn-dispatch.py --kind wave --key {batch_id}` — one `w-review-*` session reads every card + review doc + diff together, catches cross-story interactions, and files `wave-{batch}.md` with proposed Standing Policies as Operator checklist items.
6. **Boundaries hold in your sleep** — never execute unaligned work; missing env vars → temp values + requisition on the checklist; schema migrations and external-dep changes → escalate only when undeclared on the confirmed card (a declared Execution Surface was signed at alignment — proceed); production ship stays Operator-gated regardless of `earned_autonomy`.
7. **Write the handover** — update `handover.md` before exiting: checkpoint state, open escalations, pending Operator items, next action. This file is how the next shift wakes up knowing things.

## Scheduler

Installed: Windows Task `CDO-Marshal-Wake` — hourly, runs
`cdo-orchestrator/scripts/wake-marshal.py`, which composes this wake prompt
and spawns a local Devin ACP session (tab-id `cdo-marshal` — visible in the
IDE). `locks/wake.lock` prevents overlap; artifacts land in
`sessions/wake-{ts}.{prompt.md,acp.json,log}`. Manage:
`schtasks /run|/end|/delete /tn CDO-Marshal-Wake`; `--dry-run` previews.

## Logging

Append to `{orchestration_dir}/logs/autonomous-wake.log`:

```markdown
## {YYYY-MM-DD HH:MM} - Autonomous Wake

- Status: {resumed | dispatched story X | blocked: reason | idle: pool empty}
- Signals triaged: {n}
- Escalations raised: {n}
- Next action: {…}
```
