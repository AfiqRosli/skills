---
name: cdo-version-change-for-production
description: 'Determine and apply project software versioning based on changes between the local preview branch and remote origin/main. Use when preparing a production deploy, merging to main, or when the user asks what version a release should be.'
---

# Code Version — Changes to Production Workflow

## Overview

This workflow analyzes the differences between the current local preview branch and remote `origin/main` to determine the appropriate version bump for the project across all versioning layers — product (Release Train), API (SemVer), and package (SemVer). It leverages the three versioning agents: **Vera** (orchestrator), **Sage** (SemVer), and **Relay** (Release Train).

**Execute this workflow via `bmad-versioning-agent-orchestrator` (Vera) for coordinated version analysis and bumping.**

## Prerequisites

1. **Preview branch has changes ahead of `origin/main`** — `git diff origin/main...HEAD` shows modifications
2. **`origin/main` is up to date** — run `git fetch origin` before analysis
3. **Current version known** — `package.json` version field or last git tag

## On Activation

1. Load config via `bmad-init`; communicate in `{communication_language}`.
2. Verify the Prerequisites above, then run Step 0 — the Deployment Intent Gate decides full vs analysis-only mode before anything else executes.
3. Ordering contract: version files are committed BEFORE any tag is created — a tag must always point at the commit containing the bump. Step 5 prepares the tag; Step 7 creates it post-commit.

## Step 0: Deployment Intent Gate

Before analyzing or applying any version bumps, determine whether these changes are being merged to `main` and deployed to production. Release Train versions are only assigned when code ships to production — not for feature branches or work-in-progress.

### Ask the user:

> **Are these changes being merged to `main` and deployed to production now?**
>
> - **Yes — merging to main** → Proceed with full workflow (Steps 1–7): analyze changes, determine version bumps, apply updates, create tags, update changelog
> - **No — not merging yet** → Proceed with analysis-only mode (Steps 1–3): analyze changes and report what the version bump *would* be, but do NOT apply any version updates, create tags, or modify changelog

### Analysis-Only Mode

When the user is **not** merging to main:

1. Run Steps 1–3 (detect changes, categorize, determine version bumps)
2. Present the version bump summary as a **recommendation** — what the bump *will* be when they eventually merge
3. Skip Steps 4–7 (no `package.json` edits, no `release-train.json` updates, no tags, no changelog modifications)
4. Remind the user to re-run this workflow when they are ready to merge to `main`

This ensures version numbers are only assigned at the moment of production release, keeping Release Train versions honest and tied to actual deployments.

## Step 1: Detect Changes Between Preview Branch and origin/main

```bash
# Ensure remote refs are current
git fetch origin

# Get all files changed between preview branch and origin/main
git diff origin/main...HEAD --name-only

# Get detailed diff for analysis
git diff origin/main...HEAD --stat

# Get full diff for semantic analysis
git diff origin/main...HEAD
```

// turbo
```bash
# Quick commit summary of what's ahead of origin/main
git log origin/main..HEAD --oneline

# Quick status check
git status --porcelain
```

## Step 2: Categorize Changes by Impact Layer

Analyze each changed file and map it to a versioning layer:

### Layer Mapping

| File Location | Versioning Layer | Agent | Version Scheme |
| ------------- | ---------------- | ----- | -------------- |
| `server/api.ts`, `server/*.ts` | API Layer | Sage | SemVer (`/v1/` prefix) |
| `server/db/schema.ts` | API Layer | Sage | SemVer (breaking if schema changes) |
| `interfaces/*.ts` | API + Package | Sage | SemVer (breaking if contract changes) |
| `components/**/*.vue` | Product Layer | Relay | Release Train |
| `pages/**/*.vue` | Product Layer | Relay | Release Train |
| `stores/*.ts` | Product Layer | Relay | Release Train |
| `composables/*.ts` | Product Layer | Relay | Release Train |
| `nuxt.config.ts` | Product Layer | Relay | Release Train |
| `package.json` | Package Layer | Sage | SemVer |
| `assets/styles/*` | Product Layer | Relay | Release Train |
| `utils/*.ts` | Product Layer | Relay | Release Train |
| `middleware/*.ts` | Product Layer | Relay | Release Train |
| `plugins/*.ts` | Product Layer | Relay | Release Train |
| `lib/*.ts` | Product Layer | Relay | Release Train |
| `tests/**/*` | None | None | No version bump (test-only) |
| `docs/**/*` | None | None | No version bump (docs-only) |
| `.devin/**/*` | None | None | No version bump (tooling) |
| `_bmad/**/*` | None | None | No version bump (tooling) |

### Change Classification

For each changed file, determine the change type using Conventional Commits mapping:

| Pattern Found in Diff | Change Type | SemVer Impact | Release Train Signal |
| -------------------- | ----------- | ------------- | -------------------- |
| New function/endpoint exported | `feat` | MINOR bump | (none) — routine |
| New component/page added | `feat` | N/A (product) | (none) — routine |
| Bug fix (correcting behavior) | `fix` | PATCH bump | (none) — routine |
| Removed/renamed exported function | `BREAKING` | MAJOR bump | `-breaking` |
| Changed function signature | `BREAKING` | MAJOR bump | `-breaking` |
| Changed response shape | `BREAKING` | MAJOR bump | `-breaking` |
| Database schema change (column removed/renamed) | `BREAKING` | MAJOR bump | `-breaking` |
| Auth/permission model changed | `BREAKING` | MAJOR bump | `-breaking` |
| Security vulnerability patched | `security` | PATCH bump | `-security` |
| Feature behind flag (opt-in) | `preview` | N/A (product) | `-preview` |
| Refactor (no API change) | `refactor` | No bump | (none) — routine |
| Style/CSS only | `style` | No bump | (none) — routine |
| Docs/comments only | `docs` | No bump | No release |
| Test files only | `test` | No bump | No release |
| Config/tooling only | `chore` | No bump | No release |

## Step 3: Determine Version Bumps

### 3a. Product Version (Release Train) — Relay's Domain

```bash
# Get today's date for Release Train tag
DATE=$(date +%Y.%m.%d)

# Check if a tag already exists for today
git tag -l "v$DATE*"

# Determine sub-index if multiple releases today
EXISTING_TAGS=$(git tag -l "v$DATE*" | wc -l)
if [ "$EXISTING_TAGS" -gt 0 ]; then
  SUBINDEX=$((EXISTING_TAGS + 2))
  PRODUCT_VERSION="$DATE.$SUBINDEX"
else
  PRODUCT_VERSION="$DATE"
fi
```

**Determine signal suffix:**

- If any changed file in `server/`, `interfaces/`, or `server/db/schema.ts` has breaking changes → append `-breaking`
- If changes are exclusively security fixes → append `-security`
- If new features are behind a feature flag → append `-preview`
- Otherwise → no suffix (routine release)

**Final product version examples:**
- `2026.07.24` — routine release with new features/fixes
- `2026.07.24.2` — second release same day (hotfix)
- `2026.07.24-breaking` — breaking changes requiring user action
- `2026.07.24-security` — security patch

### 3b. API Version (SemVer) — Sage's Domain

Check current API version from `server/api.ts` prefix and `package.json`:

```bash
# Check if package.json has a version field
cat package.json | grep -o '"version": *"[^"]*"' | head -1

# Check last SemVer git tag
git tag -l "v[0-9]*" --sort=-version:refname | head -5
```

**Determine SemVer bump based on changes:**

| Current State | Changes Detected | New Version | Rationale |
| ------------- | ---------------- | ----------- | --------- |
| No version field | Any | `0.1.0` | Initialize SemVer at 0.1.0 for beta |
| `0.x.y` | Bug fixes only | `0.x.(y+1)` | PATCH in 0.x |
| `0.x.y` | New features (additive) | `0.(x+1).0` | MINOR in 0.x |
| `0.x.y` | Breaking changes | `0.(x+1).0` | MINOR bump in 0.x (breaking allowed) |
| `1.x.y` or higher | Bug fixes only | `1.x.(y+1)` | PATCH |
| `1.x.y` or higher | New features (additive) | `1.(x+1).0` | MINOR |
| `1.x.y` or higher | Breaking changes | `(x+1).0.0` | MAJOR |

**Important for 0.x (beta):** Breaking changes bump MINOR, not MAJOR. This is per SemVer §4 — in 0.x, anything MAY change.

### 3c. Package Version (SemVer) — Sage's Domain

The package version in `package.json` follows the same SemVer rules as the API version. For a SaaS product (not a published library), the package version tracks the API SemVer version.

## Step 4: Apply Version Updates

> **Gate check:** Only proceed if Step 0 determined the changes are being merged to `main`. If in analysis-only mode, skip to Step 7.

### 4a. Update `package.json` Version

```bash
# Read current version (or default to 0.1.0 if missing)
CURRENT_VERSION=$(node -e "console.log(require('./package.json').version || '0.0.0')")

# New version determined in Step 3b
NEW_VERSION="[determined version]"

# Update package.json version field
# Use jq or manual edit — do NOT use npm version (it creates a git commit)
```

If `package.json` does not have a `version` field, add it as the second field after `"name"`:

```json
{
  "name": "my-app",
  "version": "0.1.0",
  "private": true,
  ...
}
```

### 4b. Update `release-train.json`

Update the Release Train version file with the new product version:

```json
{
  "current": {
    "name": "Beta",
    "version": "2026.07.25",
    "date": "2026-07-25",
    "sprint": "Beta-2026.07.24"
  },
  "history": [
    { "name": "Beta", "version": "2026.07.24", "date": "2026-07-24", "sprint": "Beta-2026.07.24" },
    { "name": "Beta", "version": "2026.07.24.2", "date": "2026-07-24", "sprint": "Beta-2026.07.24" },
    { "name": "Beta", "version": "2026.07.25", "date": "2026-07-25", "sprint": "Beta-2026.07.24" }
  ]
}
```

**Rules:**
- Move the previous `current` entry into `history` (append to end)
- Set `current` to the new Release Train version from Step 3a
- Keep `history` sorted by date (oldest first)
- The `name` field reflects the release train name (e.g., "Beta")
- **Set `sprint` on every new entry** — the sprint that owns the deployed work. Resolve it from the newest sprint file in `_bmad-output/implementation-artifacts/`: only files matching `sprint-status-<Channel>-YYYY.MM.DD[.N].yaml` count (skip non-dated files like `sprint-status-archive.yaml`); sort by the embedded `YYYY.MM.DD[.N]` descending. The winner's stem minus the `sprint-status-` prefix is the sprint ID (e.g. `Beta-2026.10.04.2`). If no dated sprint-status file exists, omit `sprint`.
- A sprint ID is version-*shaped* but is a label, not a release. It may differ from every version in `release-train.json` — that's expected: the `sprint` field is what records the association.

**Sprint boundary ≠ deploy boundary:** a version bump tags a deploy. It must NEVER create, rename, or migrate sprint artifacts (`sprint-status-*.yaml`, `epics-beta-*.md`, `implementation-artifacts/<version>/` spec folders, devlog dirs). Sprint transitions are a separate, user-initiated decision handled by `cdo-version-upgrade` — mid-sprint deploys leave all sprint files untouched.

### 4c. Update `nuxt.config.ts` Runtime Config

Expose the version to the client via Nuxt runtime config:

```typescript
// In nuxt.config.ts runtimeConfig.public:
runtimeConfig: {
  public: {
    appVersion: process.env.npm_package_version || "0.0.0",
    // ... existing config
  },
},
```

### 4d. Update API Version Prefix (if MAJOR bump)

If the SemVer bump is MAJOR (e.g., `1.x.x` → `2.0.0`), update the API URI prefix:

```typescript
// server/api.ts — update prefix when major version changes
export default () =>
  new Elysia({ prefix: "/v2" })  // Was "/v1", now "/v2"
    // ... routes
```

**Only do this on MAJOR bumps.** MINOR and PATCH bumps do NOT change the URI prefix.

**WARNING: Adding or changing the API prefix breaks ALL frontend API calls.** Before applying:
1. Search for all `$fetch`, `useFetch`, and `useAsyncData` calls that hit `/api/` endpoints
2. Update every call to include the new prefix (e.g., `/api/v1/areas` instead of `/api/areas`)
3. Update any store actions that construct API URLs
4. Update any composables that make API calls
5. Test all affected flows before committing

**For the initial `/v1` prefix addition**, this requires updating every API call across:
- `stores/*.ts` — all store actions using `$api` or `$fetch`
- `composables/*.ts` — any composable making API calls
- `components/**/*.vue` — any component making direct API calls
- `pages/**/*.vue` — any page making direct API calls
- `lib/*.ts` — any utility making API calls (e.g., `auth-client.ts`)

### 4e. Update Changelog

Create or update `CHANGELOG.md` following Keep a Changelog format:

```markdown
# Changelog

## [Unreleased]
### Added
- [New features from preview branch changes]

### Changed
- [Modified behavior from preview branch changes]

### Fixed
- [Bug fixes from preview branch changes]

### Security
- [Security fixes from preview branch changes]

### Removed
- [Removed features/APIs from preview branch changes]

## [PRODUCT_VERSION] - YYYY-MM-DD
### Added
- [Previous release features]

### Fixed
- [Previous release fixes]
```

**Changelog entry rules:**
- Group entries by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Each entry should be a single line, user-facing description
- Reference the file or feature, not the implementation detail
- If breaking change, include migration note

## Step 5: Prepare the Release Tag

Compute the tag name and message now — but do NOT run `git tag` yet. A tag created here would point at the pre-bump HEAD commit, before the version files are committed. Tag creation happens in Step 7, after the `chore(release)` commit lands (or inside `cdo-git-push` / `cdo-git-quick-push`, which own the commit+tag+push sequence).

```bash
# Compute — do not create yet
TAG_NAME="v$PRODUCT_VERSION"
TAG_MSG="Release $PRODUCT_VERSION

Changes:
- [summary from changelog]

SemVer: $NEW_VERSION
"

# If SemVer MAJOR bump, also prepare the API tag
API_TAG_NAME="api-v$MAJOR_VERSION"
```

**Tag naming conventions:**
- Product: `v2026.07.24`, `v2026.07.24.2`, `v2026.07.24-breaking`
- API: `api-v1`, `api-v2` (only on MAJOR bumps)

## Step 6: Verify Version Consistency

Run validation checks to ensure all version references are aligned:

```bash
# Check package.json version
grep '"version"' package.json

# Check release-train.json current version
grep '"version"' release-train.json | head -1

# Check nuxt.config.ts exposes version
grep 'appVersion' nuxt.config.ts

# Check API prefix matches major version
grep 'prefix' server/api.ts

# Check changelog has entry for new version
grep "$PRODUCT_VERSION" CHANGELOG.md

# Check the tag name is not already taken (collision check — the tag itself is created in Step 7)
git tag -l "v$PRODUCT_VERSION"
```

### Consistency Checklist

- [ ] `package.json` `version` field matches determined SemVer
- [ ] `release-train.json` `current.version` matches determined Release Train version
- [ ] `release-train.json` `current.sprint` matches the active sprint-status file (when one exists)
- [ ] `release-train.json` `history` includes previous version
- [ ] No sprint artifacts were created, renamed, or migrated (`sprint-status-*`, `epics-beta-*`, spec folders)
- [ ] `nuxt.config.ts` `runtimeConfig.public.appVersion` references release train version
- [ ] `server/api.ts` prefix matches MAJOR version (if MAJOR bump occurred)
- [ ] `CHANGELOG.md` has entry for new product version
- [ ] Tag name computed; `git tag -l "v$PRODUCT_VERSION"` returns empty (no collision)
- [ ] No uncommitted version-related files remain (all staged)

## Step 7: Summary Report

Present a version bump summary to the user:

```markdown
# Version Bump Summary

## Changes Analyzed
- **Files changed**: [count]
- **Change types**: [feat, fix, breaking, etc.]
- **Layers affected**: [Product, API, Package]

## Version Updates

| Layer | Scheme | Previous | New | Reason |
| ----- | ------ | -------- | --- | ------ |
| Product | Release Train | [last tag] | [new tag] | [routine/breaking/security] |
| API | SemVer | [old] | [new] | [minor/patch/major] |
| Package | SemVer | [old] | [new] | [minor/patch/major] |

## Files Modified
- `package.json` — version field updated
- `release-train.json` — current version updated, previous moved to history, `sprint` field set to owning sprint
- `nuxt.config.ts` — runtimeConfig.appVersion added/updated
- `server/api.ts` — prefix updated (if MAJOR bump)
- `CHANGELOG.md` — new release entry added

## Git Tags Created
- `v[PRODUCT_VERSION]` — product release tag
- `api-v[MAJOR]` — API version tag (if MAJOR bump)

## Next Steps (in order — commit before tag before push)
- [ ] Review changes with `git diff`
- [ ] Stage version files: `git add package.json release-train.json nuxt.config.ts server/api.ts CHANGELOG.md`
- [ ] Commit as `chore(release): bump version to $NEW_VERSION` (or hand off to `cdo-git-push` / `cdo-git-quick-push`, which own staging, commit, tag, and push)
- [ ] Create the tag on that commit: `git tag -a "$TAG_NAME" -m "$TAG_MSG"` (+ `git tag -a "$API_TAG_NAME" ...` on MAJOR bumps)
- [ ] Push: `git push` then `git push origin --tags`
```

## Agent Delegation Reference

This workflow coordinates three versioning agents. Here's when to invoke each:

| Scenario | Lead Agent | Support Agent | Skill |
| -------- | ---------- | ------------- | ----- |
| Full versioning strategy analysis | Vera | Sage + Relay | `bmad-versioning-agent-orchestrator` |
| API backward compatibility check | Sage | Vera | `bmad-versioning-agent-semver` |
| Release Train tag generation | Relay | Vera | `bmad-versioning-agent-release-train` |
| Breaking change detection | Sage | Relay | `bmad-versioning-agent-semver` |
| Changelog format and entries | Relay | Vera | `bmad-versioning-agent-release-train` |
| Migration from SemVer to Release Train | Relay | Sage | `bmad-versioning-agent-release-train` |
| Deprecation policy design | Sage | Vera | `bmad-versioning-agent-semver` |
| Hotfix versioning workflow | Relay | None | `bmad-versioning-agent-release-train` |

## Edge Cases

### No Version Field in `package.json`
If `package.json` has no `version` field:
1. Initialize at `0.1.0` (honest beta per SemVer §4)
2. Add as second field after `"name"`
3. Proceed with normal workflow

### Only Test/Docs Changes
If changes between the preview branch and `origin/main` are exclusively in `tests/`, `docs/`, `.devin/`, or `_bmad/`:
- No version bump required
- No changelog entry needed
- Skip to Step 7 with "No version bump — test/docs only changes"

### Mixed Breaking and Non-Breaking Changes
If changes include both breaking and non-breaking modifications:
- The breaking change dominates — use `-breaking` suffix
- SemVer: bump MAJOR (or MINOR if still in 0.x)
- Changelog: document all changes, but the signal suffix reflects the highest severity

### Mid-Sprint Deploy
Deploying a batch of stories that belong to an in-flight sprint is the normal case, not an edge case:
- Tag with the real deploy date (and `.N` / signal suffix as usual) — never freeze or suffix the version to preserve the sprint association (no `v2026.07.24-x` patterns)
- Set `sprint` on the release-train entry to the active sprint ID
- Do NOT run `cdo-version-upgrade` — sprint files stay exactly as they are
- The sprint file only changes when the user explicitly starts a new sprint

### Same-Day Multiple Releases
If a tag for today already exists:
- Use `.N` sub-index: `2026.07.24.2`, `2026.07.24.3`
- Each sub-release gets its own changelog entry
- Hotfixes should be scoped — no feature creep

### Database Schema Changes
Database schema changes in `server/db/schema.ts` are always potentially breaking:
- Column added → MINOR (additive, backward compatible)
- Column removed/renamed → MAJOR (breaking)
- Table added → MINOR (additive)
- Table removed → MAJOR (breaking)
- Type change (e.g., `text` → `integer`) → MAJOR (breaking)

### Preview Branch Is Behind origin/main
If the preview branch has fallen behind `origin/main` (i.e., `origin/main` has commits not on the preview branch):
1. Warn the user that the preview branch is not up to date with `origin/main`
2. Recommend rebasing or merging `origin/main` into the preview branch first
3. Re-run this workflow after the preview branch is back in sync
