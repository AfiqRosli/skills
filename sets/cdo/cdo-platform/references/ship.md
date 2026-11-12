# Capability: ship — lane landing under lane authority

Verified work lands on the ship lane's LOCAL integration ref. The lane is the authority boundary: `{ship_target}` defaults to `preview`; the origin push is a separate Operator-gated leg (`push`), and **production is never in your authority**.

## Gate

- Item must be `verified` in the ledger (cdo-quality's audit pass). Shipping unverified work is the org's cardinal sin — refuse and say why.
- `{ship_target}` = `preview` → land on the local lane: commit the story's work and advance `refs/heads/cdo-lane` to it. Local only — NEVER `git push`; the origin push is the Operator's `## Pre-deploy Sign-offs` → `push` capability (pre-deploy gating exists because every push to origin costs a Netlify build — pushes batch at sign-off, never per story).
- `{ship_target}` = `production` or the ask IS production → file the request under the checklist's `## Deploy Sign-offs` and stop. The Operator signs off on prod, always.

## Execute — landing on the local lane

`refs/heads/cdo-lane` is the org's local-only integration ref — the lane's unpushed tip. Never pushed, never checked out, never a working branch: workers advance it, the `push` leg publishes it, new worktrees base on it (so dependents still see unpushed dep work). The local `{ship_target}` branch **mirrors** it (model B — "shipped, pending deploy"): landings advance it automatically (`land.py` calls `advance-lane` internally) — a manual re-assert `./scripts/advance-lane.py --project-root {root} run --lane {lane} --to refs/heads/cdo-lane` heals a stale mirror or heals after a refused advance; unpushed = `origin/{lane}..{lane}`. A plain-run refusal on a checked-out lane means org-state churn is blocking the FF — drain-end sweeps, review applies, and the push leg pass `--reconcile`, which checkpoints `docs/orchestration`/`_bmad-output` changes and merges; anything blocking outside those roots is a real conflict for the Operator, never auto-resolved.

- **Worktree drain:** the worker commits in its worktree — `./scripts/ship-commit.py --project-root {root} --orchestration-dir {orch} --work-tree {dir} --keys {key} --add-all --message "cdo {key}: <status>"` mirrors every story-scoped artifact in (devlog/card/sessions/review/knowledge live in the MAIN checkout's `{orchestration_dir}`, invisible to the worktree), stages, commits, reports the sha — then `./scripts/land.py --project-root {root} --lane {lane}` lands it on `cdo-lane` FF-only (rebase+retry once on CAS refusal — a commit whose tree predates landed sibling work silently reverts it) and advances the local `{lane}` mirror. **The ship commit carries the story's whole record, not just its code.**
- **Shared-checkout drain (`--no-worktree`):** `ship-commit.py --work-tree {root} --keys {key} --paths <story files>` commits on `{lane}` in place — `--paths` only, never `--add-all` (the main tree carries unrelated dirty state; the swept artifact paths are staged automatically). Committing on `{lane}` already implements the advance; `land.py --project-root {root} --work-tree {root} --lane {lane}` then mirrors the tip into `refs/heads/cdo-lane` FF-only.
- **Manual `cdo-platform ship` (interactive):** same contract — commit the verified work where it lives, `land.py` (FF-check→rebase→CAS→advance in one shot), report the sha.
- **Never force the ref, never land non-descendants:** `update-ref` with an old value refuses when a sibling landed meanwhile — rebase onto the lane tip and retry once, then stop and record `blocked`. The ancestor check runs before every CAS, not only on refusal — lane divergence and stale-base reverts are Marshal findings, not something to stomp.

Cloud drains are the exception (clone isolation): they commit and push `HEAD:{lane}` per story — pushing IS their way home, and their work lands on origin directly. Don't copy that habit onto the local lane.

## Journal

Record the ship as a ledger outcome — `dispatch.py outcome {key} --status shipped --lane-sha {sha} --findings "lane={preview} commit={sha} (local — awaiting pre-deploy sign-off)"` — then `handover.py write`. `shipped` means "landed on the local lane"; `stories.{key}.pushed` (written by the push leg) means "on origin". `shipped` is the status the downstream legs listen for (growth feeds on it, delivery metrics counts it). A ship that isn't journaled is a ship that can't be rolled back cleanly.

Finally, trigger the delivered review — whoever completes the ship leg owns the trigger (in-session dispatch workers do it themselves; a delayed ship — e.g. after a prod sign-off — gets it from you):

```bash
uv run .agents/skills/cdo-batch/scripts/delivery-note.py --orchestration-dir "{orch}" spawn-review {key}
```

It dedupes — already reviewed, already spawned, or already on `## Delivered` → refused, move on.

## Output

`{key, lane, result, commit}` via `dispatch.py outcome --status shipped --lane-sha`.
