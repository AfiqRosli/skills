# Capability: feed — shipped work lands in the docs queue

Shipped work is docs debt until documented. Feed makes the source material arrive on its own.

## Run

```bash
uv run ./scripts/feed.py --orchestration-dir "{orchestration_dir-resolved}"
```

## Semantics

- Every `done`/`verified`/`shipped` story not already on `docs.md` becomes `- [ ] DOC{n} — {title} | source: {key} | type: guide | attempt: N`
- Attempt-aware — when `stories.{key}.attempts` exceeds the `attempt:` on its DOC line, the doc is stale: an open item gets bumped + `| re-attempted: N` flag; a consumed `[x]`/`[-]` item gets a fresh refresh item so the rewrite goes through alignment
- Idempotent at the current attempt — a story already represented isn't re-fed
- Not everything shipped deserves a doc — the alignment pass decides doc-worthiness; feed's job is to ensure it's *considered*

## Output

feed.py JSON verbatim — `{status: fed|no_new, items_added: [...]}`.
