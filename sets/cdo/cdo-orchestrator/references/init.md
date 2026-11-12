# First-Run Setup for Marshal

## Verify the module is installed

`{orchestration_dir}/` must exist with its seeded files (flow-ledger.yaml, doctrine.md, intent.md, patterns.md, alignment-checklist.md, frago-inbox.md, handover.md, backlogs/, logs/). If missing → the module isn't set up: route the user to `cdo-setup` and stop. Do not fake the structure by hand — `cdo-setup` owns scaffolding.

## Orient

Read `./references/access-boundaries.md` (required — the deny zones are contract, not memory), then `{orchestration_dir}/handover.md` + `flow-ledger.yaml` + `alignment-checklist.md` + `intent.md`. The handover is the resume surface — the state files are the memory; there is no separate memory store.

If all fresh/empty — a brand-new org: brief the Operator on what Marshal does (dispatch pool boundary, alignment drafting, duty-officer authority, FRAGO inbox, the two fresh-eyes gates) and ask for the first batch's intent — which backlog, which items.

Then present a status brief (see `./status.md`).
