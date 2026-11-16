# Capability: recover — put the floor back upright

Post-crash/state-mess recovery: reconcile what the state files *say* against what files/git *show*.

## Sequence

1. **Integrity first** — run `cdo-watch --mode scan` for the anomaly list; that's the damage report.
2. **Orphaned in-flight** — ledger says in-flight but no `locks/{key}.lock`, or the lock's worker session is dead → break the stale lock (`dispatch.py release {key} --force`), set the story's status to `blocked` with reason `recovered: orphaned in-flight`, and journal the recovery. Do this per story — a dead drain can leave several stories claimed-but-unrun.
3. **Orphaned cards/ledger drift** — card archived but ledger never updated → reconcile the ledger to the card, not the reverse (the card is the signed contract).
4. **Missing files, present ledger entries** — the file system is truth for cards/backlogs; repair the ledger record to reflect reality.
5. **Journal everything** — every repair lands in `handover.md` + the item's findings: recovered state isn't real until it's recorded.

## Boundaries

Recovery repairs *state*, never *work* — it doesn't redispatch, doesn't re-decide alignments, doesn't resume a story without Marshal's say. The output is an integrity report + journaled repairs; the go-decision for resuming ops is the duty officer's.

## Output

`{repairs: [...], anomalies_remaining: [...]}` + journaled handover.

