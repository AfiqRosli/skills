# Capability: plan — the batch manifest

Order the confirmed pool into a dispatch sequence. Run via the script:

```bash
uv run ./scripts/manifest.py --orchestration-dir "{orch}" [--batch-id {id}] [--replan]
```

## Semantics

- **Stable topo-sort** — backlog order is the tie-breaker; `deps:` fields on backlog lines are the ordering constraints. A dep outside the pool counts as already-done.
- **Cycle → block**, don't guess: report the cyclic keys to the duty officer — a dependency loop means someone's `deps:` is wrong or the scope needs re-splitting.
- **`--replan`** — Marshal invokes this on FRAGO events: the manifest re-orders around what's in-flight (in-flight keys surface in the report — they were already claimed and can't be re-ordered retroactively, only sequenced around).

The script writes `batch.id` / `batch.manifest` / `batch.started` to the ledger — `cdo-batch` dispatches down the manifest order.

## Output

manifest.py JSON verbatim — `{manifest, deps_resolved, in_flight}` or `{errors, dead_deps|cyclic}`.

