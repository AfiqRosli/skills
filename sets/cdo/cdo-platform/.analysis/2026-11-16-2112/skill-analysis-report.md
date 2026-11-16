# Analysis Report: C:\Core\Businesses\skills\sets\cdo\cdo-platform

Generated: 2026-11-16T21:20:00+00:00 · Schema: 2

**Grade: Fair**

> Lean, well-gated release router with a genuinely deterministic spine — but shared-template surfaces (produce, headless, consult intake) resolve to nothing in this dept, and the path conventions those surfaces depend on were never stamped.

cdo-platform's strength is its script backbone: land/push-lane/advance-lane carry CAS, FF-only, and honest-refusal semantics with real tests, and SKILL.md stays a lean 709-token router. Its primary opportunity is convergence debt — capabilities and args stamped from shared cdo templates (produce, --headless, consult intake) that dead-end here, plus prose gates (verified-check, rollback runbook) the scripts could enforce deterministically.

| Severity | Count |
| --- | --- |
| Critical | 0 |
| High | 5 |
| Medium | 10 |
| Low | 8 |

## Themes

### 1. Path conventions never stamped

- Root cause: SKILL.md and the carved references use `./`-prefixed paths and bare cross-skill script names, but no Resolution rules block tells the reader where paths resolve from — so `./scripts/env-scan.py` invoked from references/ or the project root misresolves, and `dispatch.py`/`handover.md` in carved files aren't locatable after compaction. Ten of the eleven scan-path findings and two lens findings share this root.
- Fix: Stamp the canonical Resolution rules block in SKILL.md, convert every `./references/` and `./scripts/` to bare skill-root paths, and qualify cross-skill invocations (`{project-root}/.agents/skills/cdo-batch/scripts/dispatch.py`, `{orchestration_dir}/handover.md`, `{orchestration_dir}/capabilities.yaml`).
- Findings:
  - `architecture-2` `./`-prefixed paths violate the bare-path convention and misresolve from inside references/ — `SKILL.md:21,30-35; references/ship.md:13,15; references/push.md:14; references/env-check.md:6`
  - `architecture-3` Multi-file SKILL.md missing the Resolution rules block — `SKILL.md (no Resolution rules section)`
  - `architecture-6` Carved references invoke cross-skill scripts and state files by bare name with no resolvable path — `references/ship.md:24,36; references/rollback.md:9; SKILL.md:21`
  - `enhancement-5` Add the canonical Resolution rules block — root fix for the ten `./` path findings — `SKILL.md (new section); affects SKILL.md:21,30-35 and references/ship.md:13,15`

### 2. Template-stamped surfaces that dead-end in this dept

- Root cause: The cdo skill template declares surfaces this dept never wired: `produce` exists in dept-manifest.yaml and the Devlog note but has no route or reference file; `--headless`/`-H` sits in Args with no defined return contract on the org's only push path; consult.md's escalation offers `shape`/`feed`/`incident` intake capabilities this manifest doesn't register.
- Fix: For each declared surface, wire it or remove it: route `produce {key}` with a references/produce.md (cdo-continuity is the sibling model) or drop it from the manifest; give `-H` the sibling convention contract (emit the capability's output JSON, gates hold as machine-readable refusals); replace consult's phantom intake menu with the real platform-backlog path.
- Findings:
  - `architecture-1` Declared `produce` capability has no route — dispatched platform work dead-ends — `SKILL.md:12,28-35; assets/dept-manifest.yaml:48-51; references/ (no produce.md)`
  - `architecture-4` `--headless`/`-H` declared in Args with no headless path — `SKILL.md:12`
  - `architecture-5` consult.md promises a hand-off to intake capabilities this dept doesn't define — `references/consult.md:44-45`
  - `enhancement-1` Add a headless contract — `--headless`/`-H` is advertised but undefined — `SKILL.md:12 (Args line); absent from all references`
  - `enhancement-2` Remove phantom intake names from consult escalation — `shape`/`feed`/`incident` don't exist in this dept — `references/consult.md:44-45`

### 3. Prose gates the scripts should own

- Root cause: land.py's own docstring warns that prompt-prose chains 'drifted into critical bugs' — yet the org's cardinal-sin gate (ship only `verified` stories) is prompt-only, rollback is a manual git runbook duplicating ledger data, requisition lines are hand-written in a regex-owned format, and a per-activation YAML key check costs a read every run. The push-lane `warnings` NameError (found during this pass, now fixed) is the same class of drift: prose-era code paths nobody exercises until they fail.
- Fix: Apply the determinism test to each: extract `scripts/rollback.py` reading `stories.{key}.lane_sha` (log-grep fallback for legacy ships), add a `--require-status verified` ledger check to ship-commit/land, give env-scan.py a `--file-requisitions` mode, and fold the registration check into `setup.py --check`.
- Findings:
  - `determinism-1` Rollback is a manual git runbook — every step has one correct answer — `references/rollback.md:5-10`
  - `determinism-2` Model hand-writes `## Requisitions` lines in a format a regex owns — `references/env-check.md:13,16`
  - `determinism-3` The verified-gate ('cardinal sin') is enforced by prose, not by the scripts that run it — `references/ship.md:7; scripts/ship-commit.py, scripts/land.py`
  - `determinism-4` Every activation pays a YAML key-existence check for registration — `SKILL.md:21`
  - `synthesis-1` push-lane.py `warnings.append` on an undefined name — latent NameError on fetch-failure path (FIXED this pass) — `scripts/push-lane.py:205`

### 4. Invoker files restating downstream mechanics

- Root cause: SKILL.md's Overview re-explains the mirror model that ship.md owns, and ship.md + push.md both narrate advance-lane.py's reconcile internals (stash taxonomy, checkpoint semantics) — paid on every invocation including capabilities that never touch the lane.
- Fix: Keep each file to the caller's contract — the authority boundary in SKILL.md, the trigger + safety guarantee in ship.md/push.md — and let advance-lane.py's docstring own the implementation.
- Findings:
  - `leanness-1` Overview carries ship.md's mirror mechanics the entry file doesn't need — `SKILL.md:10 (Overview)`
  - `leanness-2` --reconcile internals narrated in both invoking files instead of trusted to the script — `references/ship.md:13 and references/push.md:18`

## Strengths

- Deterministic lane spine: land.py (FF-check→rebase→CAS→advance), advance-lane.py (reconcile lock, wedged-merge self-heal, state-root --ours), push-lane.py (signed-sha-only publish, non-FF guard, carried-unsigned named honestly) — with 28 real-repo tests
- Lean router SKILL.md (709 tokens) with capability-per-reference carving that matches invocation-time relevance
- Honest reporting as a first-class contract: unsigned work riding a push is named, never hidden; refused operations report instead of forcing
- Uniform script conventions: PEP 723 headers, JSON emit, 0/1/2 exit codes, --dry-run on mutating legs

## Recommendations

1. Stamp the Resolution rules block and strip `./` prefixes / qualify cross-skill paths — one convention statement retires the whole finding class (resolves: architecture-2, architecture-3, architecture-6, enhancement-5)
2. Define the `-H` contract in Args (JSON output, gates as machine-readable refusals) — one clause closes the undefined-behavior hole on the push path (resolves: architecture-4, enhancement-1)
3. Wire or remove `produce` (route + references/produce.md, or drop from dept-manifest) and replace consult's phantom intake with the platform-backlog path (resolves: architecture-1, architecture-5, enhancement-2)
4. Extract `scripts/rollback.py` (ledger lane_sha → `git revert --no-edit` → JSON report) and add the already-pushed boundary line (resolves: determinism-1, enhancement-3)
5. Add `--require-status verified` to ship-commit.py/land.py reading flow-ledger.yaml — make the cardinal-sin gate structural (resolves: determinism-3)
6. Give env-scan.py `--file-requisitions` so missing/cards → identical requisition lines (resolves: determinism-2)
7. Trim SKILL.md Overview to the authority boundary and truncate ship.md/push.md reconcile narration to trigger + guarantee (resolves: leanness-1, leanness-2)
8. Small cleanups: fold registration check into `setup.py --check`, un-number the activation roster note, cut rollback's meta-description, compress the frontmatter summary to 5–8 words; keep `.memlog.md` at root (builder convention — document it rather than move it) (resolves: determinism-4, leanness-3, leanness-4, architecture-8, architecture-7, enhancement-4)

## Experience

- **ship** — card-verified story → ship-commit → land FF-only on cdo-lane → mirror advance
- **push** — Operator signs Pre-deploy → push-lane resolves newest signed lane_sha → non-FF guard → push → ledger stamps + mirror heal
- **rollback** — shipped story turns out wrong → manual git revert runbook → journal + quarantine
- Headless: -H is declared in Args but undefined anywhere — the org's only origin-push path has no machine-readable refusal contract.

## Findings

### High (5)

#### architecture-1 — Declared `produce` capability has no route — dispatched platform work dead-ends

- Lens: architecture
- Location: `SKILL.md:12,28-35; assets/dept-manifest.yaml:48-51; references/ (no produce.md)`
- Evidence: dept-manifest.yaml declares `produce: entry: cdo-platform` ('a confirmed platform item (env fix, deploy hardening, infra task) is work to execute'), SKILL.md's Devlog note describes 'the pipeline's `produce` capability invok[ing] this dept under `cdo-batch`', and cdo-batch's dispatch prompt invokes it — yet the Capability Routing table has no `produce {key}` row, Args omits it, and references/produce.md does not exist. The fallback route is `consult {…}` / no args, which is contractually read-only. Sibling cdo-continuity has `produce {key}` → `references/produce.md` under the identical devlog note.
- Recommendation: Add `produce {key}` to Args and the routing table, and create references/produce.md (cdo-continuity/references/produce.md is the sibling model) — or remove `produce` from dept-manifest.yaml and the Devlog note if platform items are deliberately never dispatched.

#### architecture-2 — `./`-prefixed paths violate the bare-path convention and misresolve from inside references/

- Lens: architecture
- Location: `SKILL.md:21,30-35; references/ship.md:13,15; references/push.md:14; references/env-check.md:6`
- Evidence: Principles: 'All file references in a skill use bare paths from the skill root.' SKILL.md routes via `./references/ship.md`, `./scripts/setup.py`; reference files invoke `./scripts/advance-lane.py`, `./scripts/land.py`, `./scripts/ship-commit.py`, `./scripts/push-lane.py`, `./scripts/env-scan.py` — from inside references/, `./` reads as references/scripts/ (nonexistent) or as CWD-relative, so `uv run ./scripts/env-scan.py` run from the project root fails outright. (scan-paths' flag on `refs/heads/cdo-lane` at ship.md:13 is a false positive — a git ref, not a file path.)
- Recommendation: Strip the `./` prefix to bare skill-root paths everywhere (`references/ship.md`, `scripts/env-scan.py`, `uv run scripts/push-lane.py …`).

#### determinism-1 — Rollback is a manual git runbook — every step has one correct answer

- Lens: determinism
- Location: `references/rollback.md:5-10`
- Evidence: Execute steps instruct the model to run `git log --grep "cdo {key}"`, choose a revert range, run `git revert`, then journal — but the ledger already stores the exact commit (`stories.{key}.lane_sha` journaled by the ship leg). Commit identification is a ledger read, not a log-eyeball; range selection, revert, and conflict detection are all returncode-driven.
- Recommendation: Extract `scripts/rollback.py` on the land.py/push-lane.py pattern — resolve `stories.{key}.lane_sha` from flow-ledger.yaml (log-grep fallback for legacy ships), `git revert --no-edit`, report JSON `{key, revert_commit, conflicts}`; leave journaling to the existing dispatch.py/handover.py calls.

#### enhancement-1 — Add a headless contract — `--headless`/`-H` is advertised but undefined

- Lens: enhancement
- Location: `SKILL.md:12 (Args line); absent from all references`
- Evidence: `--headless`/`-H` appears exactly once — the Args line — with no semantics anywhere. Sibling dept skills define it inline (cdo-delivery 'pure JSON', cdo-review 'presentation only', cdo-code-e2e 'BLOCKED: <gate>'). An automator invoking `cdo-platform push -H` has undefined behavior on the org's only origin-push path, and prompt-level refusals like 'refuse and say why' have no non-interactive surface. All five capabilities are script-backed — easily adaptable.
- Recommendation: One clause in Args: '-H emits the capability's Output JSON verbatim; gates still hold — unverified ship, unsigned push, and prod asks return blocked with reason, never prompt; consult -H is presentation-only'.

#### synthesis-1 — push-lane.py `warnings.append` on an undefined name — latent NameError on fetch-failure path (FIXED this pass)

- Lens: determinism
- Location: `scripts/push-lane.py:205`
- Evidence: When `git fetch origin {lane}` fails but a cached `origin/{lane}` tip exists, the code appends to `warnings` — a name never defined in cmd_run (only `plan["warnings"]` is built later). Result: NameError → exit 2 via the top-level handler instead of the intended stale-origin warning. Off-lens observation from the determinism pass, verified in source.
- Recommendation: Fixed during this analysis: `warnings` initialized early in cmd_run and merged into `plan["warnings"]` once; the post-push heal now also surfaces `stash_pop` conflicts/deferred states the same way land.py does. Tests: 8/8 push-lane green.

### Medium (10)

#### leanness-1 — Overview carries ship.md's mirror mechanics the entry file doesn't need

- Lens: leanness
- Location: `SKILL.md:10 (Overview)`
- Evidence: The second half of the Overview explains mirror operation — 'the local {ship_target} branch mirrors the lane (model B)', 'ship legs and the push leg advance it via advance-lane.py so the Operator's checkout always sees landed work', 'unpushed = origin/{lane}..{lane}' — all of which reappears nearly verbatim in references/ship.md:13 where it is actionable. Paid on every invocation including env-check, rollback, and consult runs that never touch lane mechanics.
- Recommendation: Keep the authority boundary (the non-inferable: local-only landing, Operator-gated origin push, prod sign-off) and cut the plumbing.
- Proposed smallest: The release lane. Verified work lands on `{ship_target}`'s local integration ref `cdo-lane` — never pushed per story. The origin push is a separate Operator-gated leg (`## Pre-deploy Sign-offs` → `push`); production always files a Deploy Sign-off for the Operator. Owns credential logistics (real vs TEMP-CDO placeholders vs missing) and abort-safe reverts of shipped work.
- Predicted delta: Expect no loss on ship/push/rollback runs — mirror model, advance-lane healing, and the unpushed formula all live in ship.md where they're used. At most, a consult answer given without loading a reference loses the 'Operator checkout sees landed work' rationale. Route to variant eval to confirm.

#### leanness-2 — --reconcile internals narrated in both invoking files instead of trusted to the script

- Lens: leanness
- Location: `references/ship.md:13 and references/push.md:18`
- Evidence: ship.md spends ~90 tokens inside the Execute paragraph describing what advance-lane.py --reconcile does internally (stashes dirty paths outside state roots, pops WIP back uncommitted, checkpoints docs/orchestration/_bmad-output, merge-conflict and pop-conflict reporting). push.md:18 restates the same stash/pop/checkpoint semantics a second time.
- Recommendation: Truncate both to the contract: 'a plain-run refusal means org-state churn is blocking the FF — rerun advance with --reconcile; ad-hoc WIP is stashed aside and restored uncommitted after the merge, and a pop conflict is reported with the stash kept (never auto-resolved or dropped).' Keep the trigger and the 'WIP is never lost' guarantee; drop the path taxonomy, which belongs to advance-lane.py.

#### architecture-3 — Multi-file SKILL.md missing the Resolution rules block

- Lens: architecture
- Location: `SKILL.md (no Resolution rules section)`
- Evidence: SKILL.md routes to five reference files plus scripts but never stamps the canonical `## Resolution rules` block the principles require 'into any SKILL.md that references multiple internal files'. Combined with architecture-2, nothing tells the reader where bare paths, `{skill-root}`, or `{project-root}` resolve from.
- Recommendation: Add the canonical block: bare paths/`{skill-root}` resolve from the skill's installed directory; `{project-root}` → project working directory; `{skill-name}` → directory basename.

#### architecture-4 — `--headless`/`-H` declared in Args with no headless path

- Lens: architecture
- Location: `SKILL.md:12`
- Evidence: Args advertises `--headless`/`-H` but no file in the skill defines headless behavior — grep finds the string nowhere else. There is no minimal JSON return contract, which the principles' Headless section requires — acute here because ship/push/rollback make consequential, ordinarily Operator-gated calls.
- Recommendation: Either give `-H` a one-line contract in Args or a Headless section (which capabilities refuse headless — e.g. `push` needs the signature regardless), or drop the arg.

#### architecture-5 — consult.md promises a hand-off to intake capabilities this dept doesn't define

- Lens: architecture
- Location: `references/consult.md:44-45`
- Evidence: Escalation reads 'hand off to this dept's intake capability (`shape`/`feed`/`incident` as the table defines)' — boilerplate shared by all cdo consult files — but cdo-platform's routing table and dept-manifest.yaml define no `shape`, `feed`, or `incident` capability (siblings do: cdo-eng has `shape`, cdo-continuity has `incident`).
- Recommendation: Name the real intake path for platform items (file a line in the platform backlog — it enters intake through cdo-align), or scope the offer to what exists.

#### architecture-6 — Carved references invoke cross-skill scripts and state files by bare name with no resolvable path

- Lens: architecture
- Location: `references/ship.md:24,36; references/rollback.md:9; SKILL.md:21`
- Evidence: ship.md runs `dispatch.py outcome …` and `handover.py write` with no path — the scripts live at `.agents/skills/cdo-batch/scripts/dispatch.py` and `.agents/skills/cdo-handoff/scripts/handover.py`, and ship.md itself uses the full `.agents/skills/cdo-batch/scripts/delivery-note.py` form two lines later. rollback.md journals to bare `handover.md` (actually `{orchestration_dir}/handover.md`); SKILL.md:21 checks bare `capabilities.yaml` (actually `{orchestration_dir}/capabilities.yaml`).
- Recommendation: Qualify each: `{project-root}/.agents/skills/cdo-batch/scripts/dispatch.py`, `cdo-handoff`'s `handover.py`, `{orchestration_dir}/handover.md`, `{orchestration_dir}/capabilities.yaml`.

#### determinism-2 — Model hand-writes `## Requisitions` lines in a format a regex owns

- Lens: determinism
- Location: `references/env-check.md:13,16`
- Evidence: The prompt tells the model to 'file `## Requisitions` entries (`- [ ] KEY — needed by {card}`)' from env-scan.py's JSON — but env-scan.py's own `REQ_RE` re-parses exactly these lines on the next run, so the model is both writer and subject of a format contract; any phrasing drift silently drops the key from `requisitions.pending`.
- Recommendation: Give env-scan.py a `--file-requisitions` mode (or emit `requisition_lines` for mechanical append): identical missing/cards input always yields identical lines.

#### determinism-3 — The verified-gate ('cardinal sin') is enforced by prose, not by the scripts that run it

- Lens: determinism
- Location: `references/ship.md:7; scripts/ship-commit.py, scripts/land.py`
- Evidence: Gate: 'Item must be `verified` in the ledger. Shipping unverified work is the org's cardinal sin — refuse and say why.' The check is `stories.{key}.status == 'verified'` — a single YAML field equality — but neither ship-commit.py nor land.py reads a status, so the org's most important gate depends entirely on prompt compliance. Precedent in the same skill: push-lane.py independently drops signed-but-regressed stories rather than trusting the prompt-side gate.
- Recommendation: Add a `--require-status verified` ledger check to ship-commit.py or land.py reading flow-ledger.yaml, emitting `refused: status={actual}` JSON — same refusal contract push-lane.py already uses.

#### enhancement-2 — Remove phantom intake names from consult escalation — `shape`/`feed`/`incident` don't exist in this dept

- Lens: enhancement
- Location: `references/consult.md:44-45`
- Evidence: consult.md is a shared template stamped across all cdo depts. Its escalation hands off 'to this dept's intake capability (`shape`/`feed`/`incident`)' — but this dept's manifest registers only ship, push, env-check, rollback, produce, consult. The skill hunts capabilities.yaml, finds nothing, and improvises.
- Recommendation: Replace the parenthetical with this dept's actual escalation: 'add a line to the platform backlog — it enters intake through cdo-align like every backlog item.'

#### enhancement-3 — Add the already-pushed boundary to rollback

- Lens: enhancement
- Location: `references/rollback.md:Boundaries`
- Evidence: rollback.md scopes execution to 'the story's commit(s) on the ship lane' — local revert + journal. But for a pushed story, a local `git revert` does not reach origin, and the revert commit has no `pre_deploy.signed_at` so the normal push leg won't carry it — the only documented paths are the `--tip`/`--sha` escape hatches, which rollback never names.
- Recommendation: One boundary line: 'if stories.{key}.pushed is set, the local revert is only half the fix — publishing it is an Operator action (`push --sha {revert-sha}` or a new Pre-deploy Sign-off pass); name the publish path in the rollback journal.'

### Low (8)

#### leanness-3 — On Activation numbers a mixed list and tacks on an unrelated roster note

- Lens: leanness
- Location: `SKILL.md:20-24 (On Activation)`
- Evidence: Items 1-3 are setup guards; item 4 ('Method sources — wdl-release-it + wdl-improve-app per delegates_probe') is advisory-roster bookkeeping with no sequential relationship to them — the numbering signals order where none exists. It also duplicates consult.md's advisory roster incompletely (omits netlify) and in the wrong place.
- Recommendation: Keep 1-3 as the activation sequence. Move the method-sources line into the `consult` row of the Capability Routing table — or delete it, since consult.md already probes capabilities.yaml at invocation — so the roster is stated once, where it fires.

#### leanness-4 — Meta-description of scope adds no reader move

- Lens: leanness
- Location: `references/rollback.md:3`
- Evidence: 'This is the continuity-adjacent duty scoped to release.' describes the capability to itself; the Boundaries section already enforces the actual scope (shipped-only, verified-unshipped goes to kill).
- Recommendation: Cut the sentence. The first line ('A shipped story that turns out wrong gets reverted, not patched forward') already states the outcome.

#### architecture-7 — Session-state `.memlog.md` shipped at skill root

- Lens: architecture
- Location: `.memlog.md`
- Evidence: A dated working-state journal sits at skill root — the path scanner flags it as prompt content that must move to references/, but it is the builder's process memlog, not carved prompt content; sibling cdo-align carries an identical file.
- Recommendation: Keep at root per the builder convention and document the convention (or exclude from packaged skills); moving it to references/ misplaces provenance as prompt material.

#### architecture-8 — Description summary half far exceeds the 5–8-word format

- Lens: architecture
- Location: `SKILL.md:3 (frontmatter description, 325 chars)`
- Evidence: Format is `[5-8 word summary]. [Use when …]`; the summary here is a ~30-word compound sentence. The trigger half is correct — quoted, explicit phrases — so there is no hijack risk; this is a format deviation only.
- Recommendation: Compress the front half to a 5–8-word summary (e.g. 'Release engineering for the cdo pipeline.') and keep the quoted triggers.

#### determinism-4 — Every activation pays a YAML key-existence check for registration

- Lens: determinism
- Location: `SKILL.md:21`
- Evidence: On Activation step 2: 'Verify registration — `capabilities.yaml` `departments.cdo-platform`. Missing → `./scripts/setup.py`.' The model opens capabilities.yaml and checks one key's presence on every invocation.
- Recommendation: Fold the check into `setup.py --check` returning `{registered: bool}` JSON, or have the routed scripts self-report unregistered in their error channel.

#### customization-1 — Integration ref name 'cdo-lane' hardcoded in scripts and prompts

- Lens: customization
- Location: `scripts/land.py:38, scripts/push-lane.py:49, SKILL.md:10, references/ship.md:8,13, references/push.md:3,18`
- Evidence: LANE_REF = "refs/heads/cdo-lane" is a module constant in land.py and push-lane.py, and the name is baked into SKILL.md and the ship/push references. The scripts already accept '--to refs/heads/<ref>', so the value is wireable if ever exposed.
- Recommendation: If customization is ever opted into, expose a lane_ref scalar and invoke scripts with '--to {workflow.lane_ref}'; otherwise accept the fork cost as org doctrine.

#### enhancement-4 — Retain `.memlog.md` at skill root — it is the authoring memlog, correctly placed

- Lens: enhancement
- Location: `.memlog.md`
- Evidence: The path scan flags it as 'prompt file at skill root — move to references/', but per the builder's working-state conventions the workspace IS the skill folder and `.memlog.md` sits beside SKILL.md recording the edit pass (the advance-lane WIP-stash reconcile). It is not progressive-disclosure prompt content.
- Recommendation: Keep `.memlog.md` at root and let it record this analysis pass like the prior build pass.

#### enhancement-5 — Add the canonical Resolution rules block — root fix for the ten `./` path findings

- Lens: enhancement
- Location: `SKILL.md (new section); affects SKILL.md:21,30-35 and references/ship.md:13,15`
- Evidence: SKILL.md references five reference files and nine scripts but never stamps the Resolution rules block the principles file marks canonical 'for any SKILL.md that references multiple internal files', and uses `./`-prefixed paths throughout. Fixing each line without the block leaves the convention unstated — the next edit reintroduces the prefix.
- Recommendation: Stamp the canonical Resolution rules block and convert `./references/x.md` / `./scripts/x.py` to bare paths in the same pass — one convention statement retires the whole class of findings.
