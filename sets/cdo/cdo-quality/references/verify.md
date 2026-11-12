# Capability: verify

<!-- Twin contract: cdo-batch/references/prompts/review.md encodes the same card→evidence→verdict judgment for the detached delivered-review worker. Different axis (in-chain contract audit vs post-hoc fresh-eyes review), same benchmark rules — keep Execution Surface / undeclared-surface semantics in sync across both files. Note: this leg runs inside the producing worker's session — it is checklist execution against the card; the independent read belongs to the r-{key} review session. -->

The audit leg — delivered work checked against the *contract*, not its own self-report. The card is the benchmark; the devlog/diff is the evidence.

## Input

`{key}` → gather evidence via `cdo-setup/scripts/resolve-item.py --orchestration-dir {orch} {key}` (ledger + card + backlog line + signals in one JSON) + the story's deliverable (devlog, diff, PR, spec — whatever the pipeline produced).

## Audit

For each acceptance criterion on the card: **verified** (evidence exists), **unverified** (no evidence), or **failed** (evidence contradicts). Then the boundary check — did the work touch anything the card's `out` list forbids? A perfectly-executed wrong scope is a fail. The card's `## Execution Surface` tokens are in-scope declarations: a `schema-migration`/`deps-changed` declared there is aligned work, not a boundary violation — an *undeclared* one is both a finding and drift. No resolvable confirmed card = nothing declared = treat everything as undeclared.

## Verdict — each maps to a `dispatch.py outcome` call

- **verified** — all ACs evidenced, boundary held → `outcome {key} --status verified --findings "{summary}"` → release-eligible
- **findings** — gaps needing a fix pass → `outcome {key} --status blocked --findings "{which AC, what evidence is missing}"` — auto-quarantines; repair path is `cdo-eng repair` → `reconfirm`
- **failed** — contract breach → `outcome {key} --status killed --reason "{breach}"` — auto-quarantines; duty-officer decides the item's fate

Never write findings into the ledger by hand — `dispatch.py outcome` is the single writer that also flips the backlog marker and feeds metrics.

A `verified` verdict is what makes an item release-eligible — verification is the gate between "code written" and "ship-ready."

## Standards

- Evidence over assertion — cite the file/devlog line, not "looks done"
- Scope-creep findings count even when the in-scope work is clean
- Uncertain evidence → say so; a verify pass that guesses is worse than none
