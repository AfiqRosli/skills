# Capability: Batch Supervision

The batch is a state machine, and **dispatch is linear**: ONE drain worker session works the confirmed queue key by key on the ship lane (`preview`), and keeps going while the org has work — mop-ups, then a clean exit (alignment drafting is explicit-command, never drain work). Your job is spawning the drain when it's warranted and watching the floor, not running pipelines inline.

## Inputs

`state-digest.py` output first (batch, pool, `in_flight` list, `dispatch_locks`, `worker_sessions`, streak, signals — already computed) · `flow-ledger.yaml` for detail · `alignment-checklist.md` · `handover.md` · `backlog_map` from config.

## Dispatch locks (per-story claims)

Locks are per story: `locks/{key}.lock`, written only by a worker's `dispatch.py claim`. A held lock for a key means that key is running — it says nothing about other keys. A legacy `dispatch.lock` still counts for its embedded key.

- Before counting a story as "needs dispatch", check `dispatch_locks` in the digest — a fresh lock means a live worker already owns it.
- **You never write or break locks yourself.** Claim is the worker's (`cdo-batch`); break is the janitor's. Stale locks (age > 2× stall timeout) → `cdo-watch --mode janitor`, journal the break.
- `worker_sessions` in the digest names spawned workers (`sessions/{key}.json`) — a fresh lock with a dead/missing worker record is drift worth noting.

## What to decide

Pick the next action(s):

- **Dispatch the ready set — one drain, one branch** — confirmed pool non-empty → run `ready-set.py` (deps satisfied + not in-flight + no fresh lock + produce resolvable + externals present). It emits `dispatch_now`: one topo-ordered list — spawn ONE session for the whole queue:

  ```bash
  uv run .agents/skills/cdo-batch/scripts/ready-set.py --orchestration-dir "{orch}" \
      --env-file {path-to-.env}
  uv run .agents/skills/cdo-batch/scripts/spawn-dispatch.py --orchestration-dir "{orch}" \
      --project-root "{project-root}" --keys {dispatch_now CSV}
  ```

  Dispatch is **linear**: a single `w-drain-{ts}` session runs the keys in emitted order on the single working lane (`{ship_target}`, `preview` by default), recomputing `ready-set` between stories so newly-freed or newly-confirmed work joins its own drain. There are no `cdo/*` branches and nothing to merge — code lands on the lane post-verify, per story. Local landing means the `cdo-lane` ref, not origin: the push is a separate Operator-signed leg, so `shipped` ≠ "on the remote" — check `pushed` for that. `touches:` stays on the line as blast-radius context for reviewers; it no longer gates (sequential execution can't conflict with itself).

  With `{dispatch_target}` = `local` the spawn is a detached `acp-worker.py` supervisor driving a `devin acp` session on this machine — it lands in the shared `sessions.db` with `hidden=0`, so the worker is **visible and resumable in the IDE's session list**; auth is `DEVIN_API_KEY` from the environment or `{project-root}/.env` (`authenticate` per session — `devin auth login` is NOT required). Space grouping is IDE-owned state (`windsurfSpace.resourceToSpace`): `--tab-id` tags sessions with a space id/title but sessions can't self-join while the IDE runs — `join-space.py` batch-assigns spawned sessions to a space when the IDE is closed/restarting. Locks, ledger, `sessions/drain.{log,acp.json,json}` (log = session/update stream, acp.json = session_id + stop_reason + usage) are the liveness story. Sub-sessions (`r-{key}` review) spawn the same way from inside the worker — nested detached supervisors, auditors not builders, so the drain doesn't wait on them. `a-{key}` academy sessions spawn ONLY on Marshal's deliberate `--kind academy` call — extraction is a manual leg, never auto-dispatched on ship. A `g-*.lock` drain marker holds the queue's keys until the worker exits and removes it. Local drains are **pre-deploy gated**: each story's ship lands on the local-only `cdo-lane` ref (worktrees base on it — dependents still see unpushed dep work) and no worker ever pushes; the Operator's `## Pre-deploy Sign-offs` is the only path to origin (`cdo-platform push` / `push-lane.py`) — every push is a remote build, so pushes batch at sign-off. With `{dispatch_target}` = `cloud` the spawn pushes the confirmed pool to `origin/{ship_target}` first, then opens a **Devin Cloud** session (`devin --cloud -p`) on a fresh clone checked out on `{ship_target}`; the worker commits per story and pushes `HEAD:{ship_target}` home — verify BEFORE push is the contract, a refused push rebases and retries (cloud is the exception to the gate: a clone's only way home is pushing). `waiting` entries carry precise reasons and re-enter the next pass when their blocker clears. If `cdo-batch`/`spawn-dispatch.py` isn't installed or `devin` isn't on PATH, dispatch is a capability gap — say so, don't improvise the pipeline.

  The drain's tail order is fixed: **queue → mop-ups → exit.** While the queue has keys the worker builds; empty queue triggers `delivery-note.py pending` spawns (detached r- auditors — the fresh-eyes review stays a separate session by design, the worker never grades its own homework). `pending-extract` is read-only to the drain — unextracted keys are reported as extraction debt in `sessions/drain.md`, never auto-spawned (extraction is manual: `cdo-academy extract` or a deliberate `--kind academy` spawn). Still empty means the drain reports unaligned backlog items as alignment debt in `sessions/drain.md` and exits — it never drafts cards.
- **Feed the pipeline** — confirmed pool below `{alignment_buffer_min}` → **report it, don't draft.** Name the unaligned candidates and their backlogs in the brief; alignment drafts happen only on explicit command (`cdo-align` invoked by the Operator or a FRAGO). An empty pool is a finding to surface, not a queue to fill — never let "the pool is starving" become silent authorship of cards nobody asked for.
- **Quarantine/hold** — blocked items stay quarantined with reasons; dependent stories behind them hold automatically in `waiting`. Continuing the batch around a quarantine is your call — judgment, informed by `block_reason`.
- **Delivered work reviews itself fresh-eyed** — a `shipped` story's worker triggers `delivery-note.py spawn-review {key}` as its last act: a separate session (`r-{key}`) audits the evidence (card promised / findings claimed / `sessions/{key}.md` / real diff) and files its own verdict onto `## Delivered`. Near-real-time, no Operator wait. `delivery-note.py pending` is the mop-up: shipped-but-unbriefed with no live review record → `spawn-review` it yourself; a dead reviewer's record goes stale and re-admits. The worker's self-report never reaches the Operator unfiltered — either an `r-*` session's read or yours gets filed.
- **Wave read on drain** — when the pool empties and every story's terminal (`state-digest` → `wave_pending`), spawn `spawn-dispatch.py --kind wave --key {batch_id}`: one holistic session reads all the wave's cards + review docs + diffs together, catches cross-story interactions single reviews miss, and files `wave-{batch}.md` into the `alignment/reviews/` staging bay with proposed Standing Policies as Operator checklist items — the Operator's verdict lands it beside the cards. This is where "did the batch actually advance intent" gets answered.
- **Idle cleanly** — pool empty, nothing pending, wave filed → drain to a clean stop. An idle org waiting for alignment sign-off is a feature, not a failure. Say so plainly.
- **Cost ceiling** — when `{batch_budget}` is set, burn approaching it means let in-flight workers finish, spawn nothing new, and say so. Never silently overrun.

## Post-outcome chain

A worker session owns its story end-to-end — produce → `verify` (cdo-quality) → `ship` (cdo-platform, preview lane) → `feed` (cdo-growth/cdo-docs) — holding its key's lock through the legs and heartbeating at each boundary. `extract` (cdo-academy) is a manual post-ship leg, not part of the chain — `pending-extract` tracks the debt. Your job is watching the seams, not driving them:

| Ledger status | What you watch for |
|---|---|
| `done` | verify never recorded / worker died mid-chain → stale lock → janitor + recovery |
| `verified` | ship refused or skipped → the verified-vs-shipped gap is the story |
| `shipped` | feed legs missing → docs/content leak, nudge it (`cdo-docs feed` is idempotent — re-running feeds any gap; `cdo-docs audit` finds orphans the nav can't reach). Missing `extract` is expected, not a leak — `pending-extract` is the manual surface (per-key `delivered` state separates Operator-confirmed from awaiting-review work). `shipped` means landed on the local `cdo-lane` ref — a `pushed` stamp on the story means it's on origin (pre-deploy sign-off published it); signed-but-unpushed keys are `push-lane.py pending`'s queue |
| `blocked`/`killed`/`deferred` | duty-officer triage → `cdo-eng repair` → `dispatch.py reconfirm` → re-enters the pool |
| `quarantined` | `forensic {key}` for post-mortems when worth the lesson | cdo-continuity |

When a worker's outcome lands, the next ready-set pass may free dependents — recompute after any story reaches a terminal state.

## Outputs

Updated `flow-ledger.yaml` (story states, burn, pool transitions) · spawn decisions journaled · fresh `handover.md` checkpoint naming live worker sessions · status line to the Operator stating what spawned, what's waiting, and what's next.

## Non-negotiable

The Dispatch Pool Boundary: only items that completed Operator alignment dispatch. If a story fails readiness it waits with a reason — never fixed silently. (Machines that run forever but only do approved work are the entire point.)
