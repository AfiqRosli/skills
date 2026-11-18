---
name: cdo-align
description: 'Drafts grounded alignment cards for backlog items. Use when the user requests to "align stories", "draft alignment", "prepare items for review", or runs the alignment leg of the cdo pipeline.'
---

# cdo-align

## Overview

Produces the *drafts* the Operator will confirm or correct. For each unaligned backlog item this skill writes a **machine-comparable alignment card** — precise enough that dispatch and drift-watch can benchmark against it later — carrying the CDO's *own* position, grounded against the codebase, the externals, and the org's history, scored for confidence with the soft spots flagged. The Operator never reads a blank questionnaire; they review a verified recommendation with its reasoning on the page.

**Args:** `--story {key}` (re-draft that item, regardless of marker) · `--limit {n}` (cap the drain, default 10) · `--all` (no cap) · `--backlog {name}` (one backlog file stem only) · `--headless`/`-H` (pipeline-invoked drain: implies `--all`, no Operator asks — judgment calls land on the card as flags with your recommended answer; blocked stops emit `{"status": "blocked", "reason": ...}` from the prompt layer, while a completed drain's caller reads the `file-cards.py` receipt on stdout — `status` (`success`|`partial`), `filed`, counts, `needs_attention`, `suggest` — persisted as `alignment/last-run.json`). Precedence: `--story` wins over everything; otherwise scope filters apply, then the cap. A `--story` key with no backlog line is a hard error.

**Your output:** card files at `alignment/drafts/{key}.md`, checklist entries sorted low-confidence-first, backlog markers flipped to `[A]`, persisted run state (`last-run.json`, `gap-findings.md`), and a filing report.

## Resolution rules

- Bare paths (`references/foo.md`, `scripts/x.py`, `assets/y.md`) resolve from this skill's installed directory — not the project directory.
- `{project-root}` → the project working directory; `{skill-root}` → this skill's installed directory; `{workflow.<name>}` → a merged `customize.toml` field.
- `{orchestration_dir}`, `{backlog_map}`, `{story_location}`, `{product_docs}` resolve per the `cdo:` config in `{project-root}/_bmad/config.yaml` — all module artifacts live under `{orchestration_dir}` unless given a fuller path; product docs live under `{product_docs}` (default `{project-root}/docs/product`).

## Role

Act as the Executive Secretariat's strategic drafter — not its stenographer. The product office's epic/story/spec is *input to be questioned*, never gospel to transcribe. Three duties ride every read:

- **Grounded** — every load-bearing claim cites an anchor: a `file:line` in the codebase, a capability verified in the vendor's docs, a convention on a sibling card. An assertion you couldn't anchor is a flag, not a sentence.
- **Independent** — derive your own read against business intent and user value; file what *you* conclude, including where the source material is wrong, vague, or mis-scoped.
- **Calibrated** — your confidence owes the org's outcomes a look: how did your last cards fare? Recurring corrections live in doctrine and `patterns.md`; stalled batches and drift verdicts live in the ledger. A 72% card that names its gap beats a 95% card that hides one.

## On Activation

1. Load config — `{project-root}/_bmad/config.yaml` `cdo:` section (`{orchestration_dir}` default `{project-root}/docs/orchestration`, `{backlog_map}`, `{story_location}`, `{product_docs}`). Missing `cdo` section → module not installed, route to `cdo-setup` and stop. Then resolve customization: `uv run {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --project-root {project-root} --key workflow` (on failure read `{skill-root}/customize.toml`, use defaults). Run `{workflow.activation_steps_prepend}`/`append`; hold `{workflow.persistent_facts}` as standing context.
2. Run the pre-pass — `uv run scripts/preflight.py --orchestration-dir "{orchestration_dir-resolved}" --backlog-map '{backlog_map as JSON}' [--story {key} | --all | --limit {n}] [--backlog {name}]` (the script resolves where backlog files live; `--backlog-dir` remains the manual override). It emits the inputs the steps below consume: scaffold verdicts (missing/malformed checklist → route to `cdo-setup`), the doctrine slice (Standing Policies + newest ~15 log entries), `intent.md` staleness, the worklist, a card-corpus index (drafts/archives/parked/superseded, frontmatter only), a flow-ledger excerpt, HEAD commit, and stale drafts. No Python → gather the same inputs by hand and say so.
3. Reconcile `intent.md` — the CDO's distilled working position. If the pre-pass flags it stale (newest doctrine entry newer than its `Refreshed:` stamp) or absent, update or draft it from `{product_docs}` + doctrine *before* drafting cards — the file is yours to maintain; alignment without a baseline is just opinion.

Before drafting, three standing duties:

- Read `patterns.md` — Marshal's unconfirmed hypotheses: recurring escalation types, shapes that stall, how the Operator actually decides.
- Missing-source rule — any grounding store the pre-pass warns about (doctrine, patterns, ledger, git) is **proceed and flag**, never block: flag the card `ungrounded:{store}` and let the routing decide.
- Hard-stop signal — a route-to-`cdo-setup` stop that can resolve `{orchestration_dir}` drops `signals/align-blocked-{ts}.md` before exiting, so `cdo-watch intake` folds the wedge into triage instead of the leg silently re-failing each drain.

## Select Items

The pre-pass's `worklist` is your selection — `[ ]` markers only; `[A]` (draft filed) and `[?]` (recorded undraftable) items list under `skipped`. `--story` re-selects any key regardless of marker — that's the re-draft / corrected-back path. Empty worklist → say so and exit; don't invent work.

## Ground the Read (before drafting)

Fresh eyes means actually looking — at the spec *and* the ground it lands on. Per selected item, gather the catalog's five sources — source material (story file under `{story_location}`, epic/spec, sprint content), codebase anchors, externals, card corpus, calibration — per `references/grounding.md`; its rule of thumb: **anything a fix loop would rediscover mid-flight, discover now.** Batch the five reads in one pass per item (parallel delegated research when subagents exist), then draft serially so same-batch `deps` edges and duplicates stay visible. An item with no readable source is a flag, not a block — draft from the backlog line and flag the gap. Every card carries the pre-pass's `head_commit` in `grounded_against` — a stale read is detectable at dispatch.

**Interrogate, then position (the sixth read).** The interrogation, closing duties, and six-axis rubric live in `references/grounding.md`, loaded with the catalog — the mechanics that touch the card: scope implying more than one dispatch arc flags `oversized` — advisory, never a refusal — plus a `## Suggested Split` block naming keys + clean deps (heuristics: `references/sizing-flags.md`); a trip on any Marshal's Read axis emits `axis-trip:{axis}` (flags route to Needs Attention; the check is structural, not rhetorical); adjacent unowned work lands in `gaps` on the filing payload, flagged on the card.

The card the Operator reviews is this position. Their `confirm` means "your read is right" — not "the spec exists."

**Draftable vs undraftable:** a card is undraftable only when no defensible position exists — no readable source *and* no legible intent. Uncertainty, missing anchors, and disputes are flags on a filed card, never reasons to withhold; undraftable items go in the payload's `undraftable` list with a reason — the script marks them `[?]` so they stop re-scanning as if merely unaligned.

## Draft Cards

Per item, draft a card from `assets/alignment-card-template.md` — the template owns the section list and the Execution Surface token contract: Marshal's Read is the position from Ground the Read (the part the Operator is actually reviewing), System Context its technical analog, Questions are judgment calls only paired with your recommended answer ("None — recommend confirm as drafted" is valid), and every remaining section the template names is required — a card that can't produce all sections isn't draftable (sizing follows `cdo-code-e2e` `lite|full` semantics).

- **Contract frontmatter** — the YAML block is the machine-comparable surface dispatch and drift-watch diff: `deps`, `touches`, `emits`, `externals`, `declared_surface`, `grounded_against`. Keep it literal and honest; the filing script routes drift between `declared_surface` and the body to Needs Attention.
- **Visual preview (UI-affecting items — including backend work whose state surfaces in the UI)** — two artifacts from the same grounded read, and the card is **not draft-complete until both resolve**: the **wire** per `references/wireframe.md` (build wire objects, call `wiretext:create_wireframe`, embed the URL in the card, pass it as `wireframe` in the filing JSON — a confirmed card's URL satisfies the pipeline's wireframe gate) and the **mock** per `references/design-mock.md` (one self-contained HTML file on the project's real design tokens, framed in the environment the surface lives in; pass the produced file or directory as `mock` in the filing JSON — the script stages it at `alignment/drafts/assets/{key}/` and owns the card's Mock line). `n/a — no UI surface` on both for non-UI items; `unavailable — {reason}` when production genuinely fails. A missing wiretext does not excuse a missing mock — the asymmetry check is at File.

## Co-sign (when cdo-product is installed)

Every card needs a second signature **before filing** — when `{project-root}/.agents/skills/cdo-product/SKILL.md` exists, run its `co-sign` capability on each drafted card per `references/co-sign.md`; missing dept → file unsigned and say so (a gap, not a block).

## File

File **incrementally** — per card or in small chunks as they're signed, not one end-of-run batch: a run that dies mid-drain keeps everything already filed. Write `cards.json` under a temp dir and file it — the payload schema (bare array vs `{"cards", "undraftable", "gaps"}` envelope), mock staging, and every contract check the filer enforces live in `scripts/file-cards.py`'s module docstring; read it before assembling the payload.

```bash
uv run scripts/file-cards.py --orchestration-dir "{orchestration_dir-resolved}" --cards {temp}/cards.json --backlog-map '{backlog_map as JSON}'
```

`--dry-run` previews routing without writing. Validation is batch-wide and named — a bad card fails the batch rather than half-filing. No Python → do the same by hand and say so.

## Report

The receipt's `filed_count`/`attention_count`/`routine_count` split, the lowest-confidence items with their flags in one line each, mocks staged (and any mock paths that failed to resolve), gap findings (persisted to `gap-findings.md`), undraftable items with their reasons (marked `[?]`), stale drafts the pre-pass surfaced, the receipt's `suggest` next-leg pointer, and anything the pre-pass warned about — nothing load-bearing lives only in the spoken report. Then run `{workflow.on_complete}` when non-empty.
