# Capability: audit — find docs the site can't reach

The retroactive half of the visibility contract: pages that exist but are unreachable, and nav entries pointing at nothing.

## Run

```bash
uv run ./scripts/audit.py --orchestration-dir "{orchestration_dir-resolved}" \
    --project-root "{project-root-resolved}"
```

Requires `docs-profile.yaml` — run `detect` first if it's missing or the stack changed.

## Read the report

- `orphans` — pages no nav/sidebar entry reaches. For `config` nav these are invisible in the UI even though they're on disk (the reported symptom). Auto-zone pages are already excluded — they're generated, not orphaned.
- `broken_nav` — nav entries pointing at files that don't exist; these surface as dead links at build time.
- `no_docs` / `filesystem` outcomes are informational — nothing to fix.

## Act on it

- **orphans ≤ 5** → register them directly into `nav_config` per the profile's nav contract (produce's step 3, applied retroactively), then run `build_command` to prove it.
- **orphans > 5, or fixing them means reorganizing sections** → shape a `DOC{n}` item (`type: guide`, `target:` the restructure) and let it go through alignment — audit doesn't make structural calls unilaterally.
- **broken_nav** → fix or remove the dead entries; small fixes (≤ 5 entries, no restructure) are in-envelope, wide refactors get shaped like above.

## Output

audit.py JSON verbatim + what was fixed vs. enqueued.
