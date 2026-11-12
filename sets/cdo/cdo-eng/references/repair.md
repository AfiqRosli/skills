# Capability: repair — bounded fix-up on broken items

Quarantined/blocked code items come here before re-dispatch: diagnose why, apply the minimal fix, or return a precise escalation.

## Flow

Read the item's ledger findings + quarantine reason + last devlog — `cdo-setup`'s `resolve-item.py {key}` gathers the state files in one shot. Then:

- **Clear mechanical failure** (missing import, stale dep, flaky step) → apply the minimal patch, verify it locally, then `dispatch.py reconfirm {key} --reason "repaired: {what changed}"` — that moves it quarantined → confirmed pool and flips the backlog `[-]`→`[x]` for re-dispatch. (Contract-wrong items take the re-align route instead — see below.)
- **Spec problem** (the card itself was wrong) → not repairable here; escalate with what the card got wrong — that's alignment's job.
- **External blocker** (missing creds, unavailable service) → requisition, not a repair; the item stays quarantined until the requisition is granted.

## The bound

Repair is bounded — one focused pass. If the fix needs more than a contained diff, it's a new story, not a repair: say so and let Marshal decide.

## Output

`{key, action: reconfirmed|escalated|still-quarantined, what_changed}`.

