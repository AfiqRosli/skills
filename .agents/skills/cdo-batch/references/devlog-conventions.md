# Dev-Log Conventions (cdo-batch)

Vendored from cdo-code-e2e's devlog conventions — same contract, same helper
style. What differs is scope: cdo-code-e2e logs one pipeline's 13 steps; a
dispatch devlog logs the **org arc** — readiness → claim → produce →
verify → ship → extract → feed → release.

## Location & naming

```
docs/orchestration/devlog/<Channel>/<date>/<story-key>/
```

- `<Channel>` — first segment of the sprint release name (e.g. `Beta`), or
  `CDO` only when the repo has no sprint yaml at all.
- `<date>` — sprint stories: the release remainder with `.` → `-` for the
  first three segments (`Beta-2026.09.14.2` → `Beta/2026-09-14.2`).
  Non-sprint keys: the **current sprint's** date — devlogs follow the sprint
  cycle; a mid-sprint hotfix version bump never moves the folder.
  CDO-channel stories: the dispatch date `YYYY-MM-DD`.
- `<story-key>` — sprint keys get padded (`11-2-x` → `11-02-x`) for lexical
  sort; org keys (`CT1`, …) pass through unchanged.

`./scripts/devlog.py path --key {key} --project-root {root}` resolves all of
this: it checks the sprint-status yamls for the key first (a hit means the
produce leg's cdo-code-e2e devlog and the dispatch devlog share one folder),
else falls back to the newest sprint yaml's Channel/date, else
`CDO/<today>/<key>` as the last resort.

## What's in a devlog

| File | Written by |
|---|---|
| `index.md` | frontmatter `dispatch:` state block + `cdo:` meta; `## Journal` append-only body |
| `retrospective.md` | batch worker, at release — `./assets/retro-template.md` |
| `audit-*.md` | quality/security legs that produce findings docs |

On a sprint-derived path the folder is **shared**: cdo-code-e2e owns
`pipeline.steps` and its journal entries; the dispatch block and
dispatch-level entries ride the same `index.md`. `devlog.py attach` grafts
the `dispatch:`/`cdo:` frontmatter blocks onto an existing index without
touching `pipeline:`.

## The journal contract

Same as cdo-code-e2e's — `devlog.py lint` enforces it:

- Append-only `####` entries, newest at bottom. `## Journal` is the only
  outline heading — never h1–h3 inside it.
- Dispatch-leg entries get `--step N --of 8` so `metrics` can attribute
  durations.
- Every meaningful change gets a **decision entry**: `**Context**`,
  `**File:**` group(s) with `**Goal:**` + `**Gap:**` + `**Before**`/
  `**After**` in language-tagged fences, `**Why this approach:**`,
  `**Alternatives considered:**`, `**Watch out for:**`. One field per line.
- For non-code produce (specs, posts, courses, docs) the Before/After
  fences carry the artifact's literal content or spec delta — the contract
  is about *evidence in the log*, not code specifically.
- No bare `<word>` tokens or `{{` outside fences/inline code — VitePress
  compiles .md as Vue SFC and they break `docs:build`.
- Never log secret values. Lock names, session names, and verdicts are
  fine; `.env` contents are not.

## Commands

All run from the project root; `dir` is the devlog folder.

```bash
uv run .agents/skills/cdo-batch/scripts/devlog.py path --key {key} --project-root {root}
uv run .agents/skills/cdo-batch/scripts/devlog.py attach {dir} --story-key {key} --release {rel} \
    --session {session} --dept {dept} --backlog {backlog} --card {card-path}
uv run .agents/skills/cdo-batch/scripts/devlog.py set {dir} {leg} {status}        # --block dispatch (default)
uv run .agents/skills/cdo-batch/scripts/devlog.py append {dir} --title "..." --step {N} --of 8   # body via stdin
uv run .agents/skills/cdo-batch/scripts/devlog.py lint {dir}
uv run .agents/skills/cdo-batch/scripts/devlog.py coverage {dir} [--files ...]
uv run .agents/skills/cdo-batch/scripts/devlog.py sweep {dir}
```

`attach` is the handshake — call it once the claim succeeds; it's idempotent
and safe on both fresh and cdo-code-e2e-owned index.md files.

## What gets journaled, per leg

| Leg | Journal |
|---|---|
| readiness | gate result — ready (env requisitions satisfied) or the blocking gap |
| claim | lock acquired, session id, card path |
| produce | invoke → outcome; the producing dept appends its decision entries |
| verify | verdict + findings summary (quality's own journal lives in the ledger) |
| ship | lane, commit, deploy outcome |
| extract | academy extraction filed — manual leg, runs post-dispatch on Operator/Marshal command only |
| feed | content/doc backlog feed outcome |
| release | terminal status, lock released, review spawned — the close-out entry |

Blocked/killed/deferred stories journal the terminal reason and mark
remaining legs `skipped` — a failed dispatch still deserves a readable arc.
