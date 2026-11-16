---
name: cdo-git-push
description: Organized git push workflow for commits grouped by functionality and intent — CDO-owned copy invoked by the delivery org's pipeline
---

# Git Push Workflow - Functionality & Intent Based

## Overview

This workflow helps you organize and push commits in logical groups based on functionality and intent, ensuring clean, readable git history. **All push commands now dynamically detect and push to the current branch.**

## On Activation

1. Load config via `bmad-init` if available; communicate in `{communication_language}`.
2. Check Prerequisites below — especially whether the caller already supplied verification (e.g. `cdo-code-e2e` health-check) and whether the version workflow ran.
3. Execute the Workflow Steps in order. The commit-plan gate is non-negotiable: no `git add`, `git commit`, or `git push` runs without explicit user approval.

## Prerequisites

- **User approval of the commit plan** — this skill presents planned commit groups + messages before staging (see the gate below); never commit, not even locally, without it
- **Verification** — either supplied by the caller (e.g. `cdo-code-e2e` step 11 passes the pipeline's health-check result: type-check, lint, build) or run in Step 1
- Bun package manager installed and configured
- **Version workflow run** — `/cdo-version-change-for-production` should be run BEFORE this workflow to determine version bumps and update `CHANGELOG.md`, `package.json`, `release-train.json`, and `nuxt.config.ts`

## Workflow Steps

### 1. Pre-Execution Validation

**Skip this step when the caller already verified** — invoked from `cdo-code-e2e` step 11, the pipeline's health-check (type-check, lint, `bun run build`) is authoritative; re-running it is waste, not safety.

Otherwise, run the checks that exist in `package.json` via `bun` — missing scripts are skips, not failures. Use `test:run`, not `test` — bare `test` starts vitest in watch mode and hangs.

```bash
// Working tree state (a dirty tree is expected — committing it is this skill's job)
git status --porcelain

// Lint
bun run lint
if [[ $? -ne 0 ]]; then
  echo "ERROR: Linting errors. Fix linting before proceeding."
  exit 1
fi

// Tests
bun run test:run
if [[ $? -ne 0 ]]; then
  echo "ERROR: Tests failing. Fix tests before proceeding."
  exit 1
fi

// Build — a push that doesn't build is a broken ship
bun run build
if [[ $? -ne 0 ]]; then
  echo "ERROR: Build failing. Fix before proceeding."
  exit 1
fi

// Verify no sensitive data in the uncommitted changes
git diff HEAD --name-only | xargs grep -l "password\|secret\|key\|token" 2>/dev/null
if [[ $? -eq 0 ]]; then
  echo "WARNING: Potential sensitive data detected. Review before pushing."
fi
```

#### 1a. Version Workflow Context Check

Before proceeding with commits, check whether the `/cdo-version-change-for-production` workflow was run in the current session. The version workflow produces a **Version Bump Summary** that determines:

- **Product version** (Release Train tag: `YYYY.MM.DD[-signal]`)
- **API/package version** (SemVer bump: `0.x.y`)
- **Changelog entries** (added to `CHANGELOG.md` under `[Unreleased]`)
- **Files modified** (`package.json`, `nuxt.config.ts`, `CHANGELOG.md`, `release-train.json`)

**How to check:**

1. **Check chat context** — Look for a "Version Bump Summary" report in the conversation history. If found, use its output to:
   - Include version-related files (`package.json`, `nuxt.config.ts`, `CHANGELOG.md`, `release-train.json`) in the appropriate commit group
   - Use the determined version in commit messages where relevant (e.g., `chore(release): bump version to 0.1.0`)
   - Include the Release Train tag in the push step if a tag was created

2. **Check for version file changes** — If no version summary is found in chat context, check if version files were modified:

```bash
// Check if version files have uncommitted changes
// (porcelain covers modified AND untracked — a newly created release-train.json
// is invisible to plain git diff)
git status --porcelain | grep -E '(package\.json|nuxt\.config\.ts|CHANGELOG\.md|release-train\.json)'
if [[ $? -eq 0 ]]; then
  echo "Version files modified — include in commit grouping"
fi

// Check if CHANGELOG.md has unreleased entries
git diff CHANGELOG.md | grep -q '\[Unreleased\]'
if [[ $? -eq 0 ]]; then
  echo "CHANGELOG.md has unreleased entries — ensure they are included in commit"
fi
```

3. **If version workflow was NOT run** — Prompt the user (skip this prompt if a calling workflow — e.g. the `cdo-code-e2e` ship gate — already collected the decision; don't ask twice):
   > The version workflow (`/cdo-version-change-for-production`) was not detected in this session.
   > Would you like to:
   > - **A)** Run it now before committing (recommended for product/API changes)
   > - **B)** Skip it (acceptable for tooling/docs/test-only changes that don't require version bumps)
   > - **C)** Proceed anyway (version files will be committed as-is)

**Context integration rules:**

| Version Workflow Output | Git Push Action |
| ----------------------- | --------------- |
| No version bump (tooling/docs only) | Proceed normally — no version files to stage |
| Version bump determined, files modified | Stage version files (`package.json`, `nuxt.config.ts`, `CHANGELOG.md`, `release-train.json`) in a dedicated `chore(release)` commit group |
| Version bump determined | **Prompt user** whether to tag now or defer until merge to `main` |
| Breaking change detected | Ensure `-breaking` suffix in tag and `BREAKING CHANGE` footer in commit message |
| Security fix detected | Ensure `-security` suffix in tag and `Security` section in changelog |

### 2. Analyze Current Changes

```bash
// Check current status
git status

// Review staged and unstaged changes
git diff --cached
git diff

// See commit history
git log --oneline -10
```

#### 2a. Incorporate Version Workflow Context

If the version workflow was run (Step 1a), use its summary to inform commit grouping:

- **Version files** (`package.json`, `nuxt.config.ts`, `CHANGELOG.md`, `release-train.json`) → group into a `chore(release)` commit
- **Product code changes** that triggered the version bump → group by functionality as normal
- **The version summary's change classification** (feat, fix, breaking, security) → use to validate commit message types match

Example grouping with version context:
```
Group 1: feat(auth): add OAuth2 integration          ← product code
Group 2: fix(api): correct validation on user creation ← product code
Group 3: chore(release): bump version to 0.1.0       ← version files (from version workflow)
           - package.json version field
           - nuxt.config.ts appVersion in runtimeConfig
           - release-train.json current + history (with sprint field)
           - CHANGELOG.md unreleased entries
```

### 2. Group Changes by Functionality

Identify logical groups for your commits:

#### Common Functionality Categories:

- **feat**: New features
- **fix**: Bug fixes
- **refactor**: Code refactoring without functional changes
- **perf**: Performance improvements
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **test**: Adding or updating tests
- **chore**: Build process, dependency updates, etc.

#### Intent Categories:

- **user-facing**: Changes visible to end users
- **internal**: Infrastructure, refactoring, technical debt
- **security**: Security-related changes
- **breaking**: Changes that break existing functionality

### ⛔ Commit Plan Approval (GATE)

Before staging anything, present the plan — each commit's group, file list, and drafted `type(scope): message` — and get explicit approval via `ask_user_question` (confirm / adjust / abort). **Never run `git add` or `git commit` on assumption** — shipping is user-gated. When invoked from `cdo-code-e2e`, its ship gate authorizes *whether* to ship; this gate confirms *what* lands in each commit.

### 3. Execute File Staging

// Execute staging with precision checks

```bash
// Stage files for specific functionality
git add path/to/feature/files/
git add path/to/related/tests/

// Verify what's staged
git status
git diff --cached --name-only

// Validate staged files have corresponding tests
staged_files=$(git diff --cached --name-only)
for file in $staged_files; do
  if [[ $file == *.vue || $file == *.ts || $file == *.js ]]; then
    test_file="${file%.*}.test.${file##*.}"
    if [[ ! -f $test_file ]]; then
      echo "WARNING: No test file found for $file"
    fi
  fi
done
```

### 4. Execute Commit Creation

// Execute commit with strict message validation

```bash
// Function to validate commit message format
validate_commit_msg() {
  local msg="$1"
  if [[ ! $msg =~ ^(feat|fix|refactor|perf|docs|style|test|chore)(\(.+\))?: .+ ]]; then
    echo "ERROR: Invalid commit message format. Use: type(scope): description"
    return 1
  fi
  return 0
}

// Execute commits with validation
validate_commit_msg "feat(auth): implement OAuth2 integration with Google"
git commit -m "feat(auth): implement OAuth2 integration with Google"

validate_commit_msg "feat(ui): add responsive navigation menu for mobile"
git commit -m "feat(ui): add responsive navigation menu for mobile"

validate_commit_msg "fix(auth): resolve token expiration handling edge case"
git commit -m "fix(auth): resolve token expiration handling edge case"

validate_commit_msg "fix(api): correct data validation on user creation"
git commit -m "fix(api): correct data validation on user creation"

validate_commit_msg "refactor(store): extract common state logic to base composable"
git commit -m "refactor(store): extract common state logic to base composable"

validate_commit_msg "refactor(api): consolidate duplicate endpoint handlers"
git commit -m "refactor(api): consolidate duplicate endpoint handlers"

validate_commit_msg "perf(query): optimize database queries with proper indexing"
git commit -m "perf(query): optimize database queries with proper indexing"

validate_commit_msg "perf(components): implement lazy loading for heavy components"
git commit -m "perf(components): implement lazy loading for heavy components"
```

### 5. Execute Pre-Push Validation

// Execute comprehensive pre-push checks

```bash
// Review commits before pushing
git log --oneline -5
git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' -10

// Show changes in each commit
git show --stat HEAD

// Tests/lint/build already ran in Step 1 (or were supplied by the caller) —
// committing doesn't change file contents, so a post-commit re-run is redundant.
// Only re-run if Step 1 verification was skipped entirely:
bun run test:run
if [[ $? -ne 0 ]]; then
  echo "ERROR: Tests failing after commits. Fix before pushing."
  exit 1
fi

// Verify commit message format for all new commits
// (iterate subject lines, not words — `for x in $(...)` word-splits and false-fails on every real commit)
bad_commits=$(git log origin/main..HEAD --format='%s' | grep -vE '^(feat|fix|refactor|perf|docs|style|test|chore|build|ci|revert)(\(.+\))?!?: .+')
if [[ -n $bad_commits ]]; then
  echo "ERROR: Invalid commit message format:"
  echo "$bad_commits"
  exit 1
fi

// Verify version files are included if version workflow was run
for vf in package.json nuxt.config.ts CHANGELOG.md release-train.json; do
  if [[ -f $vf ]] && ! git diff --cached --name-only | grep -q "^$vf$"; then
    if git status --porcelain | grep -q "$vf"; then
      echo "WARNING: $vf has uncommitted changes — include in a chore(release) commit"
    fi
  fi
done

// Check for merge conflicts before push
git fetch origin
if [[ $(git merge-base main HEAD) != $(git rev-parse main) ]]; then
  echo "WARNING: Potential merge conflicts detected. Consider rebasing."
fi
```

### 6. Execute Push Strategy

// Execute push based on validated strategy

#### Option A: Execute All Commits Push

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Execute push for related functionality
git push origin $current_branch
if [[ $? -eq 0 ]]; then
  echo "SUCCESS: All commits pushed to $current_branch"
else
  echo "ERROR: Push failed. Resolve conflicts and retry."
  exit 1
fi
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

**If user chooses to tag:**

```bash
// Determine tag name from version workflow output or date
DATE=$(date +%Y.%m.%d)

// Check for existing tags today
EXISTING_TAGS=$(git tag -l "v$DATE*")
if [[ -n "$EXISTING_TAGS" ]]; then
  SUBINDEX=$(($(echo "$EXISTING_TAGS" | wc -l) + 1))
  TAG="v$DATE.$SUBINDEX"
else
  TAG="v$DATE"
fi

// Append signal suffix if version workflow determined one
// -breaking, -security, -preview as needed

// Create and push tag
git tag $TAG
git push origin $TAG
echo "SUCCESS: Tag $TAG created and pushed"
```

#### Option B: Execute Incremental Feature Pushes

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Execute push each feature group separately
git push origin $current_branch
if [[ $? -eq 0 ]]; then
  echo "SUCCESS: $current_branch pushed"
else
  echo "ERROR: $current_branch push failed"
  exit 1
fi

// For multiple branches, loop through them:
branches=("feature-auth-integration" "feature-ui-improvements" "fix-bug-resolution")
for branch in "${branches[@]}"; do
  git push origin $branch
  if [[ $? -eq 0 ]]; then
    echo "SUCCESS: $branch pushed"
  else
    echo "ERROR: $branch push failed"
    exit 1
  fi
done
```

#### Option C: Execute Squash and Push

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Execute interactive rebase to squash related commits
git rebase -i HEAD~3
if [[ $? -eq 0 ]]; then
  echo "SUCCESS: Commits squashed successfully"
else
  echo "ERROR: Rebase failed. Resolve conflicts and continue."
  exit 1
fi

// Execute push of cleaned up history
git push --force-with-lease origin $current_branch
if [[ $? -eq 0 ]]; then
  echo "SUCCESS: Squashed commits pushed to $current_branch"
else
  echo "ERROR: Force push failed"
  exit 1
fi
```

## Best Practices

### Commit Message Guidelines

- **Present tense**: "Add feature" not "Added feature"
- **Imperative mood**: "Fix bug" not "Fixes bug" or "Fixed bug"
- **Scope**: Specify the area affected (auth, ui, api, etc.)
- **Body**: Add detailed explanation for complex changes

### Grouping Strategy

1. **User-facing features** → Push together
2. **Internal refactoring** → Can be pushed separately
3. **Bug fixes** → Group with related features or push separately
4. **Breaking changes** → Push last with clear communication

### Before Pushing Checklist

- [ ] Commit plan approved by user (groups + messages)
- [ ] Verification passed — supplied by caller or run via `bun` (`lint`, `test:run`, `build`; missing scripts are skips)
- [ ] Code reviewed (if applicable)
- [ ] Commit messages follow conventions
- [ ] Related commits grouped logically
- [ ] No sensitive data in commits
- [ ] Dependencies updated and secure (`bun update`)

## Advanced Scenarios

### Emergency Hotfixes

```bash
// Get current branch for reference
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Create hotfix branch from main
git checkout -b hotfix/critical-bug-fix main

// Make minimal fix
git add .
git commit -m "fix: resolve critical security vulnerability in auth"
git push origin hotfix/critical-bug-fix

// Return to original branch
git checkout $current_branch

// Create PR and merge urgently
```

### Feature Branch Organization

```bash
// Get current branch for reference
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Create feature branch with descriptive name
git checkout -b feature/user-authentication-flow

// Work in logical commits
git add auth/components/
git commit -m "feat(auth): add login and registration components"

git add auth/services/
git commit -m "feat(auth): implement authentication service layer"

git add auth/tests/
git commit -m "test(auth): add comprehensive test coverage for auth flow"

// Push feature branch
git push origin feature/user-authentication-flow

// Return to original branch if needed
git checkout $current_branch
```

### Large Refactoring Projects

```bash
// Get current branch for reference
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Break into logical phases
git commit -m "refactor(api): phase 1 - extract base controller class"
git commit -m "refactor(api): phase 2 - implement dependency injection"
git commit -m "refactor(api): phase 3 - migrate existing endpoints"
git commit -m "test(api): add tests for refactored controller structure"

// Push after each phase if stable
git push origin $current_branch
```

## Troubleshooting

### Force Push Scenarios

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Use force-with-lease instead of force
git push --force-with-lease origin $current_branch

// Check if safe to force push
git fetch origin
git log --oneline origin/$current_branch..HEAD
```

### Merge Conflicts Before Push

```bash
// Get current branch dynamically
current_branch=$(git rev-parse --abbrev-ref HEAD)

// Sync with remote before pushing
git fetch origin
git rebase origin/main

// Resolve conflicts, then push
git push origin $current_branch
```

### Undo Last Commit

```bash
// Soft reset (keep changes)
git reset --soft HEAD~1

// Hard reset (lose changes)
git reset --hard HEAD~1

// Amend last commit
git commit --amend -m "new commit message"
```

## Integration with Development Workflow

This workflow integrates seamlessly with:

- **Code reviews**: Group commits for easier review
- **CI/CD**: Clean triggers for automated testing
- **Release management**: Clear changelog generation
- **Team collaboration**: Understandable commit history

## Automation Scripts

### Pre-push Hook (Optional)

```bash
#!/bin/sh
# .git/hooks/pre-push

# Run tests
bun run test:run

# Check commit message format
git log -1 --pretty=%s | grep -E "^(feat|fix|refactor|perf|docs|style|test|chore)(\(.+\))?: .+"

# Exit with error if any check fails
if [ $? -ne 0 ]; then
    echo "Pre-push checks failed!"
    exit 1
fi
```

### Commit Helper Script

```bash
#!/bin/bash
# commit-helper.sh

echo "Available commit types:"
echo "1. feat:     New feature"
echo "2. fix:      Bug fix"
echo "3. refactor: Code refactoring"
echo "4. perf:     Performance improvement"
echo "5. docs:     Documentation"
echo "6. style:    Code style"
echo "7. test:     Tests"
echo "8. chore:    Build process/dependencies"

read -p "Choose type (1-8): " type
read -p "Enter scope (e.g., auth, ui, api): " scope
read -p "Enter description: " desc

case $type in
    1) prefix="feat" ;;
    2) prefix="fix" ;;
    3) prefix="refactor" ;;
    4) prefix="perf" ;;
    5) prefix="docs" ;;
    6) prefix="style" ;;
    7) prefix="test" ;;
    8) prefix="chore" ;;
esac

commit_msg="$prefix($scope): $desc"
git add .
git commit -m "$commit_msg"
echo "Committed: $commit_msg"
```
