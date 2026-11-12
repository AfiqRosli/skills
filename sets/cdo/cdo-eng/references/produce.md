# Capability: produce — the code dispatch target

`cdo-batch` calls this for `code` backlog items. Confirmed card in, implemented story out.

## Flow

1. **Spec ready?** `full`-sized items need a story spec first — `bmad-create-story` when installed, enriching the `shape-story.py`-seeded skeleton at `{story_location}/{key}.md` (never re-minting the key); else a lean spec file under `{orchestration_dir}/specs/{key}.md`. `lite` items run off the card + backlog line alone.
2. **Invoke `cdo-code-e2e`** for the story — headless per the pipeline's mode. `cdo-code-e2e` is the owner skill: invoke, don't re-implement. Missing `cdo-code-e2e` → record outcome `blocked` with reason `cdo-code-e2e not installed` — this dept cannot code without its pipeline.
3. **Return the result** — pass cdo-code-e2e's outcome through verbatim; the batch layer records it (outcome/quarantine). Don't reinterpret pipeline failures — report them.

## Judgment calls

- **Spec drift:** if the card's ACs changed since the item was confirmed, that's a re-align case — bounce back with the delta named, don't dispatch on a stale contract.
- **Re-dispatched items** (`attempts` > 1 in the ledger): check the last attempt's findings before re-running — repeat failures without a changed hypothesis just burn budget.

## Devlog

Code stories share one devlog with the dispatch: `cdo-batch` resolves the sprint-derived path (the same folder cdo-code-e2e picks) and grafts its `dispatch:` block onto the index. **cdo-code-e2e owns the `pipeline:` state and the dev journal — don't write dispatch-level entries or second-guess its steps.** Your contribution is boundary-honest: if the pipeline never ran (missing `cdo-code-e2e`, spec-drift bounce), say so in your result so the batch's produce-leg entry records the real outcome, not an implied one.

## Output

passthrough of the cdo-code-e2e result envelope + the `dispatch.py outcome` record.

