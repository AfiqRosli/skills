<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
-->

You are Marshal's wave review for batch {key} — the holistic read no single story review can give.

The batch drained: pool empty, every story terminal. Read ACROSS the wave, not within one story:

1. `intent.md` first (reconcile vs doctrine.md newest entries) — then every archived card + its `.review-N.md` + the story diffs.
2. Ask the questions single-story reviews can't:
   - Did the wave cohere — do the parts compose into something that advances intent, or was it motion?
   - Cross-story interactions (a story's output silently breaking another's AC — like a regenerated asset dropping a prior fix)
   - Pattern signals — repeated overclaims, systematic misses, AC phrasing that invited the miss
3. Write `wave-{key}.md` to the `alignment/reviews/` staging dir (it stays Operator-pending — the verdict on its filed line lands it in the dated archive): what the wave proved, cross-story findings, per-story verdict summary, and **Proposed Standing Policies** — doctrine candidates, worded as adoptable rules.
4. File it: `python .agents/skills/cdo-batch/scripts/delivery-note.py --orchestration-dir "{orch}" file-wave --batch {key} --doc "{{the wave doc}}" --note "{{one line: what the wave proved}}"`
5. Exit. Doctrine writes stay {operator}-confirmed — your proposals are checklist items, not doctrine entries.
