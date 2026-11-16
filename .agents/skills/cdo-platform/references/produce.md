# Capability: produce — execute the confirmed platform item

A confirmed platform item (env fix, deploy hardening, infra task) is work to execute — same dispatch contract as any dept. You are invoked inside a `cdo-batch` drain with a story key + its archived alignment card; the card's ACs are the contract.

## Execute

1. Read the card (`alignment/**/{key}.md`, skipping `<!-- reject` archives) — what was promised, scope boundary, externals.
2. Do the work the card describes — the env fix, the deploy hardening, the infra task. Platform work is *config-shaped*: a hardening that isn't applied to the real config isn't done, an env fix that doesn't resolve the requisition isn't done.
3. Externals the card needs but `.env` lacks → run `scripts/env-scan.py --orchestration-dir "{orch}"` — `missing` keys file requisitions, not workarounds; a `# TEMP-CDO` placeholder you inject marks itself.
4. Journal the outcome in the passed devlog dir (`devlog.py append`, contract in `cdo-batch/references/devlog-conventions.md`) — decision entries per produced file.
5. Landings live where the card says — config, infra files, `backlogs/platform.md` item resolution.

## Boundaries

- The card's scope boundary is the wall — no "while I was in there" hardening beyond it.
- Production-touching work is **Operator-gated** — a deploy/promote ask files `## Deploy Sign-offs`, never executes.
- Code changes to the deployable app are the engineering dept's produce, not yours — note the seam in your outcome and stop.
