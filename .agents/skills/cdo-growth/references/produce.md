# Capability: produce — author content

Confirmed content item in, publishable artifact out.

## Produce

For a confirmed `CT{n}` item, write `content/{key}/`:

- the piece — post/guide/announcement shaped for its audience (technical readers get devlog-grade honesty, not marketing gloss)
- `meta.md` — title, kind, target channel, source story, publish status

When `bmad-agent-tech-writer` is installed, delegate drafting to it — owner skills invoked, not re-implemented.

## Standards

- **Source-story honesty** — the `source:` pointer means every claim traces to something that actually shipped. No vapor.
- **Kind fit** — `post` ≠ `guide`: posts are timely + narrative ("we shipped X, here's what surprised us"), guides are durable + teachable ("how to do Y").
- Calendar writes happen via `calendar` after the piece exists.

## Devlog

When invoked under `cdo-batch`, the caller hands you a devlog dir — journal the piece's decision entries to it as you work:

```bash
uv run {project-root}/.agents/skills/cdo-batch/scripts/devlog.py append {dir} --title "..." --step 3 --of 8
```

Editorial choices get the same decision-entry shape as code changes — Context, `**File:**` + `**Goal:**`/`**Gap:**`, literal Before/After fences carrying draft wording deltas, Why this angle, Alternatives considered. Contract: `cdo-batch/references/devlog-conventions.md`. Standalone invocations (no devlog dir passed) skip this — the ledger findings remain the record.

## Output

`{key, artifact: content/{key}/, kind, source_story}`.

