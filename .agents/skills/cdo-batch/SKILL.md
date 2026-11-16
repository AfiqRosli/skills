---
name: 'cdo-batch'
description: 'Executes one confirmed story end-to-end inside its own dispatch session — readiness gate, per-story lock claim, pipeline invocation, chain legs, ledger outcome, lock release. Spawned by spawn-dispatch.py (cdo-review/Marshal) or invoked directly. Use when the user requests to "dispatch a story", "run the batch", "start the next item", or a spawn prompt routes here.'
---

# cdo-batch

## Overview

The **worker contract** for one story's delivery. You run inside a dedicated session — spawned by `spawn-dispatch.py` when alignment confirms the story (usually as a key in a `w-drain` session's queue), or invoked directly for a manual dispatch. It is deliberately dumb about *whether* to run (confirmation already decided that) and rigorous about *how*: readiness gate, exclusive per-story claim, honest outcome recording, clean release. Dispatch is linear — the drain works the queue on the ship lane one key at a time — and your lock is yours alone (`locks/{key}.lock`), held one story at a time. Local work never pushes: ship lands on the `cdo-lane` ref, then mirrors onto the local `{ship_target}` branch ("shipped, pending deploy") via `advance-lane.py` — the Operator's pre-deploy sign-off is the only publisher; a `git push` from a worker session is a contract violation, not a shortcut.

**Args:** `--story {key}` (required — this skill executes named work, it doesn't pick) · `--session {name}` (the identity a spawn prompt baked in — default `w-{key}-{ts}`; the lock and ledger attribute work to it) · `--headless`/`-H` (same flow, errors become JSON)

**Your output:** one story carried from confirmed to a terminal outcome — `done` advanced through `verify` → `ship`, running the `feed` legs on ship (knowledge extraction is a manual post-ship leg — never spawned, never run inline), or a refusal/quarantine with precise reasons — plus a **devlog** at `docs/orchestration/devlog/<Channel>/<date>/<key>/` journaling the arc (same format as cdo-code-e2e's devlogs; see `./references/devlog-conventions.md`).

## Role

Act as dispatch control for exactly one story: the pool boundary is absolute — only Operator-confirmed items move, and a failed gate reports why instead of improvising. You own this story end-to-end; you own nothing else.

## On Activation

Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}` default `{project-root}/docs/orchestration`, `backlog_map`, `stall_timeout_minutes`, `ship_target`). Missing `cdo` section → route to `cdo-setup`, stop.

## 1. Readiness Gate

```bash
uv run ./scripts/dispatch.py --orchestration-dir "{orch}" check {key} \
    --stall-timeout-minutes {n} [--env-file {path-to-.env}]
```

`ready: false` → report `reasons`/`missing_env` and stop. Two outcomes worth extra handling:

- `missing_env` non-empty → file a requisition via the script (`dispatch.py ... requisition {key} --reason "ENV_X"`), inject temp values into `.env` only when the card's externals allow it, then either proceed-if-tolerated or leave the item pending with the requisition noted. Never print secret values.
- `lock for {key} held & fresh` → another session owns *this story*; report and exit. Locks on other keys are not your business — `locks[]` in the output is informational. (A `g-*` drain lock carrying your own session name is *your* queue marker — `check` and `claim` already exempt it; a drain lock held by anyone else means the drain owns this key — stop.)

## 2. Claim

```bash
uv run ./scripts/dispatch.py --orchestration-dir "{orch}" claim {key} --session "{session}" --step dispatch
```

The claim writes `locks/{key}.lock`, flips the story to `in-flight` with a `step_started` timestamp (the watchdog's heartbeat), and removes it from `pool.confirmed`. A refused claim is a stop, not a retry — check `locks/` and the story's ledger state first.

**Devlog — attach now.** Once the claim lands, resolve and attach the story's devlog. It's the audit spine for everything after — every leg boundary journals to it.

```bash
uv run ./scripts/devlog.py path --key {key} --project-root "{project-root}"
uv run ./scripts/devlog.py attach {dir} --story-key {key} --release {rel-from-path} \
    --session "{session}" --dept {dept} --backlog {backlog} --card {card-path} \
    [--pipeline --sprint-status {sprint_yaml} --story-file {path}]  # when path reports shared_with_pipeline
uv run ./scripts/devlog.py set {dir} readiness done
uv run ./scripts/devlog.py set {dir} claim done
```

`path` checks the sprint yamls first: a sprint story resolves to the same `Channel/date` folder cdo-code-e2e derives, so a code dispatch shares one devlog — pass `--pipeline` then so the index carries cdo-code-e2e's `pipeline.steps` (its resume contract) alongside your grafted `dispatch:` block. Keys not in any sprint yaml land under the **current sprint's** `Channel/date` — devlogs follow the sprint, not the app version (`CDO/<today>` only survives when the repo has no sprint yaml at all). Then append your opening entry (`append --title "Dispatch opened" --step 2 --of 8`): card, backlog, session, what the readiness gate saw.

## 3. Invoke the Pipeline

Route by backlog → department `produce` capability from `capabilities.yaml`:

- Look up the item's backlog in `{backlog_map}`, find the dept owning it in `capabilities.yaml` (`departments.{dept}.capabilities.produce.entry`) and invoke that capability with the story key. `check` reports `produce_entry`/`dept` and flags a missing `produce` — treat `ready: false` on that reason as a pre-claim stop.
- **Pass the devlog dir with the invocation** — the producing dept journals its own decision entries (literal Before/After per file per `./references/devlog-conventions.md`) into `{dir}`; standalone invocations without a dir simply skip journaling. For `code` items the dir is already the cdo-code-e2e path — the dept's pipeline writes its journal there; you add dispatch-level entries only.
- **`code` backlog special case:** `cdo-eng` owns `produce` when registered. If `cdo-eng` is absent but `cdo-code-e2e` is installed, invoke `cdo-code-e2e --story {key}` directly — the direct path is the fallback, not the preference.
- Missing dept module or missing `cdo-code-e2e` → capability gap: record outcome `blocked` with a precise reason (`cdo-eng absent`, `cdo-code-e2e not installed`) and release the lock.

Let the pipeline run — your job during it is the **heartbeat**, not interference. At each step boundary (and at least every `{stall_timeout_minutes}` on long steps) refresh the liveness timestamps, or a legitimately-slow step reads as a stall and the janitor will break your live lock:

```bash
uv run ./scripts/dispatch.py --orchestration-dir "{orch}" heartbeat {key} --session "{session}" --step {current-step}
```

Each heartbeat boundary is also a devlog beat: `devlog.py set {dir} produce in-progress` when the produce leg starts, `append` a short entry when it returns (invoke → outcome — the dept's own decision entries carry the detail).

## 4. Record Outcome and Drive the Chain

```bash
uv run ./scripts/dispatch.py --orchestration-dir "{orch}" outcome {key} \
    --status {done|verified|shipped|blocked|killed|deferred} --findings "..." \
    --reason "..." --burn {units}
```

`blocked`/`killed`/`deferred` auto-quarantine. `--burn` feeds the cost ledger — report units consumed so `batch_budget` has teeth.

**You own this story's whole arc.** The lock is per-story, so holding it through the legs blocks nobody — keep it and drive the chain, heartbeating at each leg boundary:

Every leg is a journal beat — `devlog.py set {dir} {leg} in-progress` on entry, `append` the outcome + `set {leg} done` (or `skipped`/`blocked`) on exit:

- `done` → invoke `cdo-quality verify {key}` (contract audit against the card) → its verdict writes `verified`/`blocked`/`killed` via this same script
- `verified` → invoke `cdo-platform ship {key}` (preview lane only) → records `shipped` — `land.py` lands the commit on the local `cdo-lane` ref **FF-only** (the new tip must descend from the old — it rebases before CAS, never lands a stale tree) and advances the local `{ship_target}` branch to the lane tip ("shipped, pending deploy"); **never pushes** — the origin publish is the Operator's `## Pre-deploy Sign-offs` → `cdo-platform push`, not yours (pre-deploy gating: pushes batch at sign-off, remote builds stop running per story). The ship commit carries the story's WHOLE record — `ship-artifacts.py` sweeps devlog/card/sessions/review/knowledge into the commit tree before `git commit`, not just the code
- `shipped` → invoke `cdo-growth feed` and `cdo-docs feed` — shipped work becomes content and docs candidates (`cdo-docs`'s `feed.py` lands unaligned `DOC{n}` items on `backlogs/docs.md`; idempotent + attempt-aware — a re-attempted story re-feeds the doc refresh, so the docs queue never silently goes stale). Knowledge extraction is NOT yours — it's a manual leg: never spawn `a-{key}` sessions and never run `cdo-academy extract` inline. `delivery-note.py pending-extract` tracks the unextracted set (per-key `delivered` state: awaiting-review | review-filed | confirmed); the Operator/Marshal decides when extraction runs — a deliberate `spawn-dispatch.py --kind academy --key {key}` spawn or `cdo-academy extract` inline. The missing `extract` stamp IS the debt signal — journal nothing extra.
- `blocked`/`killed`/`deferred` → record and stop; triage is Marshal's/watch's job — the repair path is `cdo-eng repair` → `reconfirm` puts it back in the pool. Note in your terminal report whether `ready-set.py` now shows follow-ups freed by your outcome. Mark the unrunnable legs `skipped` in the dispatch block and journal the terminal reason — a failed dispatch still gets a readable arc, not a silent gap.

If a mid-chain leg leaves the story stuck (verify never recorded, ship refused), record what happened in findings and release — a story sitting `done` forever without `verify` is an integrity anomaly the digest surfaces for Marshal.

## 5. Release

**Devlog close-out first.** Before the lock goes, the devlog must stand on its own — a reader landing from the docs sidebar gets the whole arc without you:

```bash
uv run ./scripts/devlog.py sweep {dir}
uv run ./scripts/devlog.py lint {dir}
```

`lint` failures are formatting bugs in entries you (or the produce leg) wrote — fix them. Then write `retrospective.md` beside `index.md` from `./assets/retro-template.md` (dispatch-scoped: what shipped, what struggled, what the next dispatch should know), `set {dir} release done`, and append the close-out entry — terminal status, commit/lane if shipped, review spawned.

```bash
uv run ./scripts/dispatch.py --orchestration-dir "{orch}" release {key} --session "{session}"
```

`release` requires `--session` naming the lock holder (`--force` is for stale-lock breaks by recovery, not workers). Release at terminal state — the story is yours until an outcome records.

**Session ledger note:** append your terminal report to `sessions/{key}.md` next to your spawn record — what ran, status, burn, anything the next shift needs. `handover.md` belongs to Marshal; your ledger line is `stories.{key}.findings` plus that file.

**Delivered-review trigger (last act, any terminal state):** whether your story `shipped`, `blocked`, got `killed` or `deferred` — trigger its independent review before you exit. Successes get audited, failures get a postmortem; the Operator should see either in minutes, not on the next wake:

```bash
uv run ./scripts/delivery-note.py --orchestration-dir "{orch}" spawn-review {key}
```

This launches a separate worker session (`r-{key}` — Devin Cloud under `dispatch_target: cloud`, detached `devin -p` under local) that audits the delivery fresh-eyed and files Marshal's verdict onto `## Delivered`. You spawn the reviewer — you do **not** do the review: your self-report would be the worker grading its own homework. A refusal (already reviewed, already spawned, devin missing) is not your problem — a later wake catches it.

## Rules

- **One story at a time per session — enforced, not advised.** Your lock names one key; `claim` refuses a second key for a session already holding a fresh story lock. A drain session runs its queue *sequentially* — each story claims, completes, and releases before the next begins — never interleave, never two `--story` args at once.
- **Never retry inside the dispatch.** A failed pipeline run is an outcome to record and hand back to triage (`cdo-watch`/duty-officer), not a loop to fix here.
- **Drain continuation — bounded context, single drain preserved.** A drain spawned with `--story-budget N` (default `cdo.drain_story_budget` = 4) hands its remaining queue to a successor after N completed story outcomes: it writes `sessions/drain.md` with `continuation: true`, spawns the successor via `spawn-dispatch --continuation` (which bypasses the fresh `g-*` check exactly once — caller marker stays up until the successor's lands), then exits. `--continuation` is a queue handoff, not a second drain — the one-drain invariant holds end-to-end.
- **Prompt contracts are versioned files.** The five spawn contracts (drain, dispatch, review, wave, academy) + note blocks live in `.agents/skills/cdo-batch/references/prompts/*.md` — `spawn-dispatch.py` loads them at spawn time. When a flagged `delivery-*` pattern traces back to contract wording, cite the file + version (`cdo-prompt v1`) in the review. Changelog convention: one line per edit — date, story key or cause.
- **Other workers are not your concern.** Sibling `locks/*.lock` files (the `g-*` drain marker, `r-*`/`a-*` aux sessions) mean other work in flight, not contention — never release, break, or report on a lock that isn't yours.
- **Temp values mark themselves.** Any `.env` value injected as a placeholder gets `# TEMP-CDO` comment suffix so a later sweep can find every fake.
- **The devlog is bookkeeping, never the gate.** A `devlog.py` failure lands in `findings` and the story continues — journal gaps are visible defects in the log itself, not a reason to hold the lock. But never write secrets to it: lock names, session ids, and verdicts are fine; `.env` contents are not.
