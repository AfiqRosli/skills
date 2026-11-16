---
name: srm-sync
description: Syncs external skill repos into the project as prefixed, BMad-structured skills. Use when the user wants to 'sync skills', 'add an external repo', 'map a skill repo', 'list imported sources', or 'remove a mapped repo'.
---

# Skills Repo Manager — Sync

## Overview

Maps external skill repositories into `.agents/skills/` as `<prefix>-*` skills, adapted to BMad conventions. The registry lives at `{project-root}/_bmad/srm/sources.yaml` — each repo declares its path, layout, skills paths, and the **prefix** the user chose at registration.

**Hard rules**

- Never modify a source repo. The only operations performed on sources are `git clone` (first fetch into `skills_repo_root`, via the `clone` command or `sync --clone-missing`) and `git pull --ff-only`, the latter only when both the repo entry and the module's `git_pull` config allow it.
- Never overwrite a skill folder that lacks a `.srm-origin` marker — those are foreign/hand-installed; skip and report.
- Every emitted skill gets a `.srm-origin` marker (repo, source path, commit, timestamp) — this is what makes pruning safe.
- Prefixes come from the user, never guessed. During `add`, ask for the prefix unless the invocation already supplied one.

## Resolution rules

- Bare paths and `{skill-root}` (e.g. `scripts/sync.py`, `{skill-root}/references/adaptation.md`) resolve from this skill's installed directory — not the project directory.
- `{project-root}` → the project working directory.

## On Activation

Resolve `{project-root}` to the actual project root before running anything. All paths below are real filesystem paths.

Script: `scripts/sync.py` (run with `python`). Common flags: `--config-root {project-root}`, `--registry {project-root}/_bmad/srm/sources.yaml`, `--skills-dir {project-root}/.agents/skills` — all three default to the correct values when `--config-root` is the project root, so usually `python scripts/sync.py <command> --config-root "{project-root}"` suffices.

If `{project-root}/_bmad/srm/sources.yaml` does not exist, the module isn't set up — tell the user to run `srm-setup` first, then stop.

Route on the user's intent:

| Intent | Action |
|---|---|
| "sync", "update skills", "refresh", no args | **sync** |
| "add", "register", "map", a repo path | **add** flow |
| "remove", "unregister" + name | **remove** |
| "list", "what's registered" | **list** |
| "missing", "not cloned", "what isn't fetched" | **missing** |
| "status", "out of date", "stale" | **status** |

## Actions

### sync

```bash
python scripts/sync.py sync --config-root "{project-root}"
```

Options: `--repo <name>` (one repo only), `--no-pull` (skip git pull), `--clone-missing` (clone registered repos that aren't checked out yet, via each entry's registry `url`), `--prune` (delete stale skills — **only after the user confirms the stale list**).

For each repo: pulls (if enabled), resolves each `skills_paths` entry, adapts and copies skills, refreshes that repo's help-CSV block in `{project-root}/_bmad/module-help.csv`, then scans for stale `.srm-origin` skills.

Report the JSON result plainly: skills mapped (with counts per repo), skipped collisions, warnings, stale list. If `stale` is non-empty, show it and ask whether to re-run with `--prune` — do not prune uninvited.

If `missing` is non-empty, those repos are registered but not cloned locally — common on a fresh workspace right after `srm-setup` seeds the registry. Show the list (name, expected path, url) and offer to re-run with `--clone-missing` to fetch them all, or `sync --repo <name> --clone-missing` for one — do not clone uninvited. Entries with `reason: "clone failed"` already failed this run — show their `error` and its fix (auth, bad URL, blocked target) instead of re-offering the same flag. Entries with an empty `url` can't be fetched; the user must clone those by hand to the registered `path` (or fix the entry). A repo row carrying `path_repointed` means its registry `path` was corrected to the clone location — tell the user. A bare `clone --url <url>` also fetches a repo but only that: follow with `sync --repo <name>` to map it, and repoint the entry's `path` first if the clone landed somewhere other than the registered location.

### add

0. **If the user gave a remote URL** (`https://github.com/<owner>/<repo>` or `git@host:<owner>/<repo>`) instead of a local path, clone it first:

```bash
python scripts/sync.py clone --config-root "{project-root}" --url "<url>"
```

This clones into `{skills_repo_root}/<owner>/<repo>` and returns `path` (registry form), `resolved` (local path), and `name` (suggested repo name). `status: "exists"` means the repo is already cloned there — reuse the returned path, don't re-clone. `status: "error"` (unrecognized URL, `skills_repo_root` unset, clone failure, or a non-git dir blocking the target) — show the message and stop.
1. Run `python scripts/sync.py detect --path "<repo-path>"` — prints suggested layout, candidate skills paths, grouped sources, and persona-file count. After a `clone`, pass the returned `resolved` path.
2. Present the detection result and **ask the user for the prefix** to prepend (e.g. `bmad-bus`) — skip the question if the invocation already supplied one. Also confirm/correct the suggested layout and skills paths — the user knows the repo.
3. Register:

```bash
python scripts/sync.py add --config-root "{project-root}" --name "<repo-name>" --path "<abs-or-{skills_repo_root}-relative path>" --prefix "<prefix>" --layout "<flat|grouped>" --skills-paths "<comma,separated,paths>" [--url "<git-url>"] [--no-pull]
```

   If the repo was cloned in step 0, pass the same URL to `--url` so the registry records its origin, and use the clone output's `path`/`name` values.
4. Offer to run `sync --repo <name>` immediately.

Repo `path` values may use the literal `{skills_repo_root}` token — resolved from `srm.skills_repo_root` in `{project-root}/_bmad/config.yaml`.

### remove

```bash
python scripts/sync.py remove --config-root "{project-root}" --name "<repo-name>" [--delete-skills]
```

Without `--delete-skills`, only unregisters the repo — its `bmad-*`-style skills then show as stale on the next sync. With it, deletes every skill carrying that repo's `.srm-origin` marker immediately. **Always confirm with the user before passing `--delete-skills`.**

### list

```bash
python scripts/sync.py list --config-root "{project-root}"
```

Present the registry as a table: name, prefix, layout, skills paths, git_pull.

### missing

```bash
python scripts/sync.py missing --config-root "{project-root}"
```

Read-only clone-status check — emits `cloned`/`missing` lists plus counts, no pulls and no writes. `srm-setup` runs this to report seeded-source status; it also answers "what isn't fetched yet" directly.

### status

```bash
python scripts/sync.py status --config-root "{project-root}"
```

Compares each mapped skill's `.srm-origin` commit against the repo's current HEAD: `current`, `behind`, or `unknown` (not a git repo). If anything is `behind`, suggest `sync`.

## What the script does (reference)

Layout handling:

- **grouped** — a skills path that is itself a BMad module (`module.yaml`, `agents/`, `workflows/`). The whole dir is copied to `.agents/skills/<prefix>-<source>/` plus a generated router `SKILL.md`; each `agents/<id>.md` becomes `<prefix>-<source>-<id>/` (agent body as SKILL.md, `.agent.yaml` metadata as `customize.toml`); each `workflows/<w>/` becomes `<prefix>-<source>-<w>/` pointing into the router folder.
- **flat** — a dir of `*/SKILL.md`; each is copied to `<prefix>-<name>/` with frontmatter `name:` rewritten and a missing `description:` synthesized.
- **`.claude` path** — only when `.claude` itself is a declared skills path: `.claude/skills/*` are flat-mapped, and loose personas under `.claude/agents/` and `.claude/commands/**/agents/` are wrapped as `<prefix>-<stem>` skills. A `.claude` dir elsewhere in a repo (e.g. a BMad repo's compiled commands) is ignored — declared skills paths are the boundary.
- Windows symlink checkouts (a "dir" that is actually a small file containing a relative path) are dereferenced against the repo root.

Full adaptation details: `references/adaptation.md`.
