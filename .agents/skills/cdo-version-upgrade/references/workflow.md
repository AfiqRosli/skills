# Project Version Upgrade Workflow

**Goal:** Migrate non-done stories from the current release to a new release — renumber epics and stories, migrate story spec files, archive old release artifacts, and verify consistency.

**Sprint boundary ≠ deploy boundary:** this workflow runs ONLY when the user starts a new sprint — it is never a side effect of a production deploy. Mid-sprint deploys tag real dates and record `sprint` on their `release-train.json` entries; they leave all sprint artifacts untouched. If the user hasn't asked for a new sprint, don't run this.

**Your Role:** You are a release engineer supervising a scripted partition + renumber. `scripts/` owns the mechanics — your judgment is the confirmation gate, the epic order, and done-vs-spec reclassification. Everything below is one scripted partition: renumber compactly, trace with `was`-chains, archive don't delete.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve:

- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `implementation_artifacts` (default `_bmad-output/implementation-artifacts`)
- `planning_artifacts` (default `_bmad-output/planning-artifacts`)
- `release_train` (default `{project-root}/release-train.json`; a `release_train`/`release_train_file` key in bmm config overrides)
- `date` = current date
- Always respond in `{communication_language}`

`{Channel}` = the release-train name (`release-train.json` `current.name`, e.g. `Beta`); sprint IDs are `{Channel}-{version}`.

### Invocation modes

**Interactive (default):** run the three scripts in EXECUTION order; present the single confirmation gate between resolve and apply.

**Headless (`-H` / `--yes` supplied by the caller):** the gate is pre-answered. Requires the caller to supply `--new-version {sprint-id}` explicitly — a headless run never invents the target. Optional `--epic-order "2,1,9"` (default: preserve existing) and `--reclassify` (JSON `{key: status}` for done-vs-spec overrides). Chain the scripts, collect their JSON, emit the minimal result object (versions, counts, report). Without `--new-version` + `--yes`, return `{"status": "blocked", "reason": "sprint migration requires an explicit new-version and confirmation"}` — never prompt a pipeline.

---

## EXECUTION

<workflow>

<step n="1" goal="Resolve + pre-flight + confirm — the single gate">
<action>Run `uv run scripts/resolve-upgrade.py --project-root {project-root}` (pass `--new-version`/`--epic-order` when the caller supplied them). It emits the plan JSON: the version pair (old = newest version with all three artifacts, never blindly `release-train.current`), skew case, deploys shipped under the old sprint, the terminal/non-terminal partition, spec-file presence, pre-flight `errors`/`warnings`, and `status_mismatch` entries.</action>
<action>If `errors` is non-empty, report them verbatim and stop — do not proceed to mutation.</action>
<action>Judgment — for each `status_mismatch` (sprint says `done`, spec `Status:` disagrees): search the codebase for the implementation. No implementation found → add `"reclassify": {"{key}": "{spec-status}"}` to the plan and flag it. Implementation found → stays done.</action>
<action>Present ONE confirmation covering both decisions (skip under headless — inputs were supplied):</action>

```
Version Bump Plan:
  Old version (artifacts): {old_version}
  New version:             {new_version}
  Version skew:            {none | catch-up to {new_version} | mid-sprint deploy — new version confirmed}
  Deploys shipped under {old_version}: {deploy tags, or "none"}

  Terminal stories staying archived: {n} ({keys})
  Non-done stories migrating:        {n}
  Spec files to migrate:             {n} ({keys})
  Renumbering:                       {old->new key map}

  Epic order: [preserve existing | user-provided order]
  (Bugs & Enhancement always lands last — the fixed catch-all position
   sprint tooling assumes)

Proceed? (y/n)
```

<check if="user declines"><action>Abort the workflow.</action></check>
<action>Save the (possibly edited) plan JSON — `partition-renumber.py` consumes it.</action>
</step>

<step n="2" goal="Apply the transform">
<action>Run `uv run scripts/partition-renumber.py --plan {plan-file} --apply` (or `--dry-run` first for a write-nothing preview — the safe headless entry point). The script:</action>

- Creates `{new_spec_folder}`, generates `epics-beta-{new_version}.md` (epics in confirmed order, `(was X.Y in {old})` chains, verbatim story bodies) and `sprint-status-{new_version}.yaml` (terminal lines dropped, `# was N.M in {old}` on every migrated line)
- Migrates each spec file copy-**verify**-delete — never delete-then-recreate
- Archives the old epics + sprint yaml through `.new` siblings: write, verify parse, then rename over the original — a mid-write failure never truncates the only copy of terminal-story content
- Leaves `release-train.json` untouched — the new sprint's first deploy records its own `sprint` via `cdo-version-change-for-production`

<check if="script reports errors"><action>Report verbatim; the script already protected originals — inspect and rerun after fixing the named input.</action></check>
</step>

<step n="3" goal="Verify and report">
<action>Run `uv run scripts/verify-migration.py --old-version {old} --new-version {new} --project-root {project-root}` — emits the eight step-checks as `{check, pass, details}` JSON. Any failure: report verbatim, fix, re-verify.</action>
<action>Report:</action>

```
Version Bump Complete: {old_version} -> {new_version}

New:  {new_epics_file} ({epics} epics, {stories} stories)
      {new_sprint_status}
      {new_spec_folder}/ ({specs} spec files)
Old:  {old_epics_file} ({terminal} terminal stories retained)
      {old_sprint_status}
      {old_spec_folder}/ (terminal spec files only)
Reclassified from done: {n}
Flags: {semantic references now pointing at renumbered/archived stories — bodies preserved verbatim}
```

<action>Under headless, return instead `{"status", "old_version", "new_version", "counts", "reclassified", "flags", "report"}` with every assumption logged (chosen version, preserved/supplied epic order, reclassifications).</action>
<action>The migrated tree is left uncommitted by design — a calling pipeline may hand it to `cdo-git-quick-push` as the next leg.</action>
</step>

</workflow>

---

## JUDGMENT RULES (the parts scripts can't own)

- **Migrated stories keep their status verbatim** — a `review` story stays `review`.
- **Story bodies are verbatim.** A kept story referencing a renumbered or archived story number is acceptable — the was-chain disambiguates. Flag semantic oddities in the report; never silently edit bodies.
- **Done-vs-spec disagreement is a judgment call** — search the codebase before reclassifying; the script only applies what the plan records.
- **Epic priority comes from the user** — the single gate covers version pair + epic order; Bugs & Enhancement lands last because sprint tooling treats it as the fixed catch-all position.

## FILE NAMING CONVENTIONS

| Artifact | Pattern | Example |
| -------- | ------- | ------- |
| Epics file | `epics-beta-{version}.md` | `epics-beta-Beta-2026.09.14.2.md` |
| Sprint status | `sprint-status-{version}.yaml` | `sprint-status-Beta-2026.09.14.2.yaml` |
| Spec folder | `{version}/` | `Beta-2026.09.14.2/` |
| Spec file | `{epic}-{story}-{slug}.md` | `11-4-polar-sdk-version-pinning.md` |

`epics-beta-` is a permanent protocol literal shared with sibling skills — it is NOT derived from `{Channel}` (the channel already lives inside `{version}`).

## TROUBLESHOOTING

- **Script emits `errors`** -> the message names the input to fix (missing artifact, unknown status, target collision, uncovered epic). Fix and rerun — `--dry-run` writes nothing.
- **Release train ahead of artifacts** -> `resolve-upgrade` reports the skew case: `catch-up` (a new sprint was already bumped elsewhere — plan carries that sprint id) or `mid-sprint-deploy` (`current.sprint` names the old sprint — supply `--new-version`). `old_version` is always the newest version WITH artifacts.
- **Rerun after partial apply** -> archives use write-verify-rename, so an interrupted run leaves originals intact; spec deletes happen only after verified copies.
- **Done-vs-spec disagreement** -> resolve flags it in `status_mismatch`; decide from codebase evidence, record in `reclassify`.
