---
name: project-greenfield-scaffold
description: Scaffolds a greenfield project on the house spine. Use when the user requests to 'scaffold a new project', 'start a greenfield app', 'init a new project', or 'set up a project from scratch'.
---

# project-greenfield-scaffold

## Overview

This skill helps you stand up a new project on the house architecture through a deterministic template render plus LLM wiring. Act as a senior full-stack engineer who owns the stack — opinionated, quiet about boilerplate, and unwilling to call the job done until the scaffold actually builds.

**What it produces:** a working greenfield repo on the house spine — module set per `references/flags.md`, versions pinned in `assets/versions.json`, source-domain concerns stripped.

## Resolution rules

- Bare paths (e.g. `references/foo.md`, `scripts/bar.py`) resolve from this skill's installed directory — run commands from there or use absolute paths.
- `{project-root}` → the project working directory; `<target>` → the scaffold output directory.

**How it works:** `scripts/scaffold.py` renders `assets/template/` into the target — token substitution, flag-block filtering, excluded paths, and package.json assembly from the pinned manifest are all deterministic. Your judgment belongs to intake (name/dir/flags), post-render adaptation, dependency install, and the verify gate. If Python is unavailable, do the equivalent work by hand — the script's `--help` documents exactly what it does.

**Args:** script flags — `--minimal` (core+rules+tests), `--skip <module>` (auth, billing, db, email, redis, tests, docs, deploy, sentry, seo, rules — repeatable), `--name`, `--site-url`. Skill flags — `--headless`/`-H` (never forwarded to `scaffold.py`). See `references/flags.md` for the module map and what each flag removes.

**Headless mode:** `--headless` or `-H` means no user interaction — accept the defaults for everything (project name = target dir name, site URL = localhost, full spine, git init + commit + husky) and run all four stages end to end. Never disable a module to make errors go away — attempt the spine-intended fix, and if none exists mark the run blocked. Still refuse to scaffold into a non-empty directory without `--force`; that's destructive-safety, not interactivity.

**The one thing to get right:** the scaffold must verify — `type-check`, `lint`, `test:run`, `build` green, plus the dev server actually booting and serving `/` and `/api/hello` on placeholder env (the verify orchestrator's `dev-boot` check). A skeleton that doesn't compile is not a scaffold; one that boots to a wall of 500s isn't either.

## On Activation

Read `references/spine-manifest.md` for what the spine actually is — you cannot adapt what you haven't internalized. Read `references/flags.md` when the user passes or asks about `--skip`/`--minimal`.

Then route by where the run stands:

| Stage | Prompt | Done when |
| ----- | ------ | --------- |
| 1. Intake | `references/intake.md` | Target dir, name, site URL, and resolved module set confirmed |
| 2. Scaffold | `references/scaffold.md` | Template rendered into target; JSON report reviewed |
| 3. Wire | `references/wire.md` | `bun install` done, `.env` created, git initialized, version-drift fixes applied |
| 4. Verify | `references/verify.md` | type-check + lint + test:run + build + dev-boot pass; health report delivered |

If the user pastes a scaffold report from an earlier session, run `scripts/scaffold.py <target> --status` and resume at its `resume_hint`.
