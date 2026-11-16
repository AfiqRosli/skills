# Capability: produce — execute the confirmed continuity item

A confirmed continuity item (runbook to write, recovery drill to run, hardening task) is work to execute — same dispatch contract as any dept. You are invoked inside a `cdo-batch` drain with a story key + its archived alignment card; the card's ACs are the contract.

## Execute

1. Read the card (`alignment/**/{key}.md`, skipping `<!-- reject` archives) — what was promised, scope boundary, externals.
2. Do the work the card describes — write the runbook, run the drill, apply the hardening. Resilience work is *evidence-shaped*: a runbook nobody rehearsed isn't done, a drill without a recorded outcome isn't done.
3. Journal the outcome in the passed devlog dir (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`) — decision entries per produced file, Before/After for doc surfaces.
4. Landings live where the card says — `runbooks/`, `doctrine.md` updates (Operator-proposed, never self-ratified), `learning/cases/` evidence.

## Boundaries

- The card's scope boundary is the wall — no "while I was in there" hardening beyond it.
- Production-touching actions (failover drills, restore tests) are **Operator-gated** — propose the drill plan, never execute against prod on a card alone.
- Anything that changes the deployable app (code, config, infra files) is the engineering dept's produce, not yours — note the seam in your outcome and stop.
