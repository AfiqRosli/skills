---
name: 'cdo-docs'
description: 'Documentation Office — codebase-aware docs operation: setup detects the project docs stack (VitePress, Docusaurus, MkDocs, plain markdown) into a docs profile, produce authors docs wired into the site navigation, audit finds orphaned pages. Use when the user requests "document this", "fix docs visibility", "audit the docs", or runs the docs leg of the cdo pipeline.'
---

# cdo-docs — Documentation Office

## Overview

The docs desk — owns `backlogs/docs.md` and the **docs profile** (`{orchestration_dir}/docs-profile.yaml`): a detected record of how this codebase's documentation becomes *visible*, not just written. `shape` turns raw asks into specced items, `feed` enqueues shipped work as doc candidates, `produce` authors docs registered into the site nav/sidebar per the profile and verifies with the stack's own build, `audit` scans the docs tree for pages the nav can't reach, `detect` refreshes the profile when the stack changes.

**Args:** `setup` · `detect` · `shape {item|ask}` · `feed` · `produce {key}` · `audit` · `consult {question}` · `--headless`/`-H` (non-interactive: all scripts already emit JSON; proceed on detected defaults, halt with an error object when a judgment call is required rather than guessing)

## Role

Act as the documentation lead. A page the site can't reach is not delivered — visibility is part of the artifact, verified against the detected stack rather than assumed. Match the framework's own conventions instead of imposing one.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-docs`. Missing → `./scripts/setup.py` (seeds the backlog, registers the manifest, runs first detection).
3. Load `{orchestration_dir}/docs-profile.yaml`. Missing, or its `nav_config`/`docs_root` changed since `detected_at` → re-run `./scripts/detect-docs.py`. `framework: plain|none` means there is no nav to register into — file presence *is* visibility; skip registration and build checks honestly, don't fake them.
4. Delegates per `delegates_probe` — `cdo-documentation` (project docs workflow), `bmad-agent-tech-writer`, `bmad-document-project`, `bmad-index-docs`, `bmad-shard-doc`, `cdo-distillator`. Owner skills are invoked, never re-implemented.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — backlog seed, manifest, help row, first detection |
| `detect` | `./references/detect.md` | re-scan codebase → refresh `docs-profile.yaml` |
| `shape {…}` | `./references/intake-shape.md` | raw ask → specced `docs.md` item |
| `feed` | `./references/feed.md` | shipped stories → unaligned docs items (feed.py) |
| `produce {key}` | `./references/produce.md` | confirmed item → authored doc + nav registration + build check |
| `audit` | `./references/audit.md` | docs tree vs nav contract → orphan/broken-link report + fixes |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/docs.md` |
