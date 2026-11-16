# Capability: produce — confirmed item → authored, reachable doc

A doc that isn't reachable isn't delivered. Produce owns three things: the page, its registration in whatever makes it visible, and proof.

## 0. Gate the item

Find `DOC{key}`'s line in `backlogs/docs.md`. Only `- [x]` (confirmed) items produce — `- [ ]` unaligned or `- [A]` draft stops with the marker as the reason (the pool boundary; alignment/Operator review is the way in, not a workaround here). `deps:` keys that aren't `done` stop for the same reason. In `-H` this gate emits the stop as a JSON error object, no prompting.

## 1. Load the contract

Read `{orchestration_dir}/docs-profile.yaml`. Missing → run `detect` first. Every step below keys off the profile:

- `docs_root` — where the file lands
- `nav_kind` — what visibility registration means here
- `auto_zones` — dirs needing no nav edit
- `build_command` — the verification step

## 2. Author the page

Place it at `{docs_root}/{item.target}/` — the item's shaped target, refined if it's stale or `?`. **If a page already exists at the target, update it in place** — produce edits the living doc rather than minting a duplicate; the nav entry may already exist (check before adding one). Follow the framework's conventions: VitePress/CommonMark frontmatter for `vitepress`, MkDocs nav-style pages for `mkdocs`, content collections for `nuxt-content`. Match neighboring pages' frontmatter and structure — the docs profile tells you where; the neighbors tell you how. Authored prose follows `{document_output_language}` when the module config sets it.

When `cdo-documentation` (the project docs workflow) is installed, invoke it — it owns document craft: metadata, cross-references, quality gates. `bmad-agent-tech-writer` is the drafting delegate when present. Owner skills are invoked, never re-implemented; when none are installed, write it directly to the same standard.

## 3. Register visibility — by `nav_kind`

| nav_kind | Registration |
|---|---|
| `config` (vitepress, docusaurus+sidebars, starlight) | Add the entry to the file `nav_config` names — sidebar group, nav item, or `sidebars.*` entry, matching existing structure. **Exception:** if the page lands inside an `auto_zone`, the config already generates its nav — no edit, and say so. |
| `yaml-nav` (mkdocs) | Add the `nav:` entry in `nav_config`. |
| `gitbook-summary` | Add the link in `SUMMARY.md`. |
| `filesystem` / `none` | File presence is the contract. Cross-link from the section index/README if one exists — orphaned-in-spirit pages are still a defect. |

This is the step that closes the "folder exists, VitePress UI doesn't show it" gap: **no produce completes with an unregistered page.** If `nav_kind` is `config` and you cannot find where to register it, that's a produce failure — report it, don't ship a hidden page.

## 4. Verify with the stack's own build

Run `build_command` from the profile (e.g. `bun run docs:build`). The build is the visibility proof — dead links and nav config errors surface there. A failing build means the doc isn't delivered: fix what the build reports, or record `blocked` with the build output as findings.

No `build_command` recorded (no framework, or no script detected) → record `verification: skipped({reason})` honestly rather than claiming a check you didn't run.

## Devlog

When invoked under `cdo-batch`, the caller hands you a devlog dir — journal the page's decision entries to it as you work:

```bash
uv run {project-root}/.agents/skills/cdo-batch/scripts/devlog.py append {dir} --title "..." --step 3 --of 8
```

Placement/structure choices get the same decision-entry shape as code changes — Context, `**File:**` + `**Goal:**`/`**Gap:**`, literal Before/After fences carrying the doc delta or nav registration, Why this placement, Alternatives considered. Contract: `cdo-batch/references/devlog-conventions.md`. Standalone invocations (no devlog dir passed) skip this — the ledger findings remain the record.

## Output

`{key, artifact: {path under docs_root}, visibility: {how it's reachable — nav entry, auto_zone, filesystem}, build: pass|fail|skipped}`.
