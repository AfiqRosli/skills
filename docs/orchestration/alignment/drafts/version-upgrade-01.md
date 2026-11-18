---
key: "version-upgrade-01"
backlog: "backlogs/version-upgrade.md"
deps: []
touches: ["sets/cdo/cdo-align/", "sets/cdo/cdo-orchestrator/", "sets/cdo/cdo-setup/", ".agents/skills/cdo-align/", ".agents/skills/cdo-orchestrator/", ".agents/skills/cdo-setup/", "package.json", "README.md", "_bmad/config.yaml", "docs/orchestration/", "git refs (main, tag v0.4.0)"]
emits: ["release v0.4.0"]
externals: ["github.com/AfiqRosli/skills (origin push + tag)"]
declared_surface: ["deps-changed"]
grounded_against:
  commit: "64cda35"
  drafted: "2026-11-18"
---

# Alignment Card — version-upgrade-01: Upgrade project version (cut v0.4.0 carrying the cdo-align hardening)

- **Source:** `backlogs/version-upgrade.md` · drafted 2026-11-18 14:15
- **Confidence:** 87%
- **Sizing:** lite
- **P&D co-sign:** sign — revised on ES declaration: `deps-changed` declared to pre-clear the manifest gate (version-field edits are indistinguishable to it); version choice + flags hold

## Marshal's Read

- **Business intent:** consumers install sets via `bunx -p github:AfiqRosli/skills#v{tag}` (`README.md:52`). The session's cdo-align hardening on disk is invisible until a tag moves. "Upgrade project version" = cut the next release carrying it — same read as platform-01.
- **User value:** anyone installing `cdo` gets the hardened cdo-align — env-matched mock/wire framing, enforced filing contract (required sections, co-sign stamp, `grounded_against.commit`), `--backlog-map`, `customize.toml` surface — plus the `product_docs` config key across `cdo-setup`/`cdo-orchestrator`.
- **Challenges to the source spec:** none — the FRAGO is thin but the release shape is unambiguous from the platform-01 precedent (confirmed-as-drafted card, `alignment/2026/11/17/platform-01.md`; bump commit `ccef75d` = README + package.json only).
- **Alternatives weighed:** 0.3.1 patch vs 0.4.0 minor — minor wins; the payload adds capability (customize surface, config key, CLI flag, contract enforcement), matching the "minor over patch" consult platform-01 cited.
- **Strongest objection:** the release carries a contract break — `file-cards.py` now errors on cards missing template-required sections. Sibling filing paths producing thin cards batch-error post-release. That's intended hardening, but downstream producers (cdo-batch, apply-decisions) must emit full-section cards or they'll stall at validation — flag it, don't hide it.

### Strategic axes

- `intent-fit`: advances — installable release is how the org's skill work reaches consumers (README pin).
- `user-value-chain`: installer → hardened filing/contract → fewer malformed cards downstream.
- `spec-honesty`: honest but thin — source is a one-line FRAGO, no story file exists (`{story_location}` has no version-upgrade-01 entry). Flagged `ungrounded:source`.
- `reversibility`: tag + commit are cheap to undo pre-push; post-push needs a retag — Deploy Sign-off is the gate, per precedent.
- `precedent`: first item in the `version-upgrade` backlog; confirming repeats the platform-01 release-train shape (bump → tag → gated push).
- `timing`: correct cadence — a large hardening pass just landed uncommitted on disk; cutting now keeps the tag surface from drifting behind the installed tree.

## System Context

- **Current state:** HEAD `64cda35` = main; tag `v0.3.0` @ `ccef75d` pushed. `package.json` `version` = `0.3.0`; `README.md:52` pins `#v0.3.0`. Uncommitted payload: `sets/cdo/cdo-align/**` (SKILL.md 2,992→2,639 tok, env-frame refs, `references/co-sign.md` new, `customize.toml` new, script hardening, test rebuild), `sets/cdo/cdo-orchestrator/scripts/resolve-config.py` + `sets/cdo/cdo-setup/assets/module.yaml` (`product_docs` key), `.agents/skills/**` synced mirrors, `_bmad/config.yaml` (`product_docs`), `docs/orchestration/` state (backlog intake + FRAGO journal), `.memlog.md` → `.analysis/` move, stray `nul` junk at root.
- **Flow:** commit set payload → commit `.agents/` sync → commit config/orchestration `chore` → bump `package.json` + README pin → tag `v0.4.0` → push main + tag post Deploy Sign-off.
- **Integration points:** `package.json:3` `version`; `README.md:52` pin; `_bmad/config.yaml` `cdo:` section; `module.yaml` `module_version` (see Questions).
- **Owns vs platform:** we own commits/tag/lane; GitHub hosts the ref consumers resolve.

## Visual Preview

- **Wireframe:** `n/a — no UI surface` (git/version artifacts only)
- **Mock:** `n/a — no UI surface`

## Questions for the Operator

- Version `0.4.0` vs `0.3.1`? — recommended: **0.4.0** (customize surface + `product_docs` key + `--backlog-map` + enforced filing contract = capability change; platform-01 precedent: minor over patch).
- Bump cdo module version alongside? (`module.yaml` `module_version` 0.1.0, `_bmad/config.yaml` `cdo.version` 0.1.0) — recommended: **yes, 0.1.1** — `product_docs` is a config-schema addition; keep the two fields in lockstep.

## Acceptance Criteria

- [ ] `sets/cdo/cdo-{align,orchestrator,setup}` changes committed; `.analysis/` excluded, `nul` deleted not committed
- [ ] `.agents/skills/cdo-{align,orchestrator,setup}` synced copies committed
- [ ] `_bmad/config.yaml` (`product_docs` + optional `cdo.version` bump) + `docs/orchestration/` state committed as separate `chore` commit
- [ ] `package.json` `version` = `0.4.0`; `README.md` pin = `#v0.4.0`
- [ ] `v0.4.0` tag created; `main` + tag pushed to origin (post Deploy Sign-off)

## Scope Boundary

- **In:** commit splitting, version bump, tag, gated push for this release
- **Out:** further skill-content edits, dispatching other backlogged work, module-version decisions beyond the flagged question

## Externals Needed

- github.com/AfiqRosli/skills — origin push + tag (Operator-gated at Deploy Sign-off)

## Execution Surface

- **Risk surface:** `deps-changed`

## Flags

- ungrounded:source — no story file for version-upgrade-01; the read is grounded on the backlog line + FRAGO directive + platform-01 precedent, not a spec — resolves if the Operator confirms intent as read.
- contract-break — required-section enforcement in `file-cards.py` makes thin-card filing a batch error post-release — resolves when downstream producers emit full-section cards (or the hardening is walked back).
- dirty-tree — payload spans set source, installed sync, config, and org state; produce must split commits — resolves if commits land per the platform-01 split convention.
- calibration-thin — doctrine log + standing policies are template comments; corpus = 1 shipped story (platform-01, no verdict) — resolves as the ledger accrues.
- es-declaration — `deps-changed` declared on package.json manifest work (the gate can't diff version-field vs dependency edits); no dependency actually changes — vocabulary gap surfaced as a gap finding.

## Doctrine Grounding

- platform-01 card (`alignment/2026/11/17/platform-01.md`, confirmed-as-drafted): release-train convention — commit payload → sync installed → bump → tag → gated push; bump commit `ccef75d` shape.
- `consult/platform.md` (cited in platform-01): minor over patch for capability-bearing releases.
