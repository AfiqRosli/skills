# Capability: rollback — abort-safe revert

A shipped story that turns out wrong gets reverted, not patched forward.

## Execute

1. Revert the story's shipped commit — `scripts/rollback.py {key} --orchestration-dir "{orch}" --project-root "{project-root}" --reason "{why}"`. It resolves `stories.{key}.lane_sha` from the ledger (`git log` fallback for legacy ships), refuses anything that doesn't read `shipped`, `git revert --no-edit`, and reports `{lane_sha, revert_commit, pushed, conflicts}` — a conflict aborts clean and names the paths; the tree is never left half-reverted.
2. Land the revert like a ship commit — `scripts/land.py --project-root "{project-root}" --lane "{lane}"` (FF-only on `cdo-lane` + mirror advance).
3. Journal the rollback to `{orchestration_dir}/handover.md` + ledger findings: `{key, reverted-commit, reason, at}`.
4. Story state → the item returns to the quarantined pool with reason `rolled back: {why}` — re-entry to dispatch goes through re-align, not a re-ship.

## Boundaries

- Rollback only what was shipped — a `verified` but unshipped story gets killed via `{project-root}/.agents/skills/cdo-batch/scripts/dispatch.py outcome --status killed`, not a revert.
- If `stories.{key}.pushed` is set, the local revert is only half the fix — publishing it is an Operator action (`push --sha {revert-sha}` or a fresh `## Pre-deploy Sign-offs` pass; on production a `## Deploy Sign-offs` item). Name the publish path in the rollback journal.
- A `conflicts` result is escalation, not a retry: journal the named paths and hand the rollback decision to the duty officer — a messy revert inside a live batch is how bad weeks get worse.

## Output

`{key, lane_sha, revert_commit, pushed}` + rollback journal.
