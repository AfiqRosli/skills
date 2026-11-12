---
name: 'cdo-review'
description: 'Presents the Operator review surface — pending alignment cards, escalations, pre-deploy + deploy sign-offs, requisitions — collects decisions, applies them, and journals corrections into doctrine. Use when the user requests to "review the checklist", "approve items", "sign off", or runs the decision leg of the cdo pipeline.'
---

# cdo-review

## Overview

The Operator's decision pass over everything the org queued for their eyes. Renders the pending surface (wiretext board when available, compact list otherwise), collects verdicts item by item or in bulk, applies them deterministically, and **auto-journals every correction into `doctrine.md`** — the org learns how the Operator actually decides.

**Args:** `--item {key}` (one item) · `--all` (walk every pending item) · `--headless`/`-H` (emit the pending surface as JSON — decisions are human business; headless review is presentation only. Use `cdo-handoff`'s `handover.py read` for the pending-items payload, or `state-digest.py` for counts)

**Your output:** applied decisions — confirmed items spawned into their own dispatch worker sessions (or pooled with reasons), corrections journaled, streak updated, requisitions recorded.

## Role

Act as the Executive Secretariat at sign-off time: present crisply, accept the verdict without lobbying, and extract the *reason* when the Operator corrects or rejects — the reason is the training data. "No" with a reason teaches; "no" alone is just a delay.

## On Activation

Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`, default `{project-root}/docs/orchestration`; missing → route to `cdo-setup`). Then run `uv run ./scripts/pending-surface.py --orchestration-dir "{orch}"` — its JSON IS the agenda: per-section pending items with parsed metadata, the parked inventory, staged-verdicts interruption state, and staged review docs. Never hand-parse the checklist.

**Staged verdicts first:** if `{orchestration_dir}/pending-decisions.jsonl` exists, a previous pass was interrupted after verdicts were spoken but before they applied — run the apply command against it (with `--consume`) or discard it before collecting new decisions. Never leave the Operator believing verdicts landed that didn't.

## Present

Before rendering, run the **delivered-review pass** — `delivery-note.py pending` lists stories that shipped without a Marshal assessment on the board. For each, do the fresh-eyes read (card promised vs `sessions/{key}.md` + ledger findings vs the actual diff where reachable), write the assessment doc to `alignment/reviews/{key}.review-{attempt}.md` (the emitted `review_doc` path — that's the Operator-pending staging; your verdict graduates it beside the card), and `delivery-note.py file` your own verdict — the worker's self-report never reaches this surface unfiltered. Skip it only if the session is explicitly presentation-only.

Order: Needs Attention → **Delivered** (what shipped — your skim surface) → Routine Review → Escalations / **Pre-deploy Sign-offs** (the preview-lane push gate — every signature spends one remote build) / Deploy Sign-offs / Requisitions. Per card item: title, confidence, the flags in one line, the draft path — and the wiretext URL when the line carries `| wire:` (UI-touching cards — the Operator checks the visual off with the card) — offer to open the full card. Per Delivered item: the one-line assessment, the verdict, the report path. When wiretext MCP is registered, render the board; otherwise a compact list. `cdo-batch` may also invoke this presentation on specific items (e.g., readiness bounce-backs).

**Parked inventory is a surface, not a pending item.** `alignment/parked/*.md` holds deferred cards — their checklist lines resolved at defer time, so they never appear on the agenda. List them (count + keys + defer date in the card's `<!-- deferred -->` stamp) when any exist — a parked card is a conscious "not now", and aging parks deserve a "resurface or keep parked?" call. `resurface {key}` revives the card into `drafts/` (warns when its grounding went stale); `unpark {key}` keeps it as history and re-opens the backlog for a fresh draft — both are verdicts in the staged decisions file, applied by key even though no pending line exists.

Non-card sections are decisions too: an escalation needs a call, a deploy sign-off needs a yes/no, a requisition needs "granted/blocked/deferred". On a Delivered item, **confirm** = accept the delivery (this also marks the story for pre-deploy — the sign-off item lands automatically); **reject** = the work's wrong — `apply-decisions` steers by the stamped verdict: `flagged:card-*` files a *reshape* escalation ("the card was wrong — re-align?"), any other flag files a *rollback* escalation. Both journal doctrine. Either verdict converges the local `{ship_target}` branch to the `cdo-lane` tip (`advance-lane --reconcile`), so the checkout you're reviewing against shows the shipped work — and a **confirm** also triggers the worktree cleanup: dead `.cdo-work/*` worktrees (no live session lock) are removed on apply, "kept until deliverables are reviewed and approved, then cleaned up" (the watch janitor's age sweep backstops); a **reject** keeps its worktrees while the rollback/reshape escalation is live. On a Pre-deploy Sign-offs item, **confirm/granted** = push the lane to that story's commit (one push publishes everything up to it); **reject/blocked** = the work stays local, journaled.

## Collect Decisions

Verdicts: **confirm** (as drafted) · **confirm-edited** (approved, but the Operator changed scope/criteria — requires `note` saying what changed) · **reject** (requires `note` — why) · **defer** (card parks under `alignment/parked/` — "looked at, not now"; `drafts/` holds only unexamined work; card sections only — a Delivered/Escalations line can't defer, reviews are accept/reject or stay pending) · **resurface** (revive a parked card — same card back to `drafts/` + a re-pended line; warns when its grounding went stale) · **unpark** (rethink a parked card — it snapshots to `superseded/` and the backlog re-opens for a fresh draft).

**Review-doc graduation:** any verdict that resolves a line carrying `| review: alignment/reviews/…` moves the staged doc beside the confirmed card — `reviews/` at a glance is the shipped-awaiting-review queue; empty means nothing needs your eyes. A wave doc or a verdict with no confirmed card lands in today's dated dir (warned).

A bare "ok" on a Routine Review item is a confirm — don't interrogate per item; batch the obvious ones and spend words on the flagged ones.

**Stage each verdict as it lands** — append one JSON line per decision to `{orchestration_dir}/pending-decisions.jsonl` (`{"key","verdict","note","lesson?"}`). Conversation is volatile; a crash mid-pass must not lose verdicts the Operator believes were recorded.

## Apply

**For `confirm-edited` first write the Operator's edits into the draft card** (`alignment/drafts/{key}.md`) — the archived card must be the *approved* version; dispatch benchmarks against it. When the edit touched scope or acceptance criteria on a card carrying a Visual Preview URL, the wireframe may now depict a design the Operator just edited away from — offer: keep as-is, regenerate (re-run wiretext and update the card), or strip the URL (the pipeline falls back to normal wireframe gating). Edits to Execution Surface tokens propagate automatically — the card body is the contract.

Run the staged verdicts once (not per item — one atomic write pass):

```bash
uv run ./scripts/apply-decisions.py --orchestration-dir "{orchestration_dir-resolved}" \
    --decisions "{orchestration_dir-resolved}/pending-decisions.jsonl" --consume
```

`--consume` removes the staging file on full success (or trims it to just the invalid lines on a partial). A plain `.json` decisions file still works — `--consume` simply won't apply.

The script archives confirmed/rejected cards to `alignment/YYYY/MM/DD/`, parks deferred cards under `alignment/parked/` (and revives/redrafts them on `resurface`/`unpark`), flips backlog markers (`[x]`/`[-]`), updates `flow-ledger.yaml` (`pool.confirmed`, `quarantined`, `autonomy.streak`), marks checklist lines resolved, files `## Pre-deploy Sign-offs` items for accepted Delivered work, appends Decision Log entries for every `confirm-edited`/`reject`, and returns `newly_confirmed` + `push_approved`. Streak rules: `confirm` on a ≥95%-confidence card increments; any correction or rejection resets to zero. No Python → apply by hand and say so.

**Pre-deploy push — a signed item IS the push order.** When `push_approved` is non-empty, run the push leg once for the whole set (one push publishes the newest signed lane commit — never per item):

```bash
uv run .agents/skills/cdo-platform/scripts/push-lane.py --orchestration-dir "{orch}" \
    --project-root "{project-root}" --lane "{ship_target}" run
```

It fast-forward-checks `origin/{ship_target}`, pushes the newest signed `lane_sha`, and stamps `stories.{key}.pushed` — unsigned work that rode along is named in the report, never hidden. A non-FF refusal → report it; reconcile before re-signing. Nothing else may push: no worker, no ship leg, no ad-hoc `git push`.

## Auto-dispatch — confirmation IS the dispatch order

Never ask "should I run these?" — the Operator's confirm already answered. Unless `cdo.dispatch_mode` is `manual`, immediately after the apply pass:

```bash
uv run .agents/skills/cdo-batch/scripts/ready-set.py --orchestration-dir "{orch}" \
    --env-file {path-to-.env}
# one linear drain session for the whole list:
uv run .agents/skills/cdo-batch/scripts/spawn-dispatch.py --orchestration-dir "{orch}" \
    --project-root "{project-root}" --keys {dispatch_now CSV}
```

1. `ready-set.py` over the whole pool (not just `newly_confirmed` — previously pooled items may have just become unblocked) → `dispatch_now` (one topo-ordered list) + `waiting`.
2. Spawn ONE drain session for the whole list — a `w-drain-{ts}` worker that runs the keys in order on the single `{ship_target}` (`preview`) lane, then mops up reviews/extracts, then drafts alignment for unaligned items before exiting. Local drains land each story on the local-only `cdo-lane` ref — nothing reaches origin until a Pre-deploy sign-off publishes it (that's the point: pushes batch at sign-off, remote builds stop running per story). `{dispatch_target}` = `cloud` is the exception — a clone's only way home is pushing, so cloud workers still push `HEAD:{ship_target}` per story after pushing the confirmed pool up front (verify before push, no branches to merge). A fresh `g-*.lock` drain marker means a drain is already running — a second spawn must not double it; skip and say so. Missing `devin` binary or a spawn refusal → report as a capability gap, don't fake it.
3. `waiting` keys stay pooled — report each reason in one line ("13-08 waits on 13-04", "02-02's dep quarantined").

The drain works unattended; this review session continues — move on to the next pending item or hand back. If `cdo-batch` isn't installed, say so — confirmed work that can't dispatch is a gap the Operator should hear.

## Report

What was confirmed (and dispatched — with worker session names), what was rejected/quarantined, what was marked for pre-deploy (and pushed — `push-lane.py`'s result: target sha, carried unsigned work, what stayed staged), what's waiting on deps or conflicts and why, what doctrine learned (the entries written), current autonomy streak, and what remains pending.
