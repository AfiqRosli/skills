# Platform consult — release engineering notes

## 2026-11-16 — Repo version bump after set changes
**Q:** How should the skills repo version (currently 0.1.0) be updated after the cdo/srm/scaffold set changes?
**Advice:** Bump to `0.2.0` in `package.json` — the change set adds a capability (cdo-version-upgrade + platform delegation), not just fixes, so minor over patch. `package.json` is the repo's only version source; `0.1.0` hits inside skills are module docs/defaults. Consumers install via `github:AfiqRosli/skills` — commit/tag is the real version they resolve; consider tagging `v0.2.0` for a stable ref.
**Outcome:** answered
