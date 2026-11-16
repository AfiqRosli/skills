# Capability: intake-shape

Turn a raw ask — a chat line, a wish, a half-sentence — into a backlog item precise enough that `cdo-align` can draft a card against it without guessing.

## What a shaped item carries

Append to `{orchestration_dir}/backlogs/product.md` as `- [ ] {key} — ...`:

- **key** — `P{n}` next number
- **problem** — who's hurting and what hurts
- **value** — what changes if this exists
- **AC sketch** — 2-4 candidate acceptance statements (alignment refines them)
- **sizing** — lite | full
- **deps** — other items, externals, upstream decisions

Format: `- [ ] P7 — {title} | problem: {…} | value: {…} | ac: {…;…} | size: {lite|full} | deps: {…|none}` — one line; the card carries detail later. Append via the canonical writer (`cdo-setup/scripts/backlog-add.py --backlog product --key-prefix P --title "…" --field value=…`) — hand-appended lines drift; the script's don't.

## Judgment calls

- **Not everything is a product item.** Code-shaped asks → `code.md` instead; pure content → `content.md`. Shaping includes routing discipline.
- **Push back on bad asks** — if the ask is incoherent, flag it on the line (`flag: incoherent — {why}`) rather than shaping garbage; an honest flag beats a confident guess.
- **Check doctrine** for prior Operator product decisions — a rejected sibling ask tells you the shape the Operator doesn't want. Bounded read: `## Standing Policies` + newest ~15 `## Decision Log` entries — the file grows forever, your context doesn't.

## Output

`{key, backlog: product.md}` — the appended line; `{routed: code|content}` when the ask belonged elsewhere.

