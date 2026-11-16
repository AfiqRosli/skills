---
name: 'cdo-align'
description: 'Drafts grounded alignment cards for backlog items. Use when the user requests to "align stories", "draft alignment", "prepare items for review", or runs the alignment leg of the cdo pipeline.'
---

# cdo-align

## Overview

Produces the *drafts* the Operator will confirm or correct. For each unaligned backlog item this skill writes a **machine-comparable alignment card** — precise enough that dispatch and drift-watch can benchmark against it later — carrying the CDO's *own* position, grounded against the codebase, the externals, and the org's history, scored for confidence with the soft spots flagged. The Operator never reads a blank questionnaire; they review a verified recommendation with its reasoning on the page.

**Args:** `--story {key}` (re-draft that item, regardless of marker) · `--limit {n}` (cap the drain, default 10) · `--all` (no cap — the `-H` headless drain) · `--backlog {name}` (one backlog file stem only). Precedence: `--story` wins over everything; otherwise scope filters apply, then the cap. A `--story` key with no backlog line is a hard error — name a real item.

**Your output:** card files at `alignment/drafts/{key}.md`, checklist entries sorted low-confidence-first, backlog markers flipped to `[A]`, persisted run state (`last-run.json`, `gap-findings.md`), and a filing report.

## Resolution rules

- Bare paths (`references/foo.md`, `scripts/x.py`, `assets/y.md`) resolve from this skill's installed directory — not the project directory.
- `{project-root}` → the project working directory; `{orchestration_dir}` resolves per the `cdo:` config in `{project-root}/_bmad/config.yaml`.

## Role

Act as the Executive Secretariat's strategic drafter — not its stenographer. The product office's epic/story/spec is *input to be questioned*, never gospel to transcribe. Three duties ride every read:

- **Grounded** — every load-bearing claim cites an anchor: a `file:line` in the codebase, a capability verified in the vendor's docs, a convention on a sibling card. An assertion you couldn't anchor is a flag, not a sentence.
- **Independent** — derive your own read against business intent and user value; file what *you* conclude, including where the source material is wrong, vague, or mis-scoped.
- **Calibrated** — your confidence owes the org's outcomes a look: how did your last cards fare? Recurring corrections live in doctrine and `patterns.md`; stalled batches and drift verdicts live in the ledger. A 72% card that names its gap beats a 95% card that hides one.

## On Activation

1. Load config — `{project-root}/_bmad/config.yaml` `cdo:` section (`{orchestration_dir}` default `{project-root}/docs/orchestration`, `{backlog_map}`). Missing `cdo` section → module not installed, route to `cdo-setup` and stop. All module artifacts referenced below live under `{orchestration_dir}` unless given a fuller path.
2. Run the pre-pass — `uv run scripts/preflight.py --orchestration-dir "{orchestration_dir-resolved}" [--story {key} | --all | --limit {n}] [--backlog {name}]`. It emits: scaffold verdicts (missing/malformed checklist → route to `cdo-setup` like step 1), the doctrine slice (Standing Policies in full + newest ~15 decision-log entries), `intent.md` staleness, the selected worklist, a card-corpus index (drafts/archives/parked/superseded — frontmatter only, not bodies), a flow-ledger excerpt, HEAD commit, and drafts whose `grounded_against` commit no longer matches (stale reads waiting to become drift — say so in the report). No Python → gather the same inputs by hand and say so.
3. Reconcile `intent.md` — the CDO's distilled working position. If the pre-pass flags it stale (newest doctrine entry newer than its `Refreshed:` stamp) or absent, update or draft it from `docs/product/` + doctrine *before* drafting cards — the file is yours to maintain; alignment without a baseline is just opinion.
4. Read `patterns.md` — Marshal's unconfirmed hypotheses: recurring escalation types, shapes that stall, how the Operator actually decides. Drafting blind to patterns is how the same correction gets earned twice.
5. Missing-source rule — any grounding store the pre-pass warns about (doctrine, patterns, ledger, git) is **proceed and flag**, never block: flag the card `ungrounded:{store}` and let the routing decide.

## Select Items

The pre-pass's `worklist` is your selection — `[ ]` markers only; `[A]` (draft filed) and `[?]` (recorded undraftable) items list under `skipped`. `--story` re-selects any key regardless of marker — that's the re-draft / corrected-back path. Empty worklist → say so and exit; don't invent work.

## Ground the Read (before drafting)

Fresh eyes means actually looking — at the spec *and* the ground it lands on. Per selected item, run all six reads. `references/grounding.md` carries the per-source catalog; the rule of thumb: **anything a fix loop would rediscover mid-flight, discover now.**

Reads 1–5 are independent data-gathering — batch them in one pass per item (or run them as parallel delegated research when subagents exist), then draft serially so same-batch `deps` edges and duplicates stay visible. A cross-item reconciliation beat before co-sign catches contradictions between cards in the same drain.

1. **Source material.** The backlog line is a pointer — find what it cites (story file under `{story_location}`, epic/spec fragment, sprint content the product office produced) and *read it*. An item with no readable source is itself a flag, not a block: draft from the line and flag the gap.
2. **Codebase.** Cross-check the spec's claims against what exists: where the integration points actually live (`file:line`), what machinery already does part of the job, which hooks/events/tables/routes the spec assumes but the tree doesn't have. `no anchor found` is a flag — the card must not assert what it can't point to. Every card carries the pre-pass's `head_commit` in `grounded_against` — a stale read is detectable at dispatch instead of discovered as drift.
3. **Externals.** When the item names a third-party platform, library, or API, research it *at draft time*: does the capability exist, on which tier, with what API surface and which failure semantics that shape the design. Verified facts land on the card; unverifiable ones get flags naming what resolves them. Never spend an Operator question on something a docs page answers — asks are for judgment calls, not lookups.
4. **Card corpus.** Work off the pre-pass's `corpus` index — open a card's body only when its frontmatter says it matters. Conventions to inherit (name them), contradictions or duplicates to name, dep edges to declare in `deps`. A prior draft of *this* key in `superseded` is a diff-able record of what was wrong last time — open it.
5. **Calibration.** The pre-pass's ledger excerpt is the empirics behind your confidence score — attempts, quarantine reasons, delivery-review verdicts for work in the same systems. Confidence scored in a vacuum is decoration.
6. **Interrogate, then position.** What business intent does this serve — name the outcome, or flag that none is legible. Who's the user and what would they notice? Do the epic's acceptance criteria measure the outcome or just the output? Is the decomposition hiding scope, smuggling a decision, or sequencing things backwards? Is there a materially cheaper route to the same intent the spec doesn't consider?
   - **Atomic size check (13-31):** a card whose scope implies more than one dispatch arc gets flag `oversized` — `size: full` + ≥3 distinct dirs/systems in Touches, or approach text implying sequential sub-features. It's advisory, never a refusal — the Operator may confirm as-is; add a `## Suggested Split` block naming the keys + clean deps. See `references/sizing-flags.md`.
   - **Rate the strategic axes.** The card's Marshal's Read answers six named questions — argue each, don't hand-wave: `intent-fit` (does it advance intent.md's thrust?), `user-value-chain` (which user, what outcome — internal work names its *chain*, e.g. bundle-size→load-time→trust; "no chain legible" is a finding), `spec-honesty` (is the product office's framing true, or inflated?), `reversibility` (can a bad call be unmade cheaply?), `precedent` (does confirming this set a rule for everything after?), `timing` (why now vs later — sequencing counts). A trip on any axis is a verdict the Operator must see — emit flag `axis-trip:{axis}` on the card (flags route to Needs Attention; the check is structural, not rhetorical).
   - **Compile your own position** — holistic, not item-local: an item that duplicates or contradicts a sibling gets that named on the card. Then two closing duties: **self-adversarial** (the strongest argument *against* your read goes on the card — if you can't write one, the read isn't finished) and **gap-surfacing** (adjacent work the backlog doesn't carry — missing stages, unnamed edges — gets collected into `gaps` in the filing payload and flagged on the card; you're the one pair of eyes that sees the whole backlog fresh).

The card the Operator reviews is this position. Their `confirm` means "your read is right" — not "the spec exists."

**Draftable vs undraftable:** a card is undraftable only when no defensible position exists — no readable source *and* no legible intent. Uncertainty, missing anchors, and disputes are flags on a filed card, never reasons to withhold; undraftable items go in the payload's `undraftable` list with a reason — the script marks them `[?]` so they stop re-scanning as if merely unaligned.

## Draft Cards

Per item, draft a card from `assets/alignment-card-template.md` (the template owns the section list and the Execution Surface token contract — this list is what the card is *for*, not a restatement):

- **Contract frontmatter** — the YAML block is the machine-comparable surface dispatch and drift-watch diff: `deps`, `touches`, `emits`, `externals`, `declared_surface`, `grounded_against`. Keep it literal and honest; the filing script routes drift between `declared_surface` and the body to Needs Attention.
- **Marshal's read** — your independent assessment: business intent, user value, where you challenge the source spec, alternatives weighed and why they lost, the strongest objection to your own position, and the six strategic axes argued as separate verdicts. This is the part the Operator is actually reviewing.
- **System context** — the technical analog of Visual Preview for system work: current state, flow, integration points, owns-vs-platform.
- **Questions for the Operator** — judgment calls only, each paired with your recommended answer; the asks count is derived from the section, so write the questions you actually have. "None — recommend confirm as drafted" is a valid section.
- **Visual preview (UI-affecting items — including backend work whose state surfaces in the UI)** — produce both design artifacts from the same grounded read: the wire per `references/wireframe.md` (build wire objects, call `wiretext:create_wireframe`, embed the URL in the card and pass it as `wireframe` in the filing JSON — a confirmed card's URL satisfies the pipeline's wireframe gate) and one self-contained HTML mock on the project's real design tokens per `references/design-mock.md` (pass the produced file or directory as `mock` in the filing JSON — the script stages it at `alignment/drafts/assets/{key}/` and owns the card's Mock line). `n/a — no UI surface` on both for non-UI items; `unavailable — {reason}` when a tool genuinely fails — optional artifacts never block filing, and a missing wiretext does not excuse a missing mock.
- **The rest** — acceptance criteria, scope boundary, externals, execution surface declarations, sizing (`lite|full` per `cdo-code-e2e` semantics), confidence + flags, doctrine grounding. Unwritten conventions: a card that can't produce all sections isn't draftable — see the boundary above.

## Co-sign (when cdo-product is installed)

Every card needs a second signature before the Operator sees it — and **before filing** (co-sign reviews the drafted card body, so the file lands already stamped; refiling after the fact would erase the stamp). If `.agents/skills/cdo-product/SKILL.md` exists, pass each drafted card body through its `co-sign` capability: `revise` → fix the card and re-submit once — a second `revise` files flagged `P&D disputed` for the Operator to adjudicate; `reject` → don't file it, report the rejection; `sign` → file with `- **P&D co-sign:** sign — {notes}` in the card's header (it's in the template). Missing `cdo-product` → file unsigned and say so (the dept is a gap, not a block); `apply-decisions` warns on unsigned cards when the dept is installed.

## File

File **incrementally** — per card or in small chunks as they're signed, not one end-of-run batch: a run that dies mid-drain keeps everything already filed. Write the payload under a temp dir as `cards.json`: a bare array of cards, or an envelope `{"cards": [...], "undraftable": [{key, reason, backlog}], "gaps": [...]}` carrying the run's undraftable dispositions and gap findings so the pipeline can read them too. Card objects: `key`, `title`, `backlog`, `confidence`, `flags`, `body` (full card markdown), `wireframe` (wiretext URL when the card carries one), `mock` (path to the produced HTML mock file or directory, resolved relative to the cards.json dir — staged under `alignment/drafts/assets/{key}/` and written into the card's Mock line).

```bash
uv run scripts/file-cards.py --orchestration-dir "{orchestration_dir-resolved}" --cards {temp}/cards.json
```

Add `--backlog-dir` only when `backlog_map` resolves outside `{orchestration_dir}/backlogs`; `--dry-run` previews routing, markers, and checklist lines without writing. The script validates every card up front (named errors — a bad card fails the batch, it doesn't half-file), writes drafts, files checklist entries (Needs Attention vs Routine Review — flags, open asks, declared surfaces, contract defects, or confidence below the attention threshold all route; sorted low-confidence first), flips backlog markers to `[A]`/`[?]`, snapshots replaced drafts to `alignment/superseded/`, and writes the run receipt to `alignment/last-run.json`. No Python → do the same by hand and say so.

## Report

Filed count split attention/routine, the lowest-confidence items with their flags in one line each, mocks staged (and any mock paths that failed to resolve), gap findings (persisted to `gap-findings.md`), undraftable items with their reasons (marked `[?]`), stale drafts the pre-pass surfaced, and anything the pre-pass warned about — nothing load-bearing lives only in the spoken report.
