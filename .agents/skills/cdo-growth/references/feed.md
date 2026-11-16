# Capability: feed — shipped work lands in the content queue

Inbound-only intake: the delivery floor is the source material. Run:

```bash
uv run ./scripts/feed.py --orchestration-dir "{orch}"
```

## Semantics

- Every `done`/`verified`/`shipped` story not already on `content.md` becomes `- [ ] CT{n} — {title} | source: {key} | kind: post`
- Idempotent — a story already represented isn't re-fed
- Not every shipped thing is content-worthy — the alignment pass on the CT item is where "is this worth a post?" gets decided; feed's job is to make sure it's *considered*

Inbound-only is a stance: this dept writes about real shipped work, it does not produce outbound spam. The source-story pointer keeps every piece honest — cite what actually shipped.

## Output

feed.py JSON verbatim — `{status: fed|no_new, items_added: [...]}`.

