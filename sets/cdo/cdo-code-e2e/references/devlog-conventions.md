# Dev Log Conventions

The dev log is both the human-readable audit trail and the machine-readable pipeline state. One folder per story per release.

## Path Derivation

`{project-root}/docs/orchestration/devlog/<Channel>/<date>/<story-key>/`

- `<Channel>` — the release name up to the first `-` (e.g. `Beta-2026.09.14.2` → `Beta`)
- `<date>` — the remainder of the release name with `.` → `-` for the date segments, preserving any sub-release suffix (e.g. `2026.09.14.2` → `2026-09-14.2`)
- `<story-key>` — the story key as it appears in sprint yaml (e.g. `01-07-geo-markdown-twins-llms-txt-update`)

Each story folder contains:

- `index.md` — the dev log: frontmatter pipeline state + chronological change journal
- `retrospective.md` — written at step 10, from `./assets/retro-template.md`

## index.md — State + Journal

Create and maintain it through `./scripts/devlog.py` — `init` scaffolds the folder from `./assets/dev-log-template.md`, `set`/`get` update and read step status, `append` adds journal entries, `snapshot`/`snapshot --check` store and compare a git-status hash of the post-dev change baseline (ship's story-scope routing uses it), `metrics` mines the journal + prior retros for the step-10 retro. Hand-editing frontmatter is the fallback when Python is unavailable.

The `pipeline:` block in frontmatter is the resume contract — update a step's value to `done` as it completes; use `in-progress`, `skipped`, or `blocked` where fitting. A resuming session reads this block first.

Journal entries are append-only, newest at the bottom. **Audience: a trainee who has never seen this codebase.** The dev log is a teaching artifact — each entry should let a new engineer understand what changed, why it was needed, why this approach works, and what they could have done differently. Explain the mechanism, not just the diff.

Each meaningful code change gets a structured **decision entry** — one per task or logical change (not per file). A prose summary alone is not a decision entry: the `**Before**`/`**After**` blocks carry the literal code from the actual diff — real snippets, never paraphrases, pseudocode, or descriptions of what changed. Snippets stay diff-relevant — the changed lines plus enough surrounding context to be legible; never whole files:

````markdown
#### <concise change title>

**Context:** the problem or goal this addresses — what was broken, missing, or needed. A trainee reading only this journal should understand why the change exists at all.

**File:** `path/to/file.ts` (or `new file`)

**Goal:** the intent of this code block — what it exists to achieve (e.g. "the constant must be module-level and provably immutable"). Written before the diff so the reader knows what "correct" looks like; without it the Before/After is mechanism without purpose.

**Gap:** what the **Before** code lacks relative to the goal — the concrete distance the **After** closes (e.g. "mutable `var` invites reassignment; the name isn't searchable"). For `new file` entries, name the capability that didn't exist before — "no helper could encrypt per-field under a scoped key".

**Before**

```ts
var e = 2.718
```

**After**

```ts
const EULER = 2.718
```

**Why this approach:** how the change solves the problem — the mechanism, not a restatement of the diff. Name the convention, pattern, or constraint that drove it (link the rule file where one applies, e.g. `.devin/rules/code-style-guide-naming-conventions.md`).
**Alternatives considered:** the genuine option space around this decision — see the flavors below.
**Watch out for:** gotchas, edge cases, or follow-ups a reader should know (e.g. "shared `loading` ref is used by two fetches — a second call would flicker state").
````

**Format contract (verified by `devlog.py lint`):**

- Entry titles are `####` (h4) — `## Journal` stays the page's only h1–h3 inside the journal, so VitePress' **On This Page** outline shows *Journal* alone. Never use `##`/`###` for entry titles or section headers inside the journal.
- **Every field label sits on its own line** — `**File:**`, `**Goal:**`, `**Gap:**`, `**Before**`, `**After**`, `**Context:**`, `**Why this approach:**`, `**Alternatives considered:**`, `**Watch out for:**`. Two labels sharing a line is a lint violation, not a style choice.
- **Every fenced block carries a language tag** (`ts`, `vue`, `json`, `diff`, `sql`, …) — bare ```` ``` ```` openings are violations.
- **Codeblock content is literal code** lifted from the real diff — diff-relevant lines plus legibility context, never paraphrases, pseudocode, or whole-file dumps.

- A logical change spanning several blocks or files repeats the `**File**`/`**Goal**`/`**Gap**`/`**Before**`/`**After**` group per block — every file the change touched gets its own group with real code.
- **Goal and Gap are required on every group** — they are what turns a code dump into a decision: Goal states intent, Gap states the distance. One line each; terse beats thorough.
- **New files** omit `**Before**` (Gap names the absent capability instead), and `**After**` expands rather than shrinks: show the file's essential blocks — the public API surface and the load-bearing implementation — one fenced block per logical piece, with a line naming what each piece is. A trainee should see what the module *is*, not just that it exists. Still selective, not a whole-file dump — pick the blocks that carry the design.
- **Coverage is verifiable:** every code file the development change touched must appear on a `**File:**` line (a casual mention elsewhere in the entry does not count) — `devlog.py coverage` checks the tally mechanically at step 4's coverage check and step 9's sweep. Docs/markdown/devlog artifacts don't count as code changes and aren't required.
- **Format is verifiable:** `devlog.py lint` checks the mechanics deterministically — heading depth, fence language tags, fields on own lines, File-group completeness, **bare `<word>` tokens outside fences/inline code** (a tag without a same-line `</tag>` close fails — paired markup like `<code v-pre>…</code>` is excused) — and `devlog.py sweep` bundles it at step 9. Fix violations before moving on; don't rationalize them.
- Pure deletions omit `**After**`.
- `**Alternatives considered**` is not a strawman list — record the genuine option space using whichever flavors apply:
  - *Rejected* — a real option that lost; say why it lost.
  - *Settled by convention* — a legitimate either-way (e.g. Composition vs Options API in Vue) where a project rule already picks the side; name the governing rule rather than pretending the choice was open.
  - *Future consideration* — an option that would win under a foreseeable change (a roadmap item, a schema revision, a scaling threshold); note what would trigger revisiting it.
  - `none — mechanical change` when no real choice existed.
- `**Alternatives considered**` and `**Watch out for**` are required only where a real choice or risk existed.
- Trivial formatting/mechanical edits may collapse to a one-line entry without snippets.

Gate outcomes, fix-loop iterations, and audit findings are also journal entries (no Before/After needed) — but write them the same way: the decision *and* the reasoning behind it, so a trainee learns the judgment, not just the outcome. The log should let someone reconstruct the entire run — and understand it — without the chat transcript.

## VitePress Integration

`docs/orchestration/devlog/` is a docs section nested under Engineering. On first use:

- Ensure `docs/orchestration/devlog/index.md` exists (create a minimal landing page if not)
- Ensure the section is registered in `{project-root}/docs/.vitepress/config.ts` sidebar — check before adding; registration is idempotent. The sidebar's `devlogSidebar()` helper scans the devlog tree at config-eval time, so new journals become navigable automatically — no per-story sidebar edits. Live reload during `docs:dev` is handled by `{project-root}/scripts/watch-devlog.mjs` (spawned by `{project-root}/scripts/dev-docs.mjs`): it watches the devlog tree and touches `config.ts` on change, so VitePress restarts and re-scans — no manual restart needed for sidebar updates. A stale `dist` build still needs `docs:build`; the review gate's publish check (step 9) covers that.
- Follow the `cdo-documentation` skill's link rules: absolute paths starting with `/`, `.md` extensions included, directory links point to `index.md`
- **Never write a bare `<word>` outside code fences** — VitePress compiles `.md` as Vue SFC, so placeholders like `<release>` or `<devlog_dir>` parse as unclosed elements and break `docs:build` with "Element is missing end tag". Wrap them in backticks (`<release>`) instead. Note the failure vector: `devlog.py append --text "..."` inside double quotes lets bash eat the backticks as command substitution, producing the bare token — prefer single-quoted `--text` or stdin for entries containing backticks.

Dev-log docs carry project frontmatter: `department: engineering`, `temporal_pattern: audit-trail`, `status: current-stable`.

## Sprint Yaml Write Rules

The sprint status file is hand-maintained with dense traceability comments. Intermediate transitions (`ready-for-dev`, `in-progress`, `review`) go through `./scripts/sprint-status.py set` — never hand-edit. When marking `done`:

- Preserve every existing comment byte-for-byte
- Append to the story's trailing comment: `DONE <YYYY-MM-DD>` plus a short outcome summary matching the established style (what shipped, notable fixes, test/lint status)
- Update `last_updated` if the field exists
- Never reformat, re-sort, or touch other entries

The story doc gets `Status: done` plus a Change Log line — same discipline: modify only the permitted sections.
