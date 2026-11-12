# Capability: produce-spec

Confirmed alignment card in, spec artifact out — the depth the work warrants.

## Input

`{key}` → archived card at `alignment/YYYY/MM/DD/{key}.md`.

## Produce

**`lite` cards:** a story spec — intent, the ACs expanded into testable statements, affected surfaces, acceptance notes. Files to `{orchestration_dir}/specs/{key}.md` (or the project's spec convention if one exists).

**`full` cards:** a PRD-shaped artifact — problem, users, requirements (functional/non-functional), success metrics, out-of-scope, epic sketch. Same destination, fuller skeleton.

## Delegation

When the owner's skill is installed, delegate rather than re-derive — owner skills are invoked, never re-implemented:

- PRD-shaped → `bmad-prd`
- UX/interface-heavy → `bmad-ux` for the spec pass
- story-file conventions → `bmad-create-story` — CDO-shaped stories arrive pre-seeded (skeleton at `{story_location}/{key}.md` + sprint-yaml entry minted by `shape-story.py` at intake): enrich the existing file to full context, never re-mint the key or clobber the shaped spec

Missing delegates → produce the artifact internally; a lean complete spec beats a missing one.

## Done means

Artifact written, path recorded, and the backlog line gets a `spec:` pointer appended. The pipeline's dispatch check can then trust the item is ready for engineering.

## Devlog

When invoked under `cdo-batch`, the caller hands you a devlog dir — journal the spec's decision entries to it as you work:

```bash
uv run {project-root}/.agents/skills/cdo-batch/scripts/devlog.py append {dir} --title "..." --step 3 --of 8
```

Spec choices get the same decision-entry shape as code changes — Context, `**File:**` + `**Goal:**`/`**Gap:**`, literal Before/After fences carrying the spec's actual wording or deltas, Why this approach, Alternatives considered. Contract: `cdo-batch/references/devlog-conventions.md`. Standalone invocations (no devlog dir passed) skip this — the ledger findings remain the record.

## Output

`{key, artifact: specs/{key}.md, delegates_used: [...]}`.

