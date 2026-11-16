# Adaptation reference — how foreign layouts become BMad-structured skills

The goal: whatever shape a source repo uses, the emitted result in
`.agents/skills/` follows the same conventions as natively installed BMad
skills — a folder named after the skill, a `SKILL.md` with proper frontmatter,
a `customize.toml` `[agent]` block for personas, and a `.srm-origin` provenance
marker.

## Registry schema (`{project-root}/_bmad/srm/sources.yaml`)

```yaml
repos:
  - name: BMAD-CYBERSEC                 # display name + help CSV module label
    url: https://github.com/...git      # clone URL — sync --clone-missing fetches
                                        # a missing repo from here; empty = hand-managed
    path: "{skills_repo_root}/BMAD-CYBERSEC"   # may use {skills_repo_root} / {project-root}
    prefix: bmad-bus                    # user-chosen at `add` time
    layout: grouped                     # grouped | flat
    git_pull: true
    skills_paths:                       # relative to repo root
      - src/core
      - src/cybersec-team
```

## Layouts

### grouped (BMad source module)

A skills path that *is* a module: contains `module.yaml` and/or `agents/` +
`workflows/`. Example: `BMAD-CYBERSEC/src/cybersec-team`.

Emits:

| Source | Target |
|---|---|
| `src/cybersec-team/` (whole dir) | `<prefix>-cybersec-team/` — verbatim copy + generated router `SKILL.md` |
| `src/cybersec-team/agents/<id>.md` | `<prefix>-cybersec-team-<id>/SKILL.md` (agent body becomes skill body) + `customize.toml` |
| `src/cybersec-team/workflows/<w>/` | `<prefix>-cybersec-team-<w>/SKILL.md` pointing into the router copy |

Agent conversion details:

- `name` frontmatter ← target skill name (`<prefix>-<source>-<id>`)
- `description` ← `.agent.yaml` `agent.metadata.description`, else `.md`
  frontmatter `description`, else title
- `customize.toml` `[agent]` ← `code` (agent id), `name` (persona — parsed from
  the `<agent name="...">` attribute in the .md, else metadata), `title`,
  `icon`, `description` from `.agent.yaml` `agent.metadata`
- A trailing note tells the skill where sibling resources live
  (`../<router>/workflows/`, `tasks/`, `templates/`)

Router SKILL.md lists every agent and workflow emitted, plus a caveat that
agents may expect `{project-root}/_bmad/<module>/config.yaml` at runtime.

### flat (dir of SKILL.md folders)

A skills path whose children each contain `SKILL.md`. Examples: `hr-skills`
→ `skills/`, `wondelai/skills` → `.agents/skills/`, `Finance-Guru` →
`.claude/skills/`.

Each child → `<prefix>-<child-dir-name>/` verbatim copy with:

- frontmatter `name:` rewritten to the target folder name
- `description:` synthesized from the first body line if absent

### `.claude` path (Claude plugin layout)

Only applies when `.claude` itself is a declared skills path (Finance-Guru
style). Emits `.claude/skills/*` as flat skills plus loose personas from
`.claude/agents/*.md` and `.claude/commands/**/agents/*.md` as
`<prefix>-<stem>` skills — file content as skill body, frontmatter
synthesized.

A `.claude` dir found elsewhere in a repo (e.g. a BMad repo's compiled
command artifacts under `.claude/commands/bmad/...`) is **not** scanned —
declared skills paths are the boundary of what gets mapped.

### Workflow skips

Dirs under `workflows/` starting with `_` (e.g. `_shared`) are shared
resource folders, not workflows — skipped.

### Windows symlink checkouts

Some repos (wondelai `skills`) publish `.agents/skills/<name>` as git
symlinks; a Windows checkout materializes them as small text files containing
the target path. The script detects these (`is_file`, <400 bytes, content is a
relative path that resolves to a real dir) and dereferences them — so listing
`.agents/skills` still reaches the real skill folders at repo root.

## Collision & prune safety

- Target folder exists **without** `.srm-origin` → skipped, reported as a
  collision. Foreign skills are never touched.
- `.srm-origin` records `{repo, source, commit, synced_at}` — drives `status`
  (synced commit vs `git rev-parse HEAD`) and staleness (repo unregistered or
  source path gone → reported; deleted only via explicit `--prune` or
  `remove --delete-skills` after user confirmation).

## Help CSV

After each repo syncs, its block in `{project-root}/_bmad/module-help.csv` is
regenerated (rows where `module` == repo name are dropped and rewritten): one
`_meta` row plus one row per emitted skill. Imported capabilities therefore
show up in `bmad-help` grouped under the source repo's name.
