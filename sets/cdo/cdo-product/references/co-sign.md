# Capability: co-sign — the second signature

Every alignment card needs Operator confirmation AND Product & Design confirmation. This is the P&D pass — invoke per drafted card before it reaches `cdo-review`.

## Input

Two call shapes — the pipeline co-signs *before* filing (cdo-align passes the drafted card body in memory, gets your verdict, stamps it, then `file-cards.py` writes once). Standalone re-sign: `{key}` → read `alignment/drafts/{key}.md` (exists after filing).

## Review — product judgment, not re-editing

Ask, in order:

1. **Is the product intent legible?** If you can't say what user value the card creates, it doesn't sign.
2. **Do the ACs test the intent?** ACs that check mechanics without checking the *point* are a reject.
3. **Does the scope boundary hold?** An "out" list missing the obvious creep surface = revise. The Execution Surface tokens count as in-scope declarations — an over-declared surface (`schema-migration` on a card that shows no DB work) is the same smuggle as a missing "out" line = revise. The mirror case counts too: a card whose body shows schema or package.json work but declares `none` stalls a legitimate run at the gate = revise.
4. **Is sizing honest?** A `lite` card hiding a multi-system change = revise.
5. **Do flags match the real soft spots?** An unflagged card on a genuinely uncertain item is worse than a flagged one — add the flag rather than sign blind.
6. **UI item with no visual?** A card touching pages/components/layout/routes/styles with `n/a` or no Visual Preview = revise — the Operator shouldn't adjudicate UI work on prose alone. `unavailable — wiretext MCP absent` is an honest degradation, not a revise.

## Verdict

- **sign** — card is Operator-ready; note any caveats the Operator should see
- **revise** — list the specific changes; the drafter re-files via `cdo-align` (idempotent by key)
- **reject** — not a product item / not worth doing; say why. Rejected cards bounce to Marshal's duty-officer, who decides whether the item dies or returns to shaping.

## Output

Verdict + one-line rationale per criterion that failed. Write the verdict onto the draft card (`- **P&D co-sign:** {verdict} — {rationale}`) so `cdo-review` sees both signatures. JSON the verdict for headless callers: `{"key": "...", "verdict": "sign|revise|reject", "notes": [...]}`.
