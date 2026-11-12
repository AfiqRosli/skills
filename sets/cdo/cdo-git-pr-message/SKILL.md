---
name: cdo-git-pr-message
description: Generate PR title and description from commits between current branch and main — CDO-owned copy invoked by the delivery org's pipeline
---

# Git PR Message Workflow

Generates a structured PR title and description by comparing commits between the current branch and `origin/main`.

## Prerequisites

- **Version workflow run** — `/cdo-version-change-for-production` should be run BEFORE this workflow to determine version bumps and update `CHANGELOG.md`, `package.json`, and `nuxt.config.ts`

## Steps

### 0. Version Workflow Context Check

Before generating the PR message, check whether the `/cdo-version-change-for-production` workflow was run in the current session:

1. **Check chat context** — Look for a "Version Bump Summary" report in the conversation history. If found, use its output to:
   - Include version information in the PR title and description
   - Reference the Release Train tag (if one was created or deferred)
   - Note the SemVer bump (if any) in the PR description

2. **Check for version file changes in the diff** — If no version summary is found in chat context, check if version files are part of the PR:

```bash
// Check if version files are in the diff between current branch and main
git diff origin/main..HEAD --name-only | grep -E '(package\.json|nuxt\.config\.ts|CHANGELOG\.md)'
if [[ $? -eq 0 ]]; then
  echo "Version files detected in PR — include versioning section in description"
fi
```

3. **Check for Release Train tags** — See if a tag was created for this PR's changes:

```bash
// List tags between origin/main and HEAD
git tag --merged HEAD --no-merged origin/main -l "v[0-9]*"
```

**Context integration rules:**

| Version Workflow Output | PR Message Action |
| ----------------------- | ----------------- |
| No version bump (tooling/docs only) | Proceed normally — no version section needed |
| Version bump determined | Include version section in PR description with SemVer and Release Train versions |
| Release Train tag created | Reference tag in PR description (e.g., "Tag: v2026.07.24") |
| Tag deferred (preview push) | Note in PR description that tag will be created on merge to `main` |
| Breaking change detected | Add `BREAKING CHANGES` section to PR description |
| Security fix detected | Add `Security` section to PR description |

### 1. Fetch Latest Remote

```bash
// turbo
git fetch origin
```

### 2. Get Current Branch Latest Commit

```bash
git log -1 --format="%H%n%s%n%b" HEAD
```

### 3. Get Main Branch Latest Commit

```bash
git log -1 --format="%H%n%s%n%b" origin/main
```

### 4. List Commits Ahead of Main

```bash
git log origin/main..HEAD --oneline
```

### 5. Get Diff Summary

```bash
git diff origin/main..HEAD --stat
```

### 6. Generate PR Title and Description

Using the gathered information (including version workflow context from Step 0), generate:

- **PR Title** — A concise conventional-commit-style summary of all changes (e.g., `feat: short description of main theme`)
- **PR Description** — A structured markdown document containing:
  - **Summary** — 1-2 paragraph overview of the PR's purpose
  - **Changes** — Categorized list (Features, Refactors, Documentation, Tooling, etc.) with bullet points referencing specific files and what changed
  - **Versioning** — Version bump details (SemVer, Release Train tag, changelog reference) if version workflow was run
  - **Files Changed** — Total file count and insertions/deletions
  - **Commits** — List of all commits with short hash and message

### PR Title Format

```
type: concise summary of main change theme
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`

If multiple types are present, use the most significant one. If equally significant, use `feat` or combine with `+`:

```
feat: add DB sync tooling and revise landing page copy
```

### PR Description Template

```markdown
## Summary

[1-2 paragraph overview of what this PR accomplishes and why]

## Changes

### Features
- **[Brief description]** (`path/to/file`) — [what it does]

### Refactors
- **[Brief description]** (`path/to/file`) — [what changed]

### Documentation
- **[Brief description]** (`path/to/file`) — [what was added]

### Tooling
- **[Brief description]** (`path/to/file`) — [what was added]

## Versioning

- **SemVer**: [current] → [new] (e.g., `0.1.0` → `0.2.0`)
- **Release Train**: `vYYYY.MM.DD` (or "tag deferred — will be created on merge to `main`")
- **Changelog**: Updated in `CHANGELOG.md` under `[YYYY.MM.DD]`

### Breaking Changes
> [If breaking changes detected, list them here with migration guidance]

### Security
> [If security fixes detected, describe the vulnerability and fix]

## Files Changed
[N] files changed, [N] insertions(+), [N] deletions(-)

## Commits
1. `[short hash]` [commit message]
2. `[short hash]` [commit message]
...
```

Only include categories that have changes. Omit empty categories.

**Versioning section** — Only include if the version workflow was run or version files are in the diff. If no version bump occurred (tooling/docs/test-only), omit the entire section.

**Breaking Changes / Security sections** — Only include if the version workflow detected breaking or security changes.
