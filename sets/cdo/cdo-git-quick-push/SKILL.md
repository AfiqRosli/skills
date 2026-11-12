---
name: cdo-git-quick-push
description: Quick git push workflow for fast, clean commits — CDO-owned copy invoked by the delivery org's pipeline
---

# Git Quick Push Workflow

## Overview

A streamlined workflow for fast, clean git commits and pushes. Perfect for small changes and quick iterations — and the default ship owner for `cdo-code-e2e` when the uncommitted tree is exactly the story's cohesive change set.

## On Activation

1. Load config via `bmad-init` if available; communicate in `{communication_language}`.
2. Run Step 0 (Version Workflow Context Check), then the Quick Steps in order.
3. The commit-plan gate is non-negotiable: no `git add`, `git commit`, or `git push` runs without explicit user approval — even when invoked by `cdo-code-e2e`.

**Execute this workflow via bmad-agent-dev (Amelia) for automated push execution.**

**Hard rule — gated shipping:** never run `git add` or `git commit` without explicit user approval of the commit plan, and never `git push` without approval. Present the plan first — no commit, not even a local one, lands on assumption.

**Verification context:** if the caller already verified the change — e.g. invoked from `cdo-code-e2e` step 11 with a passing health-check (type-check, lint, build) — do NOT re-run checks; that result is authoritative and re-running is waste, not safety. Otherwise run the checks that exist in `package.json` via `bun` (`bun run lint`, `bun run test:run`, `bun run build`) — missing scripts are skips, not failures. Use `test:run`, not `test` — bare `test` starts vitest in watch mode and hangs.

## Prerequisites

- **Version workflow run** — `/cdo-version-change-for-production` should be run BEFORE this workflow to determine version bumps and update `CHANGELOG.md`, `package.json`, `release-train.json`, and `nuxt.config.ts`

## Quick Steps

### 0. Version Workflow Context Check

Before staging, check whether the `/cdo-version-change-for-production` workflow was run in the current session:

1. **Check chat context** — Look for a "Version Bump Summary" report in the conversation history. If found, use its output to:
   - Include version-related files (`package.json`, `nuxt.config.ts`, `CHANGELOG.md`, `release-train.json`) in a dedicated `chore(release)` commit
   - Use the determined version in commit messages where relevant (e.g., `chore(release): bump version to 0.1.0`)
   - Prompt user about tagging after push (see Step 3)

2. **Check for version file changes** — If no version summary is found in chat context:

```bash
// Check if version files have uncommitted changes
// porcelain covers modified AND untracked — a newly created release-train.json
// is invisible to plain git diff
git status --porcelain | grep -E '(package\.json|nuxt\.config\.ts|CHANGELOG\.md|release-train\.json)'
if [[ $? -eq 0 ]]; then
  echo "Version files modified — stage in a chore(release) commit"
fi
```

3. **If version workflow was NOT run** — Prompt the user (skip this prompt if a calling workflow — e.g. the `cdo-code-e2e` ship gate — already collected the decision; don't ask twice):
   > The version workflow (`/cdo-version-change-for-production`) was not detected in this session.
   > Would you like to:
   > - **A)** Run it now before committing (recommended for product/API changes)
   > - **B)** Skip it (acceptable for tooling/docs/test-only changes)
   > - **C)** Proceed anyway

**Context integration rules:**

| Version Workflow Output | Quick Push Action |
| ----------------------- | ----------------- |
| No version bump (tooling/docs only) | Proceed normally — no version files to stage |
| Version bump determined, files modified | Stage version files in a `chore(release)` commit |
| Version bump determined | **Prompt user** whether to tag now or defer until ready to merge to `main` |
| Breaking change detected | Ensure `BREAKING CHANGE` footer in commit message |
| Security fix detected | Ensure `Security` section in changelog |

### 1. Plan Commits, Get Approval, Stage (GATE)

Group the changed files by functionality and draft a `type(scope): description` message per group — one commit is fine for a cohesive change. Present the plan via `ask_user_question` (confirm / adjust / abort). **Only after confirmation**, stage:

```bash
// Stage files by theme/functionality - do NOT use git add .
// Group related files together

// Example: Authentication feature
git add auth/components/
git add auth/services/
git add auth/tests/

// Example: UI components
git add components/Header.vue
git add components/Navigation.vue

// Example: API endpoints
git add server/api/users/
git add server/api/auth/

// Example: Version files (if version workflow was run)
git add package.json
git add nuxt.config.ts
git add CHANGELOG.md
git add release-train.json
```

### 2. Commit with Conventional Format

```bash
// Format: type(scope): description
// Types: feat, fix, refactor, docs, style, test, chore

git commit -m "feat(auth): add user login"
git commit -m "fix(api): resolve timeout error"
git commit -m "docs: update README"
git commit -m "refactor: simplify component structure"
```

### 3. Push and Prompt About Tagging

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Push commits
git push origin $current_branch
```

**After push completes — prompt user about tagging:**

Ask the user:
> Commits pushed to `$current_branch`. Would you like to create a Release Train tag?
> - **A) Yes — create tag `vYYYY.MM.DD`** (if these changes are ready to merge to main)
> - **B) No — skip tagging** (if this is an internal/preview push; tag will be created when ready to merge to `main`)

**Tagging decision guidance:**

| Scenario | Tag? |
| -------- | ---- |
| Pushing to `preview` for internal testing | No — tag when ready to merge to `main` |
| Ready to merge to `main` (production release) | Yes — tag the commit |
| Tooling/docs/test-only changes | No — no user-facing release |
| Hotfix to `main` | Yes — use sub-index if same day (e.g., `v2026.07.24.2`) |

## Commit Message Examples

```bash
// Features
git commit -m "feat(ui): add responsive navigation"
git commit -m "feat(api): implement user endpoints"

// Bug fixes
git commit -m "fix(auth): resolve token expiration"
git commit -m "fix(ui): correct mobile layout issue"

// Documentation
git commit -m "docs: update installation guide"
git commit -m "docs: add API documentation"

// Refactoring
git commit -m "refactor(store): extract common logic"
git commit -m "refactor(api): consolidate handlers"

// Tests
git commit -m "test(auth): add login flow tests"
git commit -m "test(api): add endpoint coverage"

// Chores
git commit -m "chore: update dependencies"
git commit -m "chore: configure linter"
```

## Quick Checklist

- [ ] Version workflow run (or skipped for tooling/docs-only changes)
- [ ] Version files staged in `chore(release)` commit (if version bump occurred)
- [ ] Commit plan approved by user (files + messages)
- [ ] Changes staged
- [ ] Commit message follows format
- [ ] Verification passed — supplied by caller or run via `bun` (`lint`, `test:run`, `build`; missing scripts are skips)
- [ ] Ready to push
- [ ] Tagging decision made (tag created if ready to merge to `main`)

## Common Commands

```bash
// Check status
git status

// View changes
git diff

// View commit history
git log --oneline -5

// Undo last commit (keep changes)
git reset --soft HEAD~1

// Amend last commit message
git commit --amend -m "new message"
```
