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
- `<target>` → the scaffold output directory.

## Run contract

**How it works:** `scripts/scaffold.py` renders `assets/template/` into the target — token substitution, flag-block filtering, excluded paths, and package.json assembly from the pinned manifest are all deterministic. Your judgment belongs to intake (name/dir/flags), post-render adaptation, dependency install, and the verify gate. If Python is unavailable, do the equivalent work by hand — the script's `--help` documents exactly what it does. `python3` in these docs means your Python 3 — on Windows that's typically `python`/`py` (a `python3` alias may be the Microsoft Store shim), and cmd/PowerShell need the `--record` JSON double-quoted.

**Args:** script flags — `--minimal` (core+rules+tests), `--skip <module>` (auth, billing, db, email, redis, tests, docs, deploy, sentry, seo, rules — repeatable), `--name`, `--site-url`. Skill flags — `--headless`/`-H` (never forwarded to `scaffold.py`). See `references/flags.md` for the module map and what each flag removes.

**Headless mode:** `--headless`/`-H` — no user interaction: accept every default (project name = target dir name, site URL = localhost, full spine, git init + commit + husky) and run all four stages end to end. Record the accepted defaults once via `scripts/scaffold.py <target> --record '{"assumptions": ["…"]}'` so the run's audit trail shows defaulted-vs-supplied. Never disable a module to make errors go away — attempt the spine-intended fix; if none exists, `--record '{"run_status": "blocked", "reason": "…"}'` instead. Still refuse to scaffold into a non-empty directory without `--force`; that's destructive-safety, not interactivity. Return JSON to the caller: `{ "status": "complete" | "blocked", "target": "<target>", "report": "<target>/.scaffold-report.json", "reason?": "<one line, blocked only>" }` — the prose health report stays the human layer.

**The one thing to get right:** the scaffold must verify — `type-check`, `lint`, `test:run`, `build` green, plus the dev server actually booting and serving `/` and `/api/hello` on placeholder env (the verify orchestrator's `dev-boot` check). A skeleton that doesn't compile is not a scaffold; one that boots to a wall of 500s isn't either.

## On Activation

First check for an existing run: if the working or target directory holds `.scaffold-report.json`, run `scripts/scaffold.py <target> --status` and resume at its `resume_hint` — a terminal hint (`run complete`, `blocked`) needs nothing else here. If the user pastes a report from elsewhere, `--record` it into `<target>/.scaffold-report.json` first — the script filters a full report down to the keys it classifies on — then `--status`. The script is the only classifier.

Read `references/spine-manifest.md` for what the spine actually is — you cannot adapt what you haven't internalized. Read `references/flags.md` when the user passes or asks about `--skip`/`--minimal`. Read `references/auth-infra.md` when the user asks for admin/audit or abuse protection (Better Auth dash + sentinel porting spec; candidate flag, not yet a module). Read `references/build-hangs.md` when a build/test/push hangs after printing success or a build gate needs designing (exit-hang rules + stamp-passed pre-push pattern).

Then route by where the run stands:

| Stage | Prompt | Done when |
| ----- | ------ | --------- |
| 1. Intake | `references/intake.md` | Target dir, name, site URL, and resolved module set confirmed |
| 2. Scaffold | `references/scaffold.md` | Template rendered into target; JSON report reviewed |
| 3. Wire | `references/wire.md` | `bun install` done, `.env` created, git initialized, version-drift fixes applied |
| 4. Verify | `references/verify.md` | type-check + lint + test:run + build + dev-boot pass; health report delivered |

