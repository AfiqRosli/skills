# Capability: drift-check — the in-flight benchmark

While a story runs, this is the "is it still doing what we approved" check. The duty officer owns the `drift` signal triage; this capability produces the evidence.

## Input

`{key}` → in-flight story (ledger `stories.{key}` state + devlog/diff so far) + its alignment card.

## Benchmark

Compare the work-in-progress against the card's scope boundary and ACs:

- **aligned** — diff/devlog consistent with card scope; keep running
- **drifting** — evidence of work outside the `out` list, or ACs being answered differently than drafted; quote the deviation (which line/file, which clause it violates)

Drift ≠ imperfection — a failing test inside scope is normal engineering; a schema migration the card's Execution Surface never declared is drift (a declared one is aligned work). Material drift on a live story is halt-worthy: journal the evidence, signal the duty officer (`signals/drift-{key}.md`), let Marshal decide kill-vs-redirect.

## Output

`{key, verdict: aligned|drifting, evidence: [...], signal_filed}`.

