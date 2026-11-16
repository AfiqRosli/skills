# Pipeline — Step Specifications

Each step lists its goal, the owner that does the work, what lands in the dev log, and its exit condition. Execute in order. On any step failure that can't be resolved, halt, log the failure in the dev log (`./scripts/devlog.py append` + `set ... blocked`), and tell the user exactly where the pipeline stopped and why.

**Circuit breaker (applies to every fix loop):** max 3 attempts per loop, then escalate via `ask_user_question` — keep trying / defer-with-reason / halt. Non-guided modes: emit `BLOCKED: <step>-fix-loop` with attempts logged and halt (there is no user to escalate to). Never churn past the budget; log the escalation outcome.

**Lite mode (`--lite`, or auto-applied when the post-dev diff is ≤300 changed lines across ≤3 files):** auto-confirm the wireframe, predev-confirm, and review gates (log the decisions); step 6 runs ONE combined audit subagent (style + security + acceptance in a single pass) instead of three owner-skill audits. Everything else is unchanged. Log `lite mode` in the dev log with the diff stats that justified it. `--full` forces the full path.

## Step 1 — create-story

**Owner:** `bmad-create-story` skill.
**Goal:** A complete, context-filled story file exists at `{story_location}/<story-key>.md` and the sprint yaml shows `ready-for-dev`.
- **CDO-shaped stories arrive pre-seeded:** an item dispatched by the CDO module already has its `{story_location}/<story-key>.md` skeleton, a sprint-yaml entry (`proposed` at shape, `backlog` after Operator confirm), and an epics-doc section — the create-story owner's job is then to *enrich* the existing file to full context, never to re-mint the key or clobber the shaped spec.
**Log:** `devlog.py init` the devlog dir first if it doesn't exist, then append a "story created" entry — key, file path, objective summary. Set the sprint status via `python ./scripts/sprint-status.py set --sprint-status <yaml> --story-key <key> --status ready-for-dev` — never hand-edit the yaml.
**Exit:** Story file exists, sprint status = `ready-for-dev` (verify via `sprint-status.py get`).

## Step 2 — wireframe

**Owner:** `wiretext:create_wireframe` MCP tool.

**Goal:** For UI-touching stories, an editable wireframe the user has confirmed; for non-UI stories, an explicit logged skip.

- **Alignment card resolution (all stories, before the UI check):** when the CDO module is configured (`{project-root}/_bmad/config.yaml` `cdo:` section → `orchestration_dir`, default `docs/orchestration`), resolve the story's card once here — `uv run {project-root}/.agents/skills/cdo-setup/scripts/resolve-item.py --orchestration-dir {orch} {story_key}` (story slugs map to their backlog item key automatically). Only `card_status: confirmed` counts — `draft`/`rejected`/`absent`, a missing card, or any resolution failure means unsigned: treat as no card and gate normally (never read tokens or a wireframe off an unsigned card). Its `card.declared`/`card.wireframe` fields feed step 4's gates and the wireframe reuse below.
- **UI surface detection:** `python ./scripts/story-brief.py <story_file>` emits `ui_surface` (advisory verdict + matched terms) — trust it unless the story obviously says otherwise. Backend-only (server routes, stores with no UI, utils, migrations) → log `skipped — no UI surface` and move on.
- **Alignment-confirmed reuse:** if the resolved confirmed card's `card.wireframe` holds a URL, verify it's live (wiretext MCP open/fetch — a dead URL means falling back to generation, not skipping the design check), then embed it in Dev Notes, log `wireframe confirmed at alignment — reused`, and skip generation + gate in every mode (re-asking would be a double gate on a signed card). When `card.mock` is a path (`mock_status: path` — resolve-item only reports `path` when the cited file exists), embed it in Dev Notes as `Mock: {path}` — the visual-fidelity companion the dev implements against alongside the wire. `mock_status: dead-link` means the card cites a file that isn't there — don't embed it; warn that the confirmed card's mock drifted.
- **Wireframe:** Build wire objects from the story's UI requirements *grounded in the real surface* — read the touched page/component and reproduce its current region structure, then mark the delta (objects `name`d after real components, `annotation` carrying the change note, typed components matching what gets built — the standard lives in `{project-root}/.agents/skills/cdo-align/references/wireframe.md`). Call `create_wireframe`, embed the returned editable URL in the story doc's Dev Notes section. A wire sketched from story prose alone is commentary, not design intent — the gate will re-ask on something the user can't hold against the live page.
- **Wiretext unavailable:** if the MCP tool is missing or errors, log `skipped — wiretext unavailable` and continue — an optional step must not dead-end the pipeline.
- **GATE:** Confirm the wireframe design via `ask_user_question` (confirm / iterate / waive). Iterate until confirmed or waived — a waive is a valid decision, log it. For UI stories, merge this ask with step 3's predev-confirm into a single `ask_user_question` call (it supports multiple questions) — one interruption instead of two. Non-guided/lite modes: auto-confirm and log.
- **Log:** Wireframe URL + confirmation outcome, or the skip reason.

**Exit:** Confirmed/waived wireframe URL embedded, or skip logged.

## Step 3 — predev-confirm

**Owner:** Orchestrator — `ask_user_question`.

**Goal:** The user has confirmed what is about to be built, framed in business value — before any code is written.

- Present the story objective and each acceptance criterion translated into the user/business outcome it delivers. Scope boundaries count as outcomes too ("X stays untouched"). `story-brief.py` already extracted the objective + ACs — present from that JSON, don't re-read the file.
- Do not present file lists or task mechanics — this gate is about *what ships and why*, not how.
- **External requirements:** scan the story for third-party services, API keys, and env vars it depends on (e.g. `NEON_API_KEY`, `DATABASE_URL`, a new provider's secret). `python ./scripts/env-parity.py {project-root} --files <story-referenced files>` extracts referenced key names mechanically — run it when the story implies env usage. For each name, confirm the key exists in `{project-root}/.env` — check key *names* only (the `KEY=` prefixes); never read or echo secret values into context or the dev log. A referenced service whose env-var name can't be determined → ask rather than guess. All present → log `external deps satisfied` and continue. Missing → fold it into this gate's `ask_user_question`: the user supplies it, confirms it's configured outside `.env` (Netlify env, CI secrets), or the story can't proceed — a missing credential is a hard blocker, not a waive. Can't be supplied → halt and log the blocker. Non-guided/lite modes: `BLOCKED: external-deps`. Likewise, name any `package.json` dependency changes the story clearly implies (new package, version bump) in the same ask — with the why, not just the what.
- End with a soft tail — "anything else we should account for?" — latent concerns surface here cheaply.
- If the user pushes back, route back to step 1 to revise the story, or halt. Non-guided/lite modes: auto-approve and log.

**Exit:** Explicit user confirmation (or logged auto-approval).

## Step 4 — development

**Owner:** `bmad-dev-story` skill.

**Goal:** All tasks/subtasks implemented, tests passing, sprint status = `review`.

- Set sprint status to `in-progress` at start and `review` at completion via `sprint-status.py set` — same surgical-edit discipline as mark-done.
- **Baseline attribution:** before writing code, note the suite's current health (e.g. run the specs nearest the touched area, or check the last known-green state). Pre-existing failures — like a missing stub from an earlier commit — must be logged as *baseline*, not absorbed into the story's fix loop or mistaken for story-caused breakage mid-remediation.
- As tasks complete, append a dev-log **decision entry** (`devlog.py append --step 4`) per task or logical change — always pass `--step <N>` so `metrics` can attribute step durations deterministically — in the structured format from `devlog-conventions.md` — Context / File / Before / After / Why this approach / Alternatives considered / Watch out for, with literal code snippets in the fenced blocks. Write for a trainee who hasn't seen the codebase: explain the mechanism and the option space, not just the diff. A prose summary alone does not satisfy this — every file the change touched appears in a `**File**`/`**Before**`/`**After**` group with real code (new files show their essential blocks under `**After**`). Lift snippets from what dev-story reports when it carries the code; when the report is summary-level, read the diff or the file so the blocks stay faithful to what actually shipped. Coverage check before moving on: `python ./scripts/devlog.py coverage <devlog_dir>` verifies every code file in the change set is named on a `**File:**` group line in the journal (docs/devlog artifacts excluded by design). At this point the uncommitted tree IS the change set — the default `git status` input is correct. A `fail` result lists the uncovered files — backfill the missing `**File**`/`**Goal**`/`**Gap**` groups before continuing, don't rationalize the gap. Format check follows: `python ./scripts/devlog.py lint <devlog_dir>` verifies heading depth, fence language tags, fields on own lines, and File-group completeness — fix violations, don't rationalize.
- **Schema-migration GATE:** Any change to the Drizzle schema or a new file under `drizzle/` pauses the pipeline for explicit approval before the migration is generated or applied — *unless `schema-migration` is in the confirmed card's `card.declared` (resolved at step 2)*, in which case that surface was signed at alignment: log `schema-migration card-covered — proceeding` and continue in every mode. Undeclared (or unconfirmed/absent card): guided asks; non-guided halts as `BLOCKED: schema-migration`.
- **Deps-changed GATE:** Any `package.json` `dependencies`/`devDependencies` addition or version modification pauses the pipeline for explicit approval *before* install — *unless `deps-changed` is in the confirmed card's `card.declared` (same carve-out: log `deps-changed card-covered — proceeding`, continue)*. Undeclared: guided asks — present the package, the version constraint, why it's needed, and the alternatives considered (prefer a pinned version published ≥7 days ago over a floating range or a brand-new release, and say so when the chosen version doesn't meet that bar); non-guided halts as `BLOCKED: deps-changed`.
- **Out-of-scope GATE:** Work not mapped to a story task/AC pauses for a user decision — extend the story or defer the work. Non-guided modes: defer and log.
- **Env-example parity:** every new env var the implementation introduces lands in `{project-root}/.env.example` — key with an empty or placeholder value, never a real secret. A needed credential surfacing mid-dev that isn't configured → same handling as step 3's external-requirements check (ask in guided; `BLOCKED: external-deps` otherwise).

**Exit:** dev-story completes cleanly — all tasks `[x]` (verify via `story-brief.py` `tasks.done == tasks.total`), tests pass, status `review`.

## Step 5 — post-dev-sync

**Owner:** Orchestrator — bookkeeping only; no type/lint/build run (the single health check at step 8 owns that).

**Goal:** The post-dev change surface is recorded and cheap hygiene checks pass before the audits consume the diff.

- Refresh the changed-file list (`git status --porcelain`) and store the post-dev baseline: `python ./scripts/devlog.py snapshot <devlog_dir>` — ship's story-scope routing compares against this.
- **Env-example parity:** `python ./scripts/env-parity.py {project-root}` — env vars referenced by the changed files must all exist as keys in `.env.example` (`missing_in_env_example`) and `.env` (`missing_in_env`). Gaps are fix targets.
- **Lockfile parity:** a `package.json` dependency change without a matching `bun.lock` update is a fix target — a stale lockfile means installs drift from what was approved.
- Fix hygiene gaps found (circuit breaker applies).
- **Lite-mode decision:** compute changed-lines vs the `--lite` threshold here (post-dev diff exists now) and log the chosen audit depth before step 6. Size is the proxy, risk is the override: any file under `utils/crypto/**`, `middleware/auth*`, `server/**/auth*`, `lib/auth*`, or a path containing `crypto`/`security`/`encrypt` forces full mode regardless of line count — a 2-line crypto change deserves three audit lenses, a 400-line CSS refactor doesn't.

**Log:** Changed-file list + parity results + lite/full audit decision.
**Exit:** Hygiene clean (or fixes applied), audit depth decided.

## Step 6 — audits

**Owner:** Parallel per-lens subagents — the orchestrator owns the fan-out.

**Goal:** Alignment, security, and adversarial review findings over the *same* diff — produced concurrently, reported compactly, with each lens's isolation preserved.

- **Fan out per-lens, not per-owner.** A pipeline subagent can't spawn subagents — so the *orchestrator* spawns one subagent per lens, each loading its owner skill and running exactly one lens's checklist over the diff. Never merge independent lenses into one context: a lens that can see a sibling's reasoning is anchored, and the owners' parallel-agent design exists precisely to prevent that. Every subagent gets: the owner skill's path, the changed-file list + `git diff HEAD` scope, the story file as spec, and `checks_status: not-run`. Subagents review the diff as-is and must not run type-check/lint/build themselves — the single health check at step 8 owns that after remediation.
  - **Alignment → `cdo-alignment-uncommitted-changes` — 1 subagent.** Its phases are sequential by design (each builds on the last), so one context loses no isolation. Through its report phase only — remediation is step 7's job.
  - **Security → `cdo-security-audit-uncommitted-changes` — per-agent lenses + scans + synthesis.** The skill's Phase-3 agents are the lenses; derive the applicable set from the changed-file list per the skill's own skip rules (Weaver + Bastion always; Gateway when `server/**` changes; Nimbus when infra/config/deploy changes; Oracle when AI/LLM features; Sentinel when user-data/auth/data-processing):
    - **N lens subagents** — one per applicable Phase-3 agent, running only that agent's checklist (the checklists are inline in the skill — no persona embodiment needed)
    - **1 scans subagent** — Phase 2 automated scans (`bun audit` + secret scan); Phase 1's triage is already supplied by the envelope
    - **1 synthesis subagent** — Phases 4–5 (cross-domain analysis + report) consuming every lens + scans verdict. Phase 6 remediation stays step 7's.
  - **Review → `bmad-code-review` — 3 subagents, one per named layer:** Blind Hunter, Edge Case Hunter, Acceptance Auditor — each with the envelope pre-answered: mode `uncommitted`, spec = `{story_file}`, story_key = `{story_key}`, checkpoints auto-confirmed. Each lens subagent produces its verdict directly — the skill's step-02 "generate prompt files and HALT" fallback is superseded (that path returns no verdict and fails the exit condition).
- **Residual flattening rule:** if an owner's checklist requires a nested pass the orchestrator can't pre-enumerate, that subagent runs it as an in-context pass — same checklist, same verdict contract. Per-lens is the norm; in-context is the fallback for the unenumerable.
- **Return contract:** each subagent writes its full report to `<devlog_dir>/audit-<lens>.md` (per-agent reports: `audit-security-<agent>.md`, `audit-review-<lens>.md`) and returns ONLY a compact verdict: `{counts_by_severity, findings: [{id, severity, file, line, title, remediation}]}`. The orchestrator merges verdicts — full reports live in the devlog dir, not in context.
- **Lite mode:** one subagent instead — combined style + security + acceptance pass on the diff, same return contract.

**Log:** per-lens severity counts + report paths.
**Exit:** All lens verdicts collected (or the lite verdict).

## Step 7 — remediate

**Owner:** Orchestrator, with re-verification subagent(s).

**Goal:** Every blocking finding resolved across all three lenses — one merged loop, not three.

- Merge all findings into one severity-ordered list: Critical/High + decision-needed → fix now; Medium/Low → defer with a reason logged. Findings on disjoint files may be fixed in parallel. The fix implementation itself may delegate to `cdo-review-implement-refinement` — same skill, but it consumes the merged finding list once, not three separate triage outputs.
- **Re-verify the delta:** after fixes land, spawn a verification subagent scoped to the fix diff only — it confirms each fixed finding and checks the fix didn't open new issues in the same files. Re-running the full audits is not required.
- **Loop:** Fix → delta re-verify → repeat until no Critical/High/blocking findings remain (max 3 attempts → escalate).
- Scoped tests only: `bunx vitest related <changed-files>` (or the changed spec files), never the full suite — step 8 owns regression.

**Log:** Findings → patches applied → items deferred (with why) → re-verification results. Each patch that changes behavior gets its own decision entry — same format as step 4, with Before/After lifted from the fix diff; mechanical one-liners may stay inside the summary entry.
**Exit:** No blocking findings; deferred items journaled.

## Step 8 — health-check

**Owner:** Orchestrator — `./scripts/health-check.py`.

**Goal:** Nothing broke — types, lint, build. This is the run's **single authoritative validation result**: the only health check in the pipeline, run once after remediation so fixes are covered too. The review gate and ship step consume this JSON rather than re-running checks.

- `python ./scripts/health-check.py {project-root} --changed-files <files>` → compact JSON: pass/fail/skip for type-check, lint, build, run in parallel (raw tails only on failure). Missing `package.json` scripts report `skipped`, not `fail` — a config gap, never a fix-loop target. If Python is unavailable, run the `bun run` commands directly; if `bun` itself is missing, pre-flight already fails closed — don't reach this step.
- **`--changed-files` accepts `git status --porcelain` output verbatim** — untracked directories are expanded to the files they contain and lint-ignored paths (`node_modules`, `.nuxt`, `dist`, …) are dropped before eslint sees them. Do not pre-expand by hand.
- **Build is delta-aware:** when `--changed-files` is given and no file is build-critical (`{project-root}/server/**`, `{project-root}/package.json`, `{project-root}/bun.lockb`/`bun.lock`, `{project-root}/nuxt.config.ts`, `{project-root}/netlify.toml`, `{project-root}/scripts/migrate.ts` — the same trigger list `{project-root}/scripts/pre-push-build-validation.sh` uses), the build check reports `skipped` — the pre-push hook re-validates build-critical changes at push anyway, and the dev server is hot-reload. `--force-build` overrides. This means review round-trips on non-critical files (stores, components, tests, docs) re-verify lint+tests only, in seconds.
- **Round-trip re-runs pass the delta, not the whole list:** on a request-changes loop, `--changed-files` should be the files the fix touched, not the full story change set — scoped verification is the point; the authoritative run already covered the rest.
- **Baseline-failure attribution:** when the suite reports failures, classify each as baseline/pre-existing vs story-attributable before the review gate consumes the JSON — a failure silently absorbed as "baseline" is the worst false-negative in the pipeline.
- **No dev-server/browser smoke** — the user runs their own dev server outside this pipeline. Never start a dev server, never open `browser_preview`. Runtime verification is the user's manual pass; log `smoke skipped — external dev server` and move on.
- **Re-check parity:** re-run `env-parity.py` + lockfile parity over the final change set — remediation may have shifted it since step 5.
- Always runs — never skipped (no earlier check exists to fall back on). Fix → re-run until clean (circuit breaker applies).

**Log:** Check results + fixes applied.
**Exit:** All checks clean (skips don't block).

## Step 9 — review

**Owner:** Orchestrator — `ask_user_question`.

**Goal:** The user has reviewed the finished work — and can actually reach the dev log — before the pipeline retros and marks it done. This gate may go back and forth; an approval is the exit, not a timer.

- **Devlog completeness sweep first** — `python ./scripts/devlog.py sweep <devlog_dir>` bundles the mechanical half (pipeline state, `audit-*.md` presence, VitePress registration, journal lint) in one call. The user reviews the finished log, not a stale one:
  - Frontmatter pipeline state is current (every completed step `done`/`skipped`).
  - Coverage check: `devlog.py coverage <devlog_dir> --files <post-dev changed-file list>` must pass — every code file is named on a `**File:**` group line. Always pass `--files` with the step-5 change list, not the live `git status` default — remediation or interim commits can shrink the live tree and silently narrow the tally. Backfill gaps with proper `**File**`/`**Goal**`/`**Gap**` groups before presenting.
  - Audit reports (`audit-*.md`) exist in the devlog dir.
- **Publish check** — the devlog must be navigable in the docs:
  - `<devlog_dir>/index.md` and `docs/orchestration/devlog/index.md` exist, and `devlogSidebar()` is registered in `docs/.vitepress/config.ts` (the `devlog.py init` result reports `vitepress_registered` — fix registration if missing).
  - The sidebar scans the devlog tree at config-eval time. `docs:dev` runs `{project-root}/scripts/dev-docs.mjs`, which spawns the devlog watcher — a running docs server picks up new journals automatically (the watcher touches `config.ts`, VitePress restarts and re-scans). A stale `dist` build still needs `docs:build`. Give the user the direct docs path (`/orchestration/devlog/<Channel>/<date>/<story-key>/`) so they can navigate straight to it.
- **Present for review:** story objective, what shipped (changed files + diffstat), the step-8 health-check verdict, audit findings fixed/deferred, and the devlog path.
- **GATE:** approve / request changes / halt via `ask_user_question`.
  - Request changes → ad-hoc routing sized to the request: a small fix is applied directly, then step 8's health check re-runs and the gate re-presents; substantive work routes back through development → audits → remediate → health-check → re-present. Log each round-trip. Circuit breaker applies per loop.
  - Halt → log `review halted` + reason and stop with state intact.
- Non-guided modes (`--yes`/`--headless`/lite): auto-approve and log — same policy as predev-confirm.

**Log:** Sweep/publish-check results + review outcome (and each rework round-trip).
**Exit:** Explicit user approval (or logged auto-approval).

## Step 10 — retrospective

**Owner:** Orchestrator (story-scoped adaptation of `bmad-retrospective` — documented carve-out; the owner skill is epic-scoped).

**Goal:** A story-level retro written to `<devlog_dir>/retrospective.md` from `./assets/retro-template.md`.

- `python ./scripts/devlog.py metrics <devlog_dir>` emits the mined signals — per-step durations, fix-loop iteration counts, gate outcomes — plus the 3 most recent prior retros' `Carry Forward` sections. Write the narrative from that JSON; don't re-read the journal or glob old retros by hand.
- Keep it lightweight; this is a story retro, not an epic ceremony.

**Exit:** `retrospective.md` written.

## Step 11 — story-sync

**Owner:** Orchestrator.

**Goal:** The story doc describes what actually shipped — implementation drifts from plan during dev and remediation — and subsequent stories know what changed under them.

- **Reconcile the story doc:** compare its tasks/Dev Notes/file lists against the devlog journal and final diff. Where reality diverged (files added or dropped, approach changes, scope shifts), update the affected sections and record the deviation as an as-built note — annotate, don't rewrite history. The `Status:` flip and Change Log line still belong to mark-done.
- **Downstream impact check:** `python ./scripts/downstream-scan.py --epic <epic_doc> --files <changed files> --sprint-status <sprint_status> --story-key <story_key>` pre-passes the epic doc — it flags story sections mentioning the change set's file stems, so you read only the flagged sections instead of every subsequent story. For each affected story, append an impact note to its Dev Notes: `Impact from <story-key>: <what changed> — <what to account for>`. Annotate, don't rewrite their tasks.
- Report the impacted-story list and annotations made; if none, say so.

**Log:** Deviations recorded in the story doc + downstream annotations (or `no downstream impact`).
**Exit:** Story doc current; affected subsequent stories annotated.

## Step 12 — mark-done

**Owner:** Orchestrator — `./scripts/mark-done.py` does the surgical writes.

**Goal:** Both tracking surfaces show the story as done.

```bash
python ./scripts/mark-done.py --story-file <story_file> --sprint-status <sprint_status> \
    --story-key <story_key> --summary "<outcome summary>"
```

- The script sets the story doc `Status:` → `done`, appends a Change Log line, sets `development_status[<key>]` → `done` with a `DONE <date>` + summary appended to the traceability comment, bumps `last_updated`, and prints a unified diff — verify only intended lines changed.
- Report the full pipeline summary to the user — steps run, gates taken, findings fixed, dev log path.

**Exit:** Both files updated; summary delivered.

## Step 13 — ship

**Owner:** `cdo-git-quick-push` or `cdo-git-push` (routed below) + `cdo-git-pr-message` for PRs.

**Goal:** The certified changes don't sit uncommitted — `done` should describe code that landed somewhere.

- **Ship-owner routing** — compare `git status --porcelain` against the story's changed-file set (the devlog snapshot + remediation delta):
  - Everything uncommitted belongs to this story — story code, story doc, sprint yaml, devlog — → `cdo-git-quick-push`: one cohesive unit, one or two commits.
  - The tree contains changes outside the story's scope, version-bump files needing a `chore(release)` split, or the user asks for grouped multi-commit history → `cdo-git-push`: full functionality-grouped commits.
  - Either way, a PR request also invokes `cdo-git-pr-message` for title/body drafted from the dev log.
- **GATE (guided):** one `ask_user_question` call covering — ship or defer; if shipping, confirm the routed owner (quick is offered as default when the tree is story-scoped); and the version-workflow decision when `cdo-version-change-for-production` hasn't run this session (run now / skip / proceed as-is). In `--yes`/`--headless`, defer and log — **never auto-commit, never auto-push.** The gate authorizes *whether* to ship; the push skill then confirms the concrete commit plan (groups + messages) before any `git add` — no commit, not even a local one, lands without user approval.
- **Pre-verified context:** step 8's health-check JSON is the authoritative verification — pass it to the push skill so it does NOT re-run type-check/lint/build. The pipeline already paid that cost; re-running it here is waste, not safety.
- **Journal rides the ship commit — order matters:** after the gate approves and the commit plan is confirmed, write the ship journal entry and `devlog.py set <dir> ship done` **before** `git add` — the devlog `index.md` then lands inside the ship commit and the tree is clean after push. The entry records the approved plan ("shipping <commit summary> to <branch>"), not a claim of success. If the commit/push fails, `set ship blocked` + append the failure — a small follow-up, never a dirty tree left dangling post-push. Never append a post-push "pushed" entry — that's exactly the uncommitted-change-after-push smell this ordering exists to kill.
- **Resume edge case — `ship: done` with a dirty tree:** if a session dies between the journal write and the push, the devlog reads terminal while the ship commit never landed. On resume, a devlog whose steps are all done but `git status` shows uncommitted story files is **not** terminal — re-present the ship gate (verify whether the commit exists via `git log`, then push or re-commit). Check tree cleanliness before treating any all-done devlog as finished.
- Close with a next-story pointer: name the next `backlog` story from the context JSON so the pipeline becomes a conveyor belt, not a dead stop. On deferral, log `ship deferred` — a devlog whose only remaining step is `ship` is terminal for resume purposes (it won't hijack the next bare invocation).

**Exit:** Ship decision executed or deferred-and-logged; next story surfaced.
