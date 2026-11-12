# Capability: rollback — abort-safe revert

A shipped story that turns out wrong gets reverted, not patched forward. This is the continuity-adjacent duty scoped to release.

## Execute

1. Identify the story's commit(s) on the ship lane (`git log --grep "cdo {key}"` / the ship journal entry — the lane is linear; per-story commits, no merges).
2. `git revert` the story's commit range — never force-push, never amend history; a revert commit is the clean, auditable undo.
3. Journal the rollback to `handover.md` + ledger findings: `{key, reverted-commit, reason, at}`.
4. Story state → the item returns to the quarantined pool with reason `rolled back: {why}` — re-entry to dispatch goes through re-align, not a re-ship.

## Boundaries

- Rollback only what was shipped — a `verified` but unshipped story gets killed via `dispatch.py outcome --status killed`, not a revert.
- If the story's merge touched shared surfaces and the revert conflicts, that's escalation: journal the conflict and hand the rollback decision to the duty officer — a messy revert inside a live batch is how bad weeks get worse.

## Output

`{key, revert_commit, ledger_status}` + rollback journal.

