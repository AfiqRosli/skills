# Analysis Report: sets/cdo/cdo-align

Generated: 2026-11-16 · Schema: 2

**Grade: Poor**

> Ships clean at draft time, but the Mock contract is not truthful across the card lifecycle — every confirmed card carries a dead mock path that resolve-item surfaces into Dev Notes, and the standard's multi-file mock is unfileable.

The extension's design rules are its strength: the browser-chrome/layer-delta wire convention and the token-grounded mock contract are non-inferable, earn their place, and are wired deterministically at filing. The opportunity is lifecycle truthfulness: apply-decisions moves the mock file on every hop but never rewrites the Mock line that cites it, and nothing downstream existence-checks the claimed path — so the artifact furthest downstream (Dev Notes) deterministically embeds a dead link.

| Severity | Count |
| --- | --- |
| Critical | 1 |
| High | 5 |
| Medium | 13 |
| Low | 12 |

## Themes

### 1. Mock pointer goes stale on every lifecycle move

- Root cause: file-cards.py owns the Mock line at draft time but apply-decisions.py's move_assets relocates the file on archive/defer/resurface/unpark while the card body is written verbatim — the citing line is never rewritten. resolve-item then trusts the stale literal as status `path` with no existence check, and pipeline.md embeds it into Dev Notes. The confirm-edited strip clause inherits the same asymmetry.
- Fix: Pick one fix point: either apply-decisions rewrites `**Mock:**` to the moved destination at every hop (same _set_mock_line surgery file-cards uses), or resolve-item resolves the mock path card-relative instead of trusting the literal. Also: line-scope the wireframe status parse, align Mock regex anchoring writer/reader, warn on move_assets dest.exists(), and clarify the confirm-edited strip clause covers both artifacts.
- Findings:
  - `determinism-1` Mock line is never rewritten when assets move — every confirmed/parked/superseded card cites a dead path — `sets/cdo/cdo-review/scripts/apply-decisions.py:124-138,617-684; sets/cdo/cdo-align/scripts/file-cards.py:238-239`
  - `architecture-1` Mock pointer goes stale on every lifecycle move — dead path reaches pipeline Dev Notes — `sets/cdo/cdo-review/scripts/apply-decisions.py:124-138,370-390,430-435,631-635,680-684; sets/cdo/cdo-setup/scripts/resolve-item.py:96-107; sets/cdo/cdo-code-e2e/references/pipeline.md:25`
  - `enhancement-2` Add: Mock-line rewrite on lifecycle moves — confirmed cards carry a dead mock link — `cdo-review/scripts/apply-decisions.py:669-684; resolve-item.py:97-107; pipeline.md:25`
  - `architecture-5` cdo-review confirm-edited 'strip' leaves stale mock handling ambiguous — `sets/cdo/cdo-review/SKILL.md:48`
  - `determinism-6` Mock sentinel text cross-contaminates wireframe status; writer/reader use different line shapes — `sets/cdo/cdo-setup/scripts/resolve-item.py:85-107 vs sets/cdo/cdo-align/scripts/file-cards.py:68,207`

### 2. file-cards.py mock staging has contract and edge gaps

- Root cause: The staging contract enforces one file renamed to mock.html while the standard advertises a multi-file mock/ dir; several edge inputs (directory path, same-src-as-dest, missing Visual Preview, terminal Wireframe line, cwd-relative source) degrade silently or crash mid-drain, and the placeholder-styling flag is prose-only.
- Fix: Decide the contract — implement directory staging (copytree under assets/{key}/mock/) or restrict design-mock.md/template to single-file. Then guard the edges: skip copy when src==dest, anchor relative paths to the --cards file's parent, warn/flag when no Visual Preview section exists, guard the index() append, and auto-flag ungrounded:design-tokens when the staged header says placeholder styling.
- Findings:
  - `determinism-3` Documented multi-file mock/ contract is unimplemented — directory degrades to unavailable — `references/design-mock.md:26,31 vs scripts/file-cards.py:225-246`
  - `architecture-2` Multi-file mock contract in design-mock.md has no staging path — `references/design-mock.md:26-31 vs scripts/file-cards.py:218-246`
  - `enhancement-3` Add: multi-file mock staging — the standard prescribes an output the filer rejects — `references/design-mock.md:26; scripts/file-cards.py:218-240`
  - `determinism-4` Relative mock paths resolve against process CWD — undeclared anchor — `scripts/file-cards.py:228-230`
  - `determinism-5` Missing Visual Preview section silently desynchronizes the two mock records — `scripts/file-cards.py:201-203,238-240,496`
  - `determinism-7` Unguarded index('\n') crashes mid-drain on a terminal Wireframe line — `scripts/file-cards.py:209-213`
  - `enhancement-4` Add: wire ungrounded:design-tokens into the Flags contract — currently prose-only 'should' — `references/design-mock.md:11; assets/alignment-card-template.md:122-128; scripts/file-cards.py`
  - `enhancement-6` Add (opportunity): two mock-edge guards — same-file copy crash and orphan checklist pointer — `scripts/file-cards.py:243-246,197-215,496`

### 3. Duplicated contract constants across producer and consumer

- Root cause: The assets path literal `alignment/drafts/assets/{key}/` is copy-pasted across file-cards.py, five apply-decisions.py sites, and four docs, and the n/a|unavailable|absent status vocab lives in five surfaces — already drifted ('mock not produced' vs 'mock file missing'). cardlayout.py exists to be the ONE layout definition but was never extended; file-cards' parked-supersede branch implements the same hop differently than apply-decisions.
- Fix: Extend cardlayout.py with the assets taxonomy (MOCK_FILENAME, mock_assets_dir(), superseded_assets(), MOCK_STATUS/WIRE_STATUS enums, shared _section parser) and vendor to both skills; replace literals; make resolve-item's parser enumerate known statuses and emit 'unknown' instead of failing open to 'path'; pick one unavailable string; move parked/assets/{key}/ in file-cards' supersede branch.
- Findings:
  - `customization-1` Mock-assets path copy-pasted across producer and consumer scripts instead of living in cardlayout.py — `file-cards.py:238,243-246,435-438; apply-decisions.py:56-60,124-138,375-377,386-388,430-432,631-633,680-682; cardlayout.py:6-26`
  - `customization-2` Visual Preview status vocab duplicated across five surfaces and already drifted; parser fails open — `template:77-78; SKILL.md:64; design-mock.md:31; file-cards.py:197-240; resolve-item.py:85-110`
  - `architecture-3` file-cards.py parked-supersede branch orphans parked mock assets — `scripts/file-cards.py:442-449`

### 4. The mock ships without a verification floor

- Root cause: The spec claimed taste-skill's verification discipline was borrowed but only its sensibility arrived: the wire has schema validation + a liveness gate, while the mock's entire check is is_file() — empty files, non-HTML blobs, or CDN-linked files stage silently and earn checklist credibility.
- Fix: Two cheap pieces: a pre-filing self-check line in design-mock.md's card contract, and a minimal mechanical check in _mock_plan warning on empty/tiny files, missing HTML structure, or external http(s) asset refs — warning posture, never blocking. resolve-item gates `path` on existence + .html suffix as defense-in-depth.
- Findings:
  - `enhancement-1` Add: verification step for the mock — the renderable artifact nothing verifies — `references/design-mock.md:22-31; scripts/file-cards.py:218-240`
  - `determinism-2` mock_status 'path' trusts the line text — no existence or shape check anywhere — `sets/cdo/cdo-setup/scripts/resolve-item.py:97-107; sets/cdo/cdo-align/scripts/file-cards.py:225-227`

### 5. Prompt-layer polish: restated rules, dead pointers, unrouted dirs

- Root cause: SKILL.md's Visual Preview bullet re-teaches the wire standard it routes to (third copy across files); design-mock.md carries skill-name attributions readers can't act on; wireframe.md numbers non-sequential constraints; the template ships dead ./references/ pointers into every filed card; specs/ is an unrouted one-off dir; SKILL.md is 400+ tokens over budget and lacks a Resolution rules block.
- Fix: Compress the SKILL.md bullet to outcome + payload contract (proposed_smallest provided); drop skill attributions keeping distilled rules; demote wireframe rules 3-5 to bullets; qualify the template's standards pointer; move or delete specs/; stamp a Resolution rules block and normalize new references to bare paths in one sweep of the cdo set.
- Findings:
  - `leanness-1` SKILL.md Visual Preview bullet restates the wire standard it routes to — `SKILL.md:64`
  - `leanness-2` design-mock.md carries provenance attributions to external skills the reader may not hold — `references/design-mock.md:13,19`
  - `leanness-3` wireframe.md 'Build it grounded' numbers a list whose last three items are not a sequence — `references/wireframe.md:13-17`
  - `leanness-4` 'Commentary, not design' motif and wiretext-doesn't-excuse-mock rule each restated 3+ times — `SKILL.md:64; references/wireframe.md:3,15,30; references/design-mock.md:31; references/grounding.md:10; assets/alignment-card-template.md:74`
  - `architecture-4` Multi-file SKILL.md has no Resolution rules block — `SKILL.md`
  - `architecture-6` specs/ is a one-off unrouted directory — `specs/visual-preview-design-artifacts.md`
  - `architecture-7` Template comment bakes skill-relative standards paths into every filed card — `assets/alignment-card-template.md:74`
  - `enhancement-7` Remove: specs/ design history shipped inside the skill — `specs/visual-preview-design-artifacts.md`
  - `prepass-1` 8 cross-dir ./ path references — legacy convention extended by new lines — `SKILL.md:27,38,48,58,64 (x2); assets/alignment-card-template.md:74 (x2)`
  - `prepass-2` SKILL.md 3406 tokens — over 3000 budget — `SKILL.md`

## Strengths

- The two-artifact convention is non-inferable and earns its place — browser-chrome framing, current/proposed layer split, and token-grounding would not emerge from a bare model or the wiretext tool description.
- file-cards.py's deterministic Mock-line ownership at draft time ('the script owns this line so the staged path is always truthful') is the right pattern — the defect is that it stops at the first hop.
- Degrade-don't-fail posture preserved end-to-end: missing wiretext/mock never blocks filing, matching the existing unavailable convention.
- ungrounded:design-tokens correctly reuses the established ungrounded:{store} flag convention.
- move_assets already relocates the whole assets/{key}/ dir — the lifecycle plumbing is multi-file-ready even though staging isn't.
- All 58 modified-suite tests pass; file-cards.py and preflight.py are clean under script-standards lint.

## Recommendations

1. Make the Mock line truthful across moves: rewrite it in apply-decisions at each hop (or resolve card-relative in resolve-item — pick one), existence-check the path in resolve-item, and line-scope the wireframe status parse. (resolves: determinism-1, architecture-1, enhancement-2, architecture-5, determinism-6, determinism-2)
2. Extend cardlayout.py with the assets taxonomy + status enums + shared section parser; vendor to both skills and replace all literals. (resolves: customization-1, customization-2, architecture-3)
3. Close staging edges in file-cards.py: decide dir-vs-single-file contract, guard SameFileError, anchor relative paths to the cards file's parent, warn on missing Visual Preview, guard the terminal-line index(). (resolves: determinism-3, architecture-2, enhancement-3, determinism-4, determinism-5, determinism-7, enhancement-6)
4. Add the mock verification floor: mechanical content check in _mock_plan + self-check line in design-mock.md + ungrounded:design-tokens auto-flag. (resolves: enhancement-1, enhancement-4)
5. Leanness sweep: compress SKILL.md bullet to proposed_smallest, drop skill attributions, fix wireframe.md numbering, relocate specs/, qualify template pointers. (resolves: leanness-1, leanness-2, leanness-3, leanness-4, architecture-7, architecture-6, enhancement-7, prepass-2)
6. One cdo-set sweep: stamp Resolution rules blocks and normalize ./ paths to bare convention (org-wide gap, not just this change). (resolves: architecture-4, prepass-1)

## Experience

- **Draft → file** — grounded read → wiretext wire + HTML mock → cards.json with mock → file-cards stages and stamps Mock line → checklist carries | mock: — smooth and deterministic
- **Confirm → consume** — apply-decisions archives card + moves assets — but Mock line stays drafts-rooted → resolve-item reports stale path → pipeline embeds dead link in Dev Notes
- **Defer → resurface** — parked card's assets move to parked/assets/; on resurface they return — Mock line still cites drafts/ the whole time
- Headless: file-cards.py and apply-decisions.py are fully scriptable; the mock staging path works headless, but the dead-link defect is invisible headless too — nothing validates the cited path at consume time.

## Findings

### Critical (1)

#### determinism-1 — Mock line is never rewritten when assets move — every confirmed/parked/superseded card cites a dead path

- Lens: determinism
- Location: `sets/cdo/cdo-review/scripts/apply-decisions.py:124-138,617-684; sets/cdo/cdo-align/scripts/file-cards.py:238-239`
- Evidence: file-cards.py stamps a drafts-rooted Mock path; apply-decisions moves the asset dir on every hop while writing the body verbatim. resolve-item emits mock_status 'path' off the confirmed card and pipeline.md instructs embedding it in Dev Notes — a deterministically dead link. Lifecycle tests assert the move, never the citing line. move_assets also returns silently on dest.exists().
- Recommendation: Rewrite the Mock line to the destination's orch-relative path at each hop (assets_moved is already returned); warn instead of silently returning on dest.exists(); add existence validation in resolve-item as defense-in-depth.

### High (5)

#### prepass-1 — 8 cross-dir ./ path references — legacy convention extended by new lines

- Lens: pre-pass
- Location: `SKILL.md:27,38,48,58,64 (x2); assets/alignment-card-template.md:74 (x2)`
- Evidence: Path-standards scan found 8 `cross-dir-dot-slash` findings. Most are pre-existing convention (`./scripts/preflight.py`, `./references/grounding.md`), but the new Visual Preview bullet and template comment added more instances under the same style instead of bare skill-root paths.
- Recommendation: Sweep the cdo set once to bare `references/foo.md` convention rather than per-file; new lines should not extend the `./` style.

#### architecture-1 — Mock pointer goes stale on every lifecycle move — dead path reaches pipeline Dev Notes

- Lens: architecture
- Location: `sets/cdo/cdo-review/scripts/apply-decisions.py:124-138,370-390,430-435,631-635,680-684; sets/cdo/cdo-setup/scripts/resolve-item.py:96-107; sets/cdo/cdo-code-e2e/references/pipeline.md:25`
- Evidence: apply-decisions moves assets/{key}/ on defer/confirm/reject/resurface/unpark but the card body is written verbatim — the Mock line still cites alignment/drafts/. resolve-item parses the stale line as status 'path' and pipeline.md embeds it in Dev Notes — a dead link on every confirmed UI-touching card.
- Recommendation: Single fix point: rewrite the Mock line at each move, or resolve the path card-relative in resolve-item. Do one, not both.

#### determinism-2 — mock_status 'path' trusts the line text — no existence or shape check anywhere

- Lens: determinism
- Location: `sets/cdo/cdo-setup/scripts/resolve-item.py:97-107; sets/cdo/cdo-align/scripts/file-cards.py:225-227`
- Evidence: resolve-item classifies anything not n/a/unavailable as 'path' — no .html check, no is_file(), no traversal rejection; even an unfilled placeholder parses as path. Mirror image: _mock_plan returns (None,None) when the filing JSON lacks mock but the card body claims one — the claim is never staged or checked. The wireframe field is held to a higher bar than a local file whose existence is trivially checkable.
- Recommendation: file-cards: when mock is absent but the body claims a path, existence-check and degrade to 'unavailable — mock declared but not staged'. resolve-item: gate 'path' on (orch/mval).is_file() and .html suffix.

#### enhancement-1 — Add: verification step for the mock — the renderable artifact nothing verifies

- Lens: enhancement
- Location: `references/design-mock.md:22-31; scripts/file-cards.py:218-240`
- Evidence: The spec claims taste-skill's verification discipline was borrowed but only its sensibility arrived. The wire has schema validation + liveness gate; the mock's entire check is is_file() — an empty file, non-HTML blob, or HTML full of CDN links stages silently and earns checklist credibility.
- Recommendation: Add a pre-filing self-check line to design-mock.md's card contract plus a minimal mechanical check in _mock_plan (warn on empty/tiny, missing HTML structure, external asset refs) — warning posture, never blocking.

#### enhancement-2 — Add: Mock-line rewrite on lifecycle moves — confirmed cards carry a dead mock link

- Lens: enhancement
- Location: `cdo-review/scripts/apply-decisions.py:669-684; resolve-item.py:97-107; pipeline.md:25`
- Evidence: file-cards established 'the script owns this line so the staged path is always truthful' — apply-decisions breaks that ownership on the next hop: the archived card is written verbatim while move_assets relocates the file. Every confirmed card's Mock path is a dead link that resolve-item surfaces into Dev Notes. The lifecycle test suite asserts the file moved but never the citing line.
- Recommendation: Rewrite the Mock line to the new location before writing the moved card at every hop; add tests asserting the card's Mock line post-move.

### Medium (13)

#### prepass-2 — SKILL.md 3406 tokens — over 3000 budget

- Lens: pre-pass
- Location: `SKILL.md`
- Evidence: Mostly pre-existing bulk; the new Visual Preview bullet added ~100 tokens of rule restatement the references own. Compressing it per leanness-1 claws some back.
- Recommendation: Apply leanness-1's proposed_smallest; a deeper trim of the whole file is out of this change's scope but worth a separate pass.

#### prepass-3 — cardlayout.py: 3 agentic-design findings + missing tests (pre-existing)

- Lens: pre-pass
- Location: `scripts/cardlayout.py`
- Evidence: Unrelated to this change but relevant to customization-1: the module that should own the assets taxonomy is itself flagged (agentic-design x3, no tests).
- Recommendation: When extending cardlayout.py for the assets contract, address the lint findings and add tests.

#### leanness-1 — SKILL.md Visual Preview bullet restates the wire standard it routes to

- Lens: leanness
- Location: `SKILL.md:64`
- Evidence: The bullet carries the wire's four signature conventions inline — browser chrome, multi-frame single wire, layerId split, to-be drawn in place — then routes to wireframe.md which states them verbatim. A third restatement sits in the template comment. Three copies of one rule set is three drift surfaces in a file already over budget.
- Recommendation: Compress the wire half of the bullet to outcome + routing + the payload contract.
- Proposed smallest: **Visual preview (UI-touching items)** — produce both design artifacts from the same grounded read: the wire per `./references/wireframe.md` (embed the URL in the card and pass it as `wireframe` in the filing JSON — a confirmed card's URL satisfies the pipeline's wireframe gate) and one self-contained HTML mock on the project's real design tokens per `./references/design-mock.md` (pass the produced file as `mock`; the script stages it at `alignment/drafts/assets/{key}/mock.html`). `n/a — no UI surface` on both for non-UI items; `unavailable — {reason}` when a tool genuinely fails — optional artifacts never block filing, and a missing wiretext does not excuse a missing mock.
- Predicted delta: The wire's framing conventions leave the entry file, so a run that skips loading wireframe.md produces an unframed sketch — but the routing line makes skipping non-compliant behavior the reference-load convention already guards. Expect no loss on compliant runs; route to variant eval to confirm.

#### architecture-2 — Multi-file mock contract in design-mock.md has no staging path

- Lens: architecture
- Location: `references/design-mock.md:26-31 vs scripts/file-cards.py:218-246`
- Evidence: design-mock.md offers 'one file per surface under the same mock dir' but _mock_plan requires is_file() and _copy_mock renames to mock.html — a drafter following the multi-file option gets one file staged under the wrong name, siblings dropped, Mock line rewritten.
- Recommendation: Tighten design-mock.md to the single-file contract, or extend the payload to accept a directory and stage all files under assets/{key}/.

#### architecture-3 — file-cards.py parked-supersede branch orphans parked mock assets

- Lens: architecture
- Location: `scripts/file-cards.py:442-449`
- Evidence: The manual-marker-flip route moves parked/{key}.md → superseded/ but never moves parked/assets/{key}/; apply-decisions performs the identical hop and does move assets. The stale parked dir can also block a future defer's move via move_assets' silent dest.exists() early-return.
- Recommendation: Move parked/assets/{key}/ → superseded/{key}.{stamp}.parked.assets/ in the parked-supersede branch; add a test.

#### architecture-4 — Multi-file SKILL.md has no Resolution rules block

- Lens: architecture
- Location: `SKILL.md`
- Evidence: SKILL.md references ~7 internal files across three dirs with ./-prefixed paths but no Resolution rules block — an org-wide gap the new line extended.
- Recommendation: Stamp the canonical Resolution rules block; normalize new references to bare paths; sweep the cdo set once.

#### architecture-5 — cdo-review confirm-edited 'strip' leaves stale mock handling ambiguous

- Lens: architecture
- Location: `sets/cdo/cdo-review/SKILL.md:48`
- Evidence: The offer says 'same call covers both' but defines strip as removing the wire URL while the mock 'degrades to unavailable on the next re-draft' — read literally the stale mock stays on the signed card and flows to Dev Notes.
- Recommendation: State explicitly that strip applies to both artifacts (set Mock to unavailable — design superseded by edit, or delete the line).

#### determinism-3 — Documented multi-file mock/ contract is unimplemented — directory degrades to unavailable

- Lens: determinism
- Location: `references/design-mock.md:26,31 vs scripts/file-cards.py:225-246`
- Evidence: The standard documents mock/{surface}.html multi-file output but _copy_mock stages exactly one file renamed mock.html; a directory path hits is_file() → unavailable; a single file of a set stages alone while _set_mock_line rewrites the drafter's per-surface line. Lifecycle side is already multi-file-ready; staging isn't.
- Recommendation: Implement directory staging (copytree + preserve the drafter's Mock line) or amend the standard to single-file-only so the written contract matches the enforced one.

#### determinism-4 — Relative mock paths resolve against process CWD — undeclared anchor

- Lens: determinism
- Location: `scripts/file-cards.py:228-230`
- Evidence: A relative mock path anchors to wherever uv run launched, not the cards file or orchestration dir — same payload resolves differently by launch context, or stages a same-named wrong file. Every other path the script touches anchors to --orchestration-dir.
- Recommendation: Anchor relative paths to the --cards file's parent directory, or reject relative paths in _validate with a named error.

#### customization-1 — Mock-assets path copy-pasted across producer and consumer scripts instead of living in cardlayout.py

- Lens: customization
- Location: `file-cards.py:238,243-246,435-438; apply-decisions.py:56-60,124-138,375-377,386-388,430-432,631-633,680-682; cardlayout.py:6-26`
- Evidence: The staging contract literal appears in file-cards.py and at five sites in apply-decisions.py plus variants, while cardlayout.py — vendored into six skills precisely to be 'the ONE definition of where a card may live' — was never extended, and file-cards.py doesn't import it. Docs repeat the literal four more times. A future path change must be hand-synced or mocks orphan.
- Recommendation: Extend cardlayout.py with the assets taxonomy (mock_assets_dir, MOCK_FILENAME, superseded_assets), vendor to all copies, replace the literals. Keep it a code constant — the writable root is already configurable via {orchestration_dir}.

#### customization-2 — Visual Preview status vocab duplicated across five surfaces and already drifted; parser fails open

- Lens: customization
- Location: `template:77-78; SKILL.md:64; design-mock.md:31; file-cards.py:197-240; resolve-item.py:85-110`
- Evidence: The path|n/a|unavailable|absent vocabulary is restated in template, SKILL.md, design-mock.md, emitted by file-cards, parsed by resolve-item — no single definition. Drift exists: docs say 'unavailable — mock not produced', script emits 'unavailable — mock file missing'. resolve-item's else→'path' fallback means any future status string silently parses as a file path. Same duplication class predates the change (RISK_TOKENS, _section re-implemented twice).
- Recommendation: Hoist the vocabulary into the shared layer: status enums, sentinel strings, shared parse helper; make unrecognized values report 'unknown' not 'path'; align the emitted string with the documented one.

#### enhancement-3 — Add: multi-file mock staging — the standard prescribes an output the filer rejects

- Lens: enhancement
- Location: `references/design-mock.md:26; scripts/file-cards.py:218-240`
- Evidence: design-mock.md sanctions one-file-per-surface but _mock_plan requires is_file() — a conformant multi-surface mock dir gets 'unavailable'. The 6 added tests cover the single-file contract only.
- Recommendation: Extend _mock_plan to accept a directory, or remove the multi-file option from the standard. Test whichever contract wins.

#### enhancement-4 — Add: wire ungrounded:design-tokens into the Flags contract — currently prose-only 'should'

- Lens: enhancement
- Location: `references/design-mock.md:11; assets/alignment-card-template.md:122-128; scripts/file-cards.py`
- Evidence: The placeholder-styling failure mode is defined and flags 'should carry' the token, but nothing checks the correlation — a placeholder mock can file with zero flags and land in Routine Review, the exact signal loss the flag exists to prevent. Same class as the unsigned-cosign auto-flag.
- Recommendation: Name the token in the template's Flags enumeration and add a cross-check in _copy_mock: staged file's header says placeholder styling but flags lack the token → append it or warn.

### Low (12)

#### leanness-2 — design-mock.md carries provenance attributions to external skills the reader may not hold

- Lens: leanness
- Location: `references/design-mock.md:13,19`
- Evidence: 'Borrow taste-skill's sensibility' and 'follow the emil-design-eng rubric selectively' name skills a reader may not have installed; the distilled rules that follow already carry every actionable instruction. The specs/ file records the sourcing for maintainers.
- Recommendation: Drop the skill-name attributions and keep the distilled rules and guardrails.

#### leanness-3 — wireframe.md 'Build it grounded' numbers a list whose last three items are not a sequence

- Lens: leanness
- Location: `references/wireframe.md:13-17`
- Evidence: Steps 1-2 are a true sequence; steps 3-5 (annotate placement-only, type components, copy-true) are concurrent constraints on the same drawing act, not ordered steps.
- Recommendation: Keep 1-2 as the ordered opening, demote 3-5 to unnumbered rules.

#### leanness-4 — 'Commentary, not design' motif and wiretext-doesn't-excuse-mock rule each restated 3+ times

- Lens: leanness
- Location: `SKILL.md:64; references/wireframe.md:3,15,30; references/design-mock.md:31; references/grounding.md:10; assets/alignment-card-template.md:74`
- Evidence: The 'sketch is commentary' framing appears in wireframe.md twice and again in grounding.md and the template; 'missing wiretext does not excuse missing mock' is stated three times. Per-file repetition is defensible motif reinforcement but wireframe.md states its own thesis twice.
- Recommendation: Keep line-15's concrete formulation in wireframe.md, compress line 3's; if leanness-1 lands, shrink the template comment's wire sentence.

#### architecture-6 — specs/ is a one-off unrouted directory

- Lens: architecture
- Location: `specs/visual-preview-design-artifacts.md`
- Evidence: Only specs/ dir across the ~20-skill cdo set; nothing routes to it; it's an implementation record, not runtime content.
- Recommendation: Adopt specs/ as an org convention or relocate the record out of the skill.

#### architecture-7 — Template comment bakes skill-relative standards paths into every filed card

- Lens: architecture
- Location: `assets/alignment-card-template.md:74`
- Evidence: 'Standards: ./references/wireframe.md and ./references/design-mock.md' persists verbatim into every filed card where the path resolves to nothing — a dead pointer shipped inside the artifact; the change doubled the dead surface.
- Recommendation: Qualify the pointer ('standards live in the cdo-align skill — references/…') or drop it.

#### determinism-5 — Missing Visual Preview section silently desynchronizes the two mock records

- Lens: determinism
- Location: `scripts/file-cards.py:201-203,238-240,496`
- Evidence: When mock is supplied but the body lacks ## Visual Preview, _set_mock_line returns unchanged yet the file still stages and the checklist carries | mock: — the filesystem and checklist say a mock exists while the card records nothing; resolve-item reports 'absent' against a real file, no warning.
- Recommendation: Warn (or mark contract_broken) when mock is supplied but no Visual Preview section exists.

#### determinism-6 — Mock sentinel text cross-contaminates wireframe status; writer/reader use different line shapes

- Lens: determinism
- Location: `sets/cdo/cdo-setup/scripts/resolve-item.py:85-107 vs sets/cdo/cdo-align/scripts/file-cards.py:68,207`
- Evidence: wireframe_status searches the whole Visual Preview section, so a Mock line's 'n/a — no UI surface' or 'unavailable' satisfies the wireframe check on a malformed card. Separately, file-cards anchors Mock-line writes to column 0 while resolve-item matches unanchored — an indented stale line survives replace but wins first-match parse.
- Recommendation: Line-scope the wireframe status parse to the Wireframe line; align regex anchoring between writer and reader.

#### determinism-7 — Unguarded index('\n') crashes mid-drain on a terminal Wireframe line

- Lens: determinism
- Location: `scripts/file-cards.py:209-213`
- Evidence: If the Wireframe line is the body's last line with no trailing newline, index raises ValueError → exit 2 mid-batch after earlier cards already filed and flipped backlog markers — half-applied state against the 'no half-filed runs' contract.
- Recommendation: Guard the index (m.end() < len(new_sec), else append at section end).

#### customization-3 — No customize.toml — correctly absent; confirm the opt-out stays deliberate

- Lens: customization
- Location: `cdo-align/ (no customize.toml)`
- Evidence: No config surface warranted: writable roots flow via {orchestration_dir}, the template is a parser contract not a swappable format, annotation budgets and 160ms are illustrative standard text. No env vars or ad-hoc config introduced.
- Recommendation: No action — record the no-customize decision in the memlog and keep it that way.

#### enhancement-5 — Add (opportunity): make the annotation budget enumerable

- Lens: enhancement
- Location: `references/wireframe.md:15`
- Evidence: The spec promised an 'annotation budget' but the delivered rule is qualitative only — 'annotate what and where, never why' plus the paragraph test. A budget in name only.
- Recommendation: Add one numeric bound — e.g., 'one annotation per proposed object, ≤ ~15 words' — keeping the paragraph test as backstop.

#### enhancement-6 — Add (opportunity): two mock-edge guards — same-file copy crash and orphan checklist pointer

- Lens: enhancement
- Location: `scripts/file-cards.py:243-246,197-215,496`
- Evidence: If the model stages the mock directly at the dest path and passes it, shutil.copy2 raises SameFileError → exit 2 mid-batch. If the card body lacks Visual Preview, the file stages and the checklist points at a Mock line that doesn't exist. Neither has a test.
- Recommendation: Skip the copy when src resolves to dest; warn when no Visual Preview section exists. One test each.

#### enhancement-7 — Remove: specs/ design history shipped inside the skill

- Lens: enhancement
- Location: `specs/visual-preview-design-artifacts.md`
- Evidence: The skill's path conventions recognize references|assets|scripts; specs/ is a fourth directory holding the change's design doc — historical rationale no runtime step loads. Removing costs nothing at run time; the 'why' lives in git history.
- Recommendation: Move to repo docs/module history or delete — a directory's worth of surface for zero runtime value.
