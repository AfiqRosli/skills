# Sizing Flags — `oversized`

A card whose scope implies **more than one dispatch arc** is flagged `oversized` at draft time — before the Operator confirms, not after a drain stalls. Advisory only: flagged cards still land on the checklist (flags surface via file-cards.py) and the Operator may confirm as-is.

## Signals (either routes the flag)

1. **Multi-surface:** `size: full` AND Touches span ≥3 distinct dirs/systems (e.g. `server/` + `stores/` + `components/` + `drizzle/` in one card).
2. **Sequential sub-features:** the approach reads as ordered sub-features that could ship independently ("then", "next add", "finally wire") — a hidden queue inside one card.

## What the flag carries

- `## Suggested Split` block on the card: recommended keys with clean deps (each its own dispatch arc, deps declared).
- The flag feeds takt: oversized cards that ship anyway show their cost in attempt burn.

## Changelog

- 2026-10-18 — 13-31 introduced (ralph-loop benchmark: one item per loop → one arc per card).
