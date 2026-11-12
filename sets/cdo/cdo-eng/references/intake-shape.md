# Capability: intake-shape — code items

Turn a raw engineering ask into a real sprint story — not just a backlog line. A shaped code item is born with all four artifacts: the `code.md` line, the story file in the current sprint's `story_location`, a `proposed` entry in the sprint yaml, and a `### Story` section in the sprint's epics doc. Alignment then interrogates a spec that exists, not a one-line claim.

## Resolve the current sprint

"Current" = the newest `_bmad-output/implementation-artifacts/sprint-status-*.yaml` (version-sort the date in the filename — `sprint-status-Beta-2026.10.11.yaml` beats `…10.04.2`). Never trust `release-train.json` for this — its `current.sprint` field lags, and the app version is irrelevant anyway: stories follow the sprint, not the release tag. The yaml's `story_location` field names the story dir; the matching epics doc is `_bmad-output/planning-artifacts/epics-beta-{release}.md` where `{release}` is the yaml filename minus `sprint-status-`/`.yaml`.

## Mint the key

Canonical key = `NN-MM-slug` — `NN` = epic number, `MM` = story number inside that epic, `slug` = kebab-case title. There are no S{n} keys on new work — the sprint key is the one identifier the backlog, ledger, cards, locks, sessions, and devlogs all share.

- **Epic (`NN`)** — honor an explicit prefix when the ask carries one (`13-20 …` → epic 13); otherwise assign by domain. `epic-13` (Bugs & Enhancement) is the catch-all for eng/org hygiene work.
- **Story (`MM`)** — max existing `NN-` story numbers in the sprint yaml + 1, zero-padded to 2.
- **slug** — title lowercased, `[^a-z0-9]+` → `-`, edges trimmed.

## The four writes — one script, ordered so a failure can't half-shape

`python .agents/skills/cdo-setup/scripts/shape-story.py --project-root {root} --orchestration-dir {orch} --title "{title}" [--epic N] [--approach "{…}"] [--touches "{…}"] [--size lite|full] [--deps "{…}"]` performs all four writes in the safe order: **sprint yaml `proposed` entry first** (the fallible write — a missing `epic-N` block refuses before any file exists) → **story skeleton** at `{story_location}/{key}.md` → **epics-doc `### Story` section** → **backlog line** via `backlog-add.py` (single writer, dedupes). `--dry-run` prints the plan + minted key without writing. Minting follows the rules above — your judgment is the *content* (approach/touches/size/deps), the script owns the mechanics (version-sort, max-MM+1, insert order, key collision).

A line without its three siblings is half-shaped — the script writes all four or reports exactly which write failed.

**The four writes are the default, not a courtesy.** Any story minted anywhere in the org's comms — intake, alignment review, a repair escalation, an Operator co-design session — runs through this script. Hand-minting a key and writing only a backlog line leaves the sprint yaml and epics doc lying about what exists.

## Splits

When a story fans out into siblings — scope too big, two concerns under one key, an Operator-directed carve like 01-10 → 01-11 — `--split-from {parent}` runs the same four writes for the child **plus lineage both ways**: the child's yaml entry, skeleton, and epics section carry `split from {parent}`, and the parent's yaml line and epics `### Story` section get annotated `split → {child}`. `--deps` defaults to the parent when unset; pass `--deps "none"` (or another list) to override. The parent must already exist in the sprint yaml. Run once per child — the script refuses to split a parent that isn't real, so the ledger can't drift into phantom lineage.

## Judgment calls

- **Sizing honesty** — `lite` = contained, one-surface; `full` = multi-surface or architectural. Under-sizing is how pipelines stall.
- **Reuse detection** — if the ask is already covered by an existing module/pattern, note `reuse: {thing}` on the line; rebuilding what exists is a common pipeline waste.
- **Already in the sprint yaml** → don't re-mint; append `was {old-key}` lineage in the note if it migrated, update the backlog line, and say so.
- **Not an engineering ask** → route elsewhere: product-shaped → `product.md`, content → `content.md`.

## Output

`{key, backlog: code.md, story_file, sprint_yaml, epics_doc}` — all four paths; `{skipped: reason}` when routed elsewhere.
