---
name: cdo-code-e2e
description: 'Runs a story end-to-end through the story pipeline — the CDO org-owned copy invoked by cdo-eng produce on dispatch. Use when the user says "run cdo-code-e2e", "run the org pipeline for story X", or when a dispatch routes here.'
---

# cdo-code-e2e

## Overview

This skill carries one story through the complete story pipeline — create, wireframe, predev-confirm, develop, sync, audit, remediate, health-check, user-review, retro, story-sync, done, ship — by orchestrating the existing owner skills in sequence rather than re-implementing them. Act as a pipeline orchestrator: you own sequencing, user gates, fix loops, and the dev log; the owner skills do the domain work.

Forked from `.devin/skills/code-e2e` (2026-10-18) — the org-owned pipeline. Its owner chain resolves from `.agents/skills` first: `cdo-*` vendored skills plus shared BMAD module skills. Upstream changes do not propagate; port fixes between the two copies deliberately.

Communicate in `{communication_language}`; write documents in `{document_output_language}`.

**Args:**

- `--story <key>` — target a specific story key (required for `--headless`)
- `--from <step>` — resume override; re-run starting at the named step. Ensure working-tree state matches the entry point (e.g. `--from development` on a clean tree finds nothing to develop). Old step names alias: `alignment`/`security-audit`/`code-review`/`*-fix` → the merged steps, and `health-check-final` → `health-check`.
- `--yes` — Yolo mode: gates auto-decide with safe policies instead of prompting
- `--headless` / `-H` — fully autonomous; gates apply their auto-policy or emit `BLOCKED: <gate>` and halt
- `--lite` — proportional effort: auto-confirm gates, one combined audit pass at step 6. Auto-applies when the post-dev diff is ≤300 lines across ≤3 files; `--full` overrides
- Bare invocation — resume the first incomplete step in a dev log's pipeline state, or start a new run for the first `backlog` story

**Your output:** A completed story (`done` in both story doc and sprint yaml) plus a dev log under `{project-root}/docs/orchestration/devlog/<Channel>/<date>/<story-key>/` containing `index.md` (pipeline state + change journal) and `retrospective.md`.

## On Activation

Run the context pre-pass — it emits one JSON blob replacing manual globbing and parsing (run `./scripts/resolve-context.py --help` for details; if Python is unavailable, do the equivalent reads yourself):

```bash
python ./scripts/resolve-context.py [--story KEY] [--from STEP] [--lite]
```

It returns: config values, `sprint_status` path, `release`, `story_location`, resolved `story_key` + source (`arg`/`resume`/`backlog`), `story_file`, `devlog_dir`, resume state, backlog list, `mode` (full/lite), and a `preflight` block (owner skills present, `bun`, git, `scripts_present` from package.json, `changed_files` from git). Then read `./references/pipeline.md` and `./references/devlog-conventions.md` and run the pipeline.

**Activation verification — before any state is mutated:**

1. **Pre-flight** — report the `preflight` block as a short table. Missing owner skill → halt and name it (do not discover it at step 6). `bun` missing → warn that health checks can't run.
2. **Story confirmation** — if `story_source` is `resume` or `backlog` (i.e. inferred, not `--story`), confirm the pick with one line: resolved story, release, and what the pipeline will do. This catches both the wrong-story pick and the "e2e meant test suite" mis-trigger. In `--yes`/`--headless`, log the inferred pick and proceed.
3. **Edge cases** — `--story` not in the yaml → halt with the valid keys. `--from` not a step → halt with the step list. Story already `done` → refuse unless `--from` targets a specific later step. Multiple resumable dev logs → ask which. Another run's devlog `in-progress` on the same story → warn about concurrent writes.

## Pipeline

Thirteen steps, executed in order. `./references/pipeline.md` has the full per-step spec — gates, fix loops, logging, and exit conditions. Steps marked **GATE** halt for explicit user approval via `ask_user_question`; never proceed past a gate on silence or assumption. Prefix every gate prompt with `Step N/13` so the user knows where they are.

| #   | Step                | Owner / action                                                | Gate or loop                        |
| --- | ------------------- | ------------------------------------------------------------- | ----------------------------------- |
| 1   | create-story        | `bmad-create-story` + `sprint-status.py`                      | —                                   |
| 2   | wireframe           | `wiretext:create_wireframe` → embed URL in story doc          | **GATE** (UI stories; else logged skip) |
| 3   | predev-confirm      | `ask_user_question` — objective + ACs + external-req check    | **GATE** (merges with step 2's ask for UI stories) |
| 4   | development         | `bmad-dev-story` + `sprint-status.py` transitions             | schema-migration + deps-changed + out-of-scope **GATEs** inside |
| 5   | post-dev-sync       | snapshot + env/lockfile parity + lite-mode decision (no build checks) | hygiene fix loop    |
| 6   | audits              | per-lens parallel subagents: alignment ∥ security agents ∥ 3 review lenses (lite: 1 combined) | — |
| 7   | remediate           | merged severity-ordered fix loop + delta re-verify            | loop until no blocking findings     |
| 8   | health-check        | `./scripts/health-check.py` — the single authoritative run (no dev-server/browser — user runs it) | fix loop until clean |
| 9   | review              | devlog sweep + publish check → present work for user review   | **GATE** (ad-hoc rework loop)       |
| 10  | retrospective       | `devlog.py metrics` + story-scoped retro → `retrospective.md` | —                                   |
| 11  | story-sync          | story doc as-built update + downstream impact annotations     | —                                   |
| 12  | mark-done           | `./scripts/mark-done.py` — story doc + sprint yaml → `done`   | —                                   |
| 13  | ship                | routed ship: `cdo-git-quick-push` (story-scoped tree) ∥ `cdo-git-push` (mixed/multi-commit) + `cdo-git-pr-message` for PRs | **GATE** (auto-defer in non-guided modes) |

## Gate Policies

| Mode       | wireframe                | predev-confirm | external-deps               | deps-changed     | schema-migration      | out-of-scope | review             | ship          |
| ---------- | ------------------------ | -------------- | --------------------------- | ---------------- | --------------------- | ------------ | ------------------ | ------------- |
| Guided     | ask unless card-confirmed URL | ask            | ask if missing              | ask unless card-declared | ask unless card-declared | ask          | ask                | ask           |
| `--yes`    | auto-confirm, log        | auto-approve, log | halt if missing (`BLOCKED`) | halt unless card-declared | halt unless card-declared | defer, log   | auto-approve, log  | defer, log    |
| `--headless` | auto-confirm, log      | auto-approve, log | halt if missing (`BLOCKED`) | halt unless card-declared | halt unless card-declared | defer, log   | auto-approve, log  | defer, log    |

`external-deps` and `deps-changed` are conditional — they only fire when the story needs an unconfigured credential/env var or the change touches `package.json` dependencies; otherwise they log and proceed in every mode. **Card-covered bypass:** when the CDO org's alignment card is confirmed (`card_status: confirmed` from `resolve-item.py` — drafts and rejected archives never count) and declares a surface on its Execution Surface (`schema-migration` / `deps-changed` in `card.declared`), that gate proceeds logged in every mode — it was signed at alignment; re-gating would double-gate a signed contract. A wiretext URL confirmed on the card likewise satisfies the wireframe gate — it gets reused, not regenerated or re-asked. Never auto-apply an *undeclared* schema migration — in non-guided modes it halts the pipeline as `BLOCKED: schema-migration`. Headless runs end with a JSON result: `{story_key, steps_completed[], gates_auto_decided[], pending_human_gates[], findings_fixed, status, ship_pending, block_reason, devlog_path}` — `ship_pending: true` + `pending_human_gates: ["ship"]` tells a cron the run ended waiting on a human gate without scraping devlogs.

## State & Resume

The dev log's `index.md` frontmatter holds the `pipeline:` checklist — the single source of truth for progress. Bookkeep it via `./scripts/devlog.py` (`init` / `set` / `get` / `append` / `metrics` / `snapshot` / `coverage` / `sweep`) rather than editing frontmatter by hand. `--from <step>` overrides the checklist position.

## Hard Rules

- Owner skills are invoked, never re-implemented. If an owner skill is missing, report it and halt — do not silently improvise its job. (Documented adaptations are allowed: step 10 adapts `bmad-retrospective` to story scope, since the owner is epic-scoped; step 6 runs owner skills inside parallel subagents with a compact return contract.)
- **Circuit breaker:** every fix loop gets a maximum of 3 attempts. Still failing → escalate via `ask_user_question`: keep trying / defer-with-reason / halt pipeline. An unconverging loop is the worst silent failure mode — never churn past the budget.
- Sprint yaml edits preserve every existing comment and the traceability style — use `mark-done.py`, which does the surgical edit and prints a diff for verification.
- Secret values never enter context, the dev log, or `.env.example` — check `.env` by key name only; placeholders in the example file.
- Steps 6–8 (audits → remediate → health-check) all run while the story sits in `review` status — the sprint status, distinct from the step-9 review gate. Only step 12 writes `done`.
- Every code change, gate decision, and fix-loop iteration lands in the dev log with context, rationale, and alternatives considered — the log is the audit trail *and* a teaching artifact: a trainee should be able to onboard to the change from the journal alone. Decision entries carry literal Before/After code — prose describing the change is not a substitute.
