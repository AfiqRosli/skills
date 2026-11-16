# Capability: produce — author a curriculum module

Confirmed curriculum item in, course module out — the internal learning
platform's content, published under `docs/academy/`.

## Layout

```
docs/academy/
  index.md                        # platform landing (seeded by setup)
  catalog.yaml                    # tracks → courses → modules coverage map
  {track}/
    index.md                      # track overview — the path, who it's for
    {course}/
      index.md                    # course overview — subject, outcomes, module index
      {NN}-{concept-id}.md        # a module — one teachable unit
```

A confirmed `C{n}` item names `track`, `course`, `level`, `concept-id`.
Produce authors **one module** — incremental: an existing course gains a
file, it is never rewritten wholesale.

## Produce

1. **Ensure the spine exists.** If `{track}/index.md` is missing, create it —
   one paragraph on the track's arc (fundamentals → advanced) and a course
   list. If `{course}/index.md` is missing, create it — what the subject is,
   what a learner can do at the end, and the module index grouped by level
   band. If both exist, update the course index's module list only.

2. **Author the module** — `{NN}-{concept-id}.md`, `NN` = next sequence
   number in the course dir:

   ```md
   ---
   level: intermediate
   concepts: [ssr-rendering]
   ---

   # {module title}

   ## Why this exists
   (the stories that demanded it — cite them; this is the "why learn this")

   ## The mental model
   (what it IS, when you need it — the correct intuition, not the API tour)

   ## How it shows up in our codebase
   (the real shape it takes in this project — actual files, actual shipped code)

   ## Exercises
   (2–4 tasks that exercise the knowledge — checkable, not trivia)
   ```

3. **Register it:**

   ```bash
   uv run ./scripts/catalog.py --academy-dir "{academy}" add \
     --track {t} --course {c} --module-id {module-id} \
     --title "{title}" --level {level} --source-story {key} \
     --concepts {concept-id},{other-concepts-covered}
   ```

   The `--concepts` list records which knowledge-graph nodes the module
   actually teaches — the gap-check reads it to count coverage even when
   the module-id differs from the concept-id.

   The module enters the coverage map — the next gap-check counts it.

## Style

- Teach for the org's actual work — cite source stories and real files as
  the "why this exists"; the learner should recognize the codebase in every
  example.
- **Level honesty** — `fundamentals` assumes only the floor and builds up;
  `intermediate` can lean on fundamentals modules; `advanced` assumes the
  course's earlier bands. Don't pitch fundamentals at experts or vice versa.
- A module is *self-contained but linked* — readable alone, but honest about
  which earlier modules it leans on.
- Content shaped like the org, not like a textbook — internal platform
  means internal voice.

## Devlog

When invoked under `cdo-batch`, the caller hands you a devlog dir — journal the module's decision entries to it as you work:

```bash
uv run {project-root}/.agents/skills/cdo-batch/scripts/devlog.py append {dir} --title "..." --step 3 --of 8
```

Curriculum choices get the same decision-entry shape as code changes — Context, `**File:**` + `**Goal:**`/`**Gap:**`, literal Before/After fences carrying module content deltas, Why this level/scope, Alternatives considered. Contract: `cdo-batch/references/devlog-conventions.md`. Standalone invocations (no devlog dir passed) skip this — the ledger findings remain the record.

## Output

`{key, track, course, module_id, module_path}` + catalog entry registered.
