# Capability: push — the pre-deploy lane publish

The ONLY actor that pushes to `origin/{ship_target}` under pre-deploy gating. Runs after the Operator signs `## Pre-deploy Sign-offs` items — the sign-off IS the push authorization; never push unsigned work.

## Gate

- The Operator signs items under `## Pre-deploy Sign-offs` in the checklist. `apply-decisions` stamps `stories.{key}.pre_deploy.signed_at` — unsigned work never pushes.
- One push per sign-off pass: the newest *signed* lane commit goes to `origin/{lane}` — earlier commits on `cdo-lane` ride along physically (linear history, no cherry-picking). `push-lane.py` reports every story carried; unsigned-but-carried stories are named, not hidden.
- `{ship_target}` = `production` → refuse: production asks file `## Deploy Sign-offs`, always.

## Execute

```bash
uv run scripts/push-lane.py --orchestration-dir "{orch}" \
    --project-root "{project-root}" --lane "{lane}" run
```

`run` resolves the newest `signed_at` story's `lane_sha` on `cdo-lane`, fetches `origin/{lane}`, refuses non-fast-forward (reconcile first — escalate, never force), pushes `origin {sha}:{lane}`, then stamps `stories.{key}.pushed` for every story whose lane_sha the push covered. A successful push also re-asserts the local `{lane}` branch at the `cdo-lane` tip (`advance-lane.py --reconcile`) — ship legs already advance it, this heals any missed/failed advance: ad-hoc WIP stashes aside and restores uncommitted, org-state churn checkpoints + merges; a refusal reports only — the WIP is never lost. Signed work already on origin (legacy pushes predating the gate) heals to a `pushed` stamp without a push. Escape hatches — Operator-typed only: `--tip` pushes the whole `cdo-lane` tip (signed or not — "push everything", carried unsigned work is named), `--sha {sha}` pushes an explicit commit.

`pending` lists the queue read-only: signed-awaiting-push and marked-unsigned — Marshal's surface for "what's staged vs what's waiting on a signature".

## Journal

The script writes `stories.{key}.pushed = {at, sha}` — Marshal surfaces the push outcome in the review report: what went up, what rode along unsigned, what stayed staged. A push isn't complete until the ledger knows it.
