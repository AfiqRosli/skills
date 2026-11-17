<!-- confirm 2026-11-17 10:55 UTC — confirmed as drafted -->

---
key: "platform-01"
backlog: "backlogs/platform.md"
deps: []
touches: ["sets/cdo/cdo-align/", ".agents/skills/cdo-align/", "package.json", "README.md", "docs/orchestration/", "git refs (preview, main, tag v0.3.0)"]
emits: ["release v0.3.0"]
externals: ["github.com/AfiqRosli/skills (origin push + tag)"]
declared_surface: ["git-commits", "version-bump", "tag-push"]
grounded_against:
  commit: "f91f326"
  drafted: "2026-11-17"
---

# Alignment Card — platform-01: Release train — ship cdo-align set update as v0.3.0

- **Source:** `backlogs/platform.md` · drafted 2026-11-17 18:49
- **Confidence:** 85%
- **Sizing:** lite
- **P&D co-sign:** n/a — release engineering, no product surface

## Marshal's Read

- **Business intent:** consumers install sets via `bunx -p github:AfiqRosli/skills#v{tag}` (`README.md:52`). The cdo-align updates on disk are invisible to consumers until a tag moves. "Update the release train" = cut the next release carrying the set update.
- **User value:** anyone installing `cdo` gets the refreshed cdo-align (SKILL.md, references, file-cards.py +81 LOC, expanded tests, new `evals/cases.json`).
- **Challenges to the source spec:** none — the FRAGO is thin but the release shape is unambiguous from the v0.2.0 precedent (commit `8a379da`).
- **Alternatives weighed:** 0.2.1 patch vs 0.3.0 minor — minor wins; the change adds evals + script capability, matching the consult note's own advice ("minor over patch" — `consult/platform.md`).
- **Strongest objection:** the dirty tree mixes three concerns — set update, cdo-setup install, and stray tooling junk. A sloppy produce leg could commit generated noise or fold install state into the release payload.

## System Context

- **Current state:** HEAD `f91f326` = origin/main = v0.2.0 tag point; checkout sits on new `preview` lane. Uncommitted: `sets/cdo/cdo-align/**` edits + `evals/cases.json` (new) + `.analysis/2026-11-17-1633/` (generated reports), cdo-setup install (`docs/orchestration/`, `_bmad/config.yaml`, `module-help.csv`), junk (`nul`, `prepass-*.err`).
- **Flow:** commit set update → sync `.agents/skills/cdo-align` to set source → bump `package.json` → README pin → tag `v0.3.0` → push main + tag. Push is Operator-gated (Deploy Sign-off).
- **Integration points:** `package.json` `version` field; `README.md:52` pinned install example; `.agents/skills/` is the committed installed tree (precedent: `1870493`, `8a379da`).
- **Owns vs platform:** we own commits/tag; GitHub hosts the ref consumers resolve.

## Visual Preview

- **Wireframe:** `n/a — no UI surface` (git/version artifacts only)
- **Mock:** `n/a — no UI surface`

## Questions for the Operator

- Version `0.3.0` vs `0.2.1`? — recommended: **0.3.0** (new evals + capability changes = minor, per the prior consult).
- Commit `sets/cdo/cdo-align/evals/cases.json`? — recommended: **yes** (part of the set payload).
- Commit `.analysis/2026-11-17-1633/` report artifacts? — recommended: **no** (generated analysis output; not set source).
- `nul` + `prepass-*.err` root junk? — recommended: **delete, don't commit**.
- cdo-setup install artifacts (`docs/orchestration/`, config)? — recommended: **commit as a separate `chore` commit, same push** — repo-local state, not release payload.

## Acceptance Criteria

- [ ] `sets/cdo/cdo-align` changes + `evals/` committed; `.analysis/` and root junk excluded
- [ ] `.agents/skills/cdo-align` synced to the set source and committed
- [ ] `package.json` `version` = `0.3.0`; `README.md` pin = `#v0.3.0`
- [ ] cdo-setup install committed separately (`chore` commit)
- [ ] `v0.3.0` tag created; `main` + tag pushed to origin (post Deploy Sign-off)

## Flags

- Working tree is dirty across three concerns — produce must split commits cleanly.
- Grounded against a dirty tree (`f91f326` + unstaged); drift-watch should re-anchor post-commit.
