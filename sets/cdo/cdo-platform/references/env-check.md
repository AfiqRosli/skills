# Capability: env-check — credential logistics

Which externals exist, which are placeholders, what's missing. Run via the script:

```bash
uv run ./scripts/env-scan.py --orchestration-dir "{orch}" [--env-file {path}]
```

## Reading the report

- `real` — set keys (values never surface in output, ever)
- `temp_placeholders` — `# TEMP-CDO` markers: they unblocked dispatch but are NOT real credentials; a story shipping on a placeholder is a ship-to-failure
- `missing` — card-declared externals with no key → file `## Requisitions` entries (`- [ ] KEY — needed by {card}`) so the Operator sees exactly what to grant
- `requisitions.pending` — what's already asked and ungranted

Act on the gaps: file the missing-key requisitions, flag temp-placeholder stories as ship-blocked. Granting a requisition = setting the real value — that's the Operator's side; your side is naming it precisely.

## Output

env-scan.py JSON verbatim — `{ok, real, temp_placeholders, missing, requisitions}`.

