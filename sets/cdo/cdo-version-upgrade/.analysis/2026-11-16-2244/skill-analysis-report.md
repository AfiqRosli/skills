# Analysis Report: C:/Core/Businesses/skills/sets/cdo/cdo-version-upgrade

Generated: 2026-11-16 · Schema: 2

**Grade: Good**

> Faithful vendored port that runs and wires correctly — but 4 high findings collapse to two root causes: deterministic mechanics are re-derived per-run in the prompt instead of shipped as scripts (the org's own standard), and there is no headless story under cdo-platform's advertised -H contract.

The port is lean (SKILL.md 227 tokens), faithful to upstream, correctly wired into cdo-platform via the sibling-delegate pattern, and preserves the deploy-boundary/sprint-boundary doctrine intact. Its primary opportunity is structural: the workflow already fully specifies three deterministic jobs (version-pair resolution, partition+renumber, verification) that sibling cdo skills ship as scripts — plus it advertises pipeline invocation while dead-ending under headless.

| Severity | Count |
| --- | --- |
| Critical | 0 |
| High | 4 |
| Medium | 4 |
| Low | 9 |

## Themes

### 1. Mechanics belong in shipped scripts, not per-run prompt derivation

- Root cause: The workflow fully specifies three deterministic jobs — resolve the version pair + classify stories, partition/renumber the artifacts, verify the result — then tells the executor to re-derive those scripts inline on every run over files that can be 2000+ lines and get destructively rewritten. Sibling cdo skills ship exactly this class of script (shape-story.py, sprint-status.py, manifest.py); fork-drift only diffs SKILL.md so adding scripts/ trips no gate.
- Fix: Ship scripts/: resolve-upgrade.py (emits version pair, skew case, terminal/non-terminal partition, spec list as JSON), partition-renumber.py (the already-written pseudocode transform, judgment inputs as CLI args), verify-migration.py (the 8 post-checks as {check, pass, details} JSON with a --dry-run/pre-flight mode). Prompt keeps only the judgment: reclassification override, epic order, flag review.
- Findings:
  - `determinism-1` Entire partition+renumber transform is scripted inline per-run instead of shipped — `references/workflow.md:7, 51-66, 77, 122-161, 196`
  - `determinism-2` Verification checklist is scripted inline per-run instead of shipped — `references/workflow.md:163-172`
  - `determinism-3` Version-pair resolution and story classification done by hand-scanning fully-loaded files — `references/workflow.md:24-47, 92-94`
  - `enhancement-2` Add scripted pre-flight validation before mutation (plan-validate-execute) — `references/workflow.md:Step 1 / before Steps 2-7`

### 2. Undefined behavior under cdo-platform's -H contract

- Root cause: cdo-platform advertises --headless for every capability with machine-readable JSON output, but the delegate mandates three interactive inputs (sprint-start confirmation, version-pair confirmation, Proceed y/n + epic order) and emits a markdown report. An automator invoking `cdo-platform version-upgrade -H` hits undefined behavior on a file-rewriting workflow.
- Fix: Pick one and declare it: (a) -H returns blocked + reason ('sprint migration requires Operator confirmation') in references/version-upgrade.md — one clause matching the dept's machine-refusal contract; or (b) give the delegate a real headless path — new_version/epic_order params with computable defaults, assumptions logged as typed entries, minimal JSON return — matching cdo-code-e2e's three-mode table.
- Findings:
  - `enhancement-1` Add a headless invocation contract for the single gate — `SKILL.md:On Activation + references/workflow.md:Step 1`
  - `architecture-1` Delegate has no headless path under cdo-platform's advertised -H contract — `SKILL.md:14-16 + references/workflow.md:91-115`

### 3. Recap sections duplicate rules already enforced at point of use

- Root cause: KEY RULES restates all seven rules verbatim from inline guards; TROUBLESHOOTING re-indexes the same remedies by symptom; the status-flow section re-lists the partition sets; emphasis (ALWAYS, Do-NOT) stands in for missing failure rationale. Three places now hold the same rules and can drift — inherited verbatim from upstream.
- Fix: Truncate-then-delete: cut KEY RULES to a one-line pointer (or drop it), keep TROUBLESHOOTING's symptom->fix shape only if it earns its place, truncate status-flow to the one net-new clause (migrated stories keep status verbatim), reframe ALL-CAPS rules as the failure they guard. Coordinate with upstream so fork-drift stays honest — or accept the diff as a deliberate port.
- Findings:
  - `leanness-1` KEY RULES is a pure recap section — `references/workflow.md:194-202`
  - `leanness-2` TROUBLESHOOTING restates inline guards verbatim — `references/workflow.md:213-219`
  - `leanness-3` Status flow reference restates the partition block — `references/workflow.md:68-73`
  - `leanness-4` ALL-CAPS ALWAYS and stacked Do-NOTs shout where failure rationale would carry — `references/workflow.md:64, 77, 197`
  - `enhancement-4` Consolidate the duplicated rules surface (KEY RULES vs TROUBLESHOOTING vs inline) — `references/workflow.md:KEY RULES + TROUBLESHOOTING sections`

### 4. Write-path safety gap on the two in-place archive rewrites

- Root cause: The skill mandates copy-verify-delete for spec files but rewrites the old epics file and old sprint status in place — a mid-write failure on a 2000+ line archive truncates the only remaining copy of terminal-story content before the Step 8 check runs.
- Fix: Extend the same discipline: write archived output to `{old_file}.new`, run the parse/count checks on it, then rename over the original — a few lines inside the same transform script.
- Findings:
  - `enhancement-3` Extend copy-verify-then-replace to the two archived files — `references/workflow.md:Steps 6-7`

### 5. Vendored-copy bookkeeping gaps

- Root cause: Port-fidelity loose ends: no resolution-rules block so `{project-root}`/`{Channel}` are undefined in the carved workflow; fork-drift diffs SKILL.md only, leaving ~94% of the forked content (references/workflow.md) unmeasured; release_train_file and the `epics-beta-` prefix are hardcoded while sibling artifact paths are config-resolved.
- Fix: Stamp the canonical Resolution rules block into SKILL.md + a one-line {Channel} anchor in workflow.md; extend the fork-drift pair to diff workflow.md against references/workflow.md; resolve the release-train path from bmm config (or declare the literals permanent protocol constants) — no customize.toml surface needed.
- Findings:
  - `architecture-2` No resolution-rules block; carved workflow uses undefined placeholders — `SKILL.md (absent); references/workflow.md:15,26,28-31`
  - `architecture-3` fork-drift.py pair registration diffs SKILL.md only — workflow drift invisible — `cdo-code-e2e/scripts/fork-drift.py:43,82-84`
  - `customization-1` release_train_file hardcoded while sibling artifact paths are config-resolved — `references/workflow.md:15-20 vs :26`
  - `customization-2` `epics-beta-` filename prefix bakes the channel name literally — `references/workflow.md:33-34, 208`
  - `customization-3` Workflow produces artifacts and stops — on_complete candidate — `references/workflow.md:162-189`

## Strengths

- Deploy-boundary vs sprint-boundary doctrine preserved end-to-end — the skill can only be triggered by an Operator sprint-start, and both siblings now cross-reference correctly
- Genuinely non-inferable mechanics carried forward intact: last-paren-group (was X.Y) injection, hyphenated-status parsing (\S+ not \w+), copy-verify-delete ordering, done-vs-spec reclassification
- Single confirmation gate covering both decisions (version pair + epic order) — right-sized human checkpoint for a destructive partition
- Correct vendored wiring: name, 'CDO-owned copy' description, delegates-when-installed registration, and dept routing all match the sibling-delegate pattern (cdo-code-e2e precedent)
- Improved over upstream layout: workflow carved into references/ per house path standards; SKILL.md at 227 tokens is far under budget

## Recommendations

1. Ship the three deterministic scripts (resolve-upgrade, partition-renumber, verify-migration) with --dry-run/pre-flight — highest leverage: clears 4 findings including both determinism highs, and makes the headless path trivially definable (resolves: determinism-1, determinism-2, determinism-3, enhancement-2)
2. Define the -H contract — either blocked-refusal in the delegation doc or a param-driven headless path with JSON return; one clause either way (resolves: enhancement-1, architecture-1)
3. Write archived files to .new siblings, verify, then rename — extends the skill's own copy-verify-delete rule to the two in-place rewrites (resolves: enhancement-3)
4. Trim recap sections per leanness findings and reframe emphasis as failure rationale — decide upstream-vs-vendored divergence first since the sections are identical to the original (resolves: leanness-1, leanness-2, leanness-3, leanness-4, enhancement-4)
5. Bookkeeping pass: Resolution rules block + {Channel} anchor, fork-drift secondary-file diff for workflow.md, release-train path via config or documented literal (resolves: architecture-2, architecture-3, customization-1, customization-2, customization-3)

## Experience

- **Operator sprint-start via dept** — Operator declares new sprint -> cdo-platform version-upgrade -> delegate confirms version pair + epic order -> partition/renumber -> archive -> verify -> summary report
- **Direct invocation** — 'bump version'/'new sprint version' -> skill resolves pair -> single gate -> transform -> verify -> report
- Headless: No defined -H path today — the delegate dead-ends at interactive gates; needs either a blocked-refusal or a param-driven JSON return under cdo-platform's -H contract.

## Findings

### High (4)

#### determinism-1 — Entire partition+renumber transform is scripted inline per-run instead of shipped

- Lens: determinism
- Location: `references/workflow.md:7, 51-66, 77, 122-161, 196`
- Evidence: The workflow thrice instructs 'script it, don't hand-edit' (lines 7, 77, 196) — the fenced pseudocode block and mechanical-rules list already fully specify the transform, so every invocation pays generation cost to re-derive a script whose mis-derivation silently corrupts sprint artifacts during a destructive migration.
- Recommendation: Ship scripts/partition-renumber.py implementing the already-specified transform; prompt passes judgment inputs (new_version, epic order, reclassifications) as args. Precedent: cdo-setup/scripts/migrate-sprint-keys.py, sprint-status.py. Fork-drift diffs SKILL.md only, so scripts/ trips no gate.

#### determinism-2 — Verification checklist is scripted inline per-run instead of shipped

- Lens: determinism
- Location: `references/workflow.md:163-172`
- Evidence: 'Script the verification — counts, not eyeballs' precedes 8 pass/fail checks, each with one correct answer for a given file state — canonical post-processing script work, and the only safety net before/after destructive deletes.
- Recommendation: Ship scripts/verify-migration.py emitting {check, pass, details} JSON; prompt consumes the JSON and renders the report template.

#### enhancement-1 — Add a headless invocation contract for the single gate

- Lens: enhancement
- Location: `SKILL.md:On Activation + references/workflow.md:Step 1`
- Evidence: The skill is 'invoked by the delivery org's pipeline' but dead-ends interactive-only at 'Confirm the user is starting a new sprint' and 'Proceed? (y/n)'. Both gate questions have computable defaults, so a supplied new_version/epic_order + confirm flag can replace them.
- Recommendation: Define the headless path: accept new_version (default from resolution order), epic_order (default: preserve existing), confirmation bypass; emit the Version Bump Plan + minimal JSON result with assumptions logged.

#### architecture-1 — Delegate has no headless path under cdo-platform's advertised -H contract

- Lens: architecture
- Location: `SKILL.md:14-16 + references/workflow.md:91-115`
- Evidence: cdo-platform's Args declare --headless for all capabilities with JSON-verbatim output and machine-readable refusals; the delegate mandates three interactive inputs and emits markdown. Sibling cdo-code-e2e defines a full three-mode gate-policy table.
- Recommendation: Either declare the capability interactive-only under -H (blocked + reason in references/version-upgrade.md) or give the delegate a real headless path for sibling parity.

### Medium (4)

#### determinism-3 — Version-pair resolution and story classification done by hand-scanning fully-loaded files

- Lens: determinism
- Location: `references/workflow.md:24-47, 92-94`
- Evidence: A fully-specified 3-branch decision tree (newest version with all three artifacts, version-core comparison, current.sprint presence) plus terminal-set partition over fully-loaded 2000+ line files — deterministic extraction work the confirmation template only needs as counts and key lists.
- Recommendation: Ship scripts/resolve-upgrade.py emitting {old_version, candidate_new_version, skew_case, deploys_under_old, terminal, non_terminal, spec_files, counts}; keep reclassification, epic order, and oddity-flagging in the prompt.

#### enhancement-2 — Add scripted pre-flight validation before mutation (plan-validate-execute)

- Lens: enhancement
- Location: `references/workflow.md:Step 1 / before Steps 2-7`
- Evidence: Nothing checks up front that input files exist and parse, statuses are in the known set, spec files exist per non-terminal story, or renumbered keys won't collide — on files rewritten in place. The human 'y' is currently the only pre-mutation validator.
- Recommendation: Extend the transform script with pre-flight checks emitted in the plan (optionally a --dry-run that writes nothing — doubles as the safe headless entry point).

#### enhancement-3 — Extend copy-verify-then-replace to the two archived files

- Lens: enhancement
- Location: `references/workflow.md:Steps 6-7`
- Evidence: Spec files get copy-verify-delete, but old epics and old sprint status are rewritten in place — a mid-write failure truncates the only remaining copy of terminal-story content before verification runs.
- Recommendation: Write to `{old_file}.new`, run Step 8 checks on it, rename over the original.

#### leanness-1 — KEY RULES is a pure recap section

- Lens: leanness
- Location: `references/workflow.md:194-202`
- Evidence: All seven rules restate content already enforced at point of use (scripted partition x3, B&E-last x5, was-traceability x6, archive-not-delete, verbatim bodies, user epic order, copy-verify-delete). Step 8 already serves as the verification checklist.
- Recommendation: Delete, or truncate to a one-line pre-flight pointer. Identical to upstream — coordinate divergence deliberately.

### Low (9)

#### enhancement-4 — Consolidate the duplicated rules surface (KEY RULES vs TROUBLESHOOTING vs inline)

- Lens: enhancement
- Location: `references/workflow.md:KEY RULES + TROUBLESHOOTING sections`
- Evidence: KEY RULES items 1-3, 5, 7 restate the mechanical-rules block nearly verbatim; all five TROUBLESHOOTING rows restate inline guards. Rules now live in two or three places that can drift.
- Recommendation: Keep TROUBLESHOOTING (diagnostic shape earns its place) and cut KEY RULES to what isn't already stated, or drop it.

#### architecture-2 — No resolution-rules block; carved workflow uses undefined placeholders

- Lens: architecture
- Location: `SKILL.md (absent); references/workflow.md:15,26,28-31`
- Evidence: No `## Resolution rules` block (sibling cdo-platform stamps one); the carved file uses `{project-root}` and `{Channel}` with no local definition — inherited verbatim from upstream.
- Recommendation: Stamp the canonical Resolution rules block into SKILL.md and add a one-line {Channel} anchor in workflow.md.

#### architecture-3 — fork-drift.py pair registration diffs SKILL.md only — workflow drift invisible

- Lens: architecture
- Location: `cdo-code-e2e/scripts/fork-drift.py:43,82-84`
- Evidence: The pair `project-version-upgrade -> cdo-version-upgrade` registers, but check_forks diffs only SKILL.md — ~94% of the forked content (references/workflow.md, relocated per path standards) is never measured.
- Recommendation: Extend the pair entry or add a per-pair secondary-file map to also diff workflow.md under the same name normalization.

#### leanness-2 — TROUBLESHOOTING restates inline guards verbatim

- Lens: leanness
- Location: `references/workflow.md:213-219`
- Evidence: All five rows duplicate rules stated where the failure occurs; no new remedy exists in the table — same content re-indexed by symptom.
- Recommendation: Delete or truncate to a pointer line.

#### leanness-3 — Status flow reference restates the partition block

- Lens: leanness
- Location: `references/workflow.md:68-73`
- Evidence: The lifecycle arrow and two bullet lists repeat the TERMINAL/NON_TERMINAL sets defined ten lines earlier; the one net-new fact is status-verbatim-on-migration.
- Recommendation: Truncate to: 'Migrated stories keep their status verbatim — a review story stays review.'

#### leanness-4 — ALL-CAPS ALWAYS and stacked Do-NOTs shout where failure rationale would carry

- Lens: leanness
- Location: `references/workflow.md:64, 77, 197`
- Evidence: 'Bugs & Enhancement is ALWAYS last' and 'Do NOT perform dozens of manual edits' rely on emphasis; the B&E-last rule never states why it holds, so a reader may optimize it away.
- Recommendation: Reframe each shout as the failure it guards (e.g. B&E is the fixed catch-all position sprint tooling assumes).

#### customization-1 — release_train_file hardcoded while sibling artifact paths are config-resolved

- Lens: customization
- Location: `references/workflow.md:15-20 vs :26`
- Evidence: Artifact dirs resolve from _bmad/bmm/config.yaml but release-train.json is baked as a literal — the same literal is baked into cdo-version-change-for-production and cdo-git-quick-push, so a relocation forks the whole set.
- Recommendation: Resolve the release-train path from bmm config alongside the artifact dirs — extend the existing channel, no customize.toml needed.

#### customization-2 — `epics-beta-` filename prefix bakes the channel name literally

- Lens: customization
- Location: `references/workflow.md:33-34, 208`
- Evidence: Sprint IDs carry {Channel}-{version} and current.name supplies the channel at runtime, yet the epics prefix is literally 'beta' — ambiguous if the train name moves past Beta.
- Recommendation: Derive the prefix from the resolved channel, or declare 'epics-beta-' a permanent literal in FILE NAMING CONVENTIONS — protocol constant, not a customize surface.

#### customization-3 — Workflow produces artifacts and stops — on_complete candidate

- Lens: customization
- Location: `references/workflow.md:162-189`
- Evidence: Migrated files are left uncommitted with no handoff to the set's commit+tag+push owner (cdo-git-quick-push).
- Recommendation: If a customize.toml ever exists, on_complete ('hand the migrated tree to cdo-git-quick-push') earns its place; today the delegating pipeline owns sequencing — option, not gap.
