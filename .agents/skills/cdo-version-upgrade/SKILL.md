---
name: cdo-version-upgrade
description: 'Handle a sprint-boundary version upgrade: migrate non-done stories to a new release, renumber epics and stories, reorder by priority, archive old release artifacts, and verify consistency. Use when the user says "bump version", "new release", "version upgrade", or "new sprint version" — CDO-owned copy invoked by the delivery org''s pipeline, delegated from cdo-platform.'
---

# Project Version Upgrade

## Overview

Migrates non-done stories to a new sprint release: renumber epics and stories, move spec files, archive old release artifacts, verify consistency. Runs ONLY at a user-initiated sprint boundary — never as a side effect of a production deploy (mid-sprint deploys are handled by `cdo-version-change-for-production`).

## Resolution rules

- Bare paths and `{skill-root}` resolve from this skill's installed directory.
- `{project-root}` → the project working directory.

## On Activation

1. Load config via `bmad-init`; communicate in `{communication_language}`.
2. Confirm the user is starting a new sprint (not just shipping a deploy). If unsure, ask before doing anything. Under a headless invocation (`-H`/`--yes` from `cdo-platform`), require an explicit `--new-version` — else return a `blocked` result; the mechanics are scripted (`scripts/resolve-upgrade.py` → `partition-renumber.py` → `verify-migration.py`), no prompting.
3. Follow the instructions in `references/workflow.md`.
