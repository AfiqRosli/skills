# Analysis Report: C:\Core\Businesses\skills\sets\srm (srm-sync + srm-setup) — clone-missing changes

Generated: 2026-11-16T21:56:00+08:00 · Schema: 2

**Grade: Good**

> The clone-missing feature is well-placed and mirrors the stale/prune confirm-gate, but its clone-failure signal, silent registry-path rewrite, and the hand-rolled seeded-path check leave gaps a real run will hit.

The change earns its place almost everywhere: clone_into() is a clean extraction, --clone-missing is properly user-gated, and the seed url comment fix was overdue. The primary opportunity is disclosure — failed clones collapse into 'missing', a registry path rewrite happens silently, and srm-setup re-derives in prose what the script can already compute.

| Severity | Count |
| --- | --- |
| Critical | 0 |
| High | 0 |
| Medium | 8 |
| Low | 7 |

## Themes

### 1. Clone-flow results are under-disclosed and under-routed

- Root cause: --clone-missing produces three outcomes (cloned, failed, not-attempted) but the report collapses failed clones into the same `missing` list as never-tried ones, and the registry `path` rewrite on divergent targets is invisible. The offered single-repo alternative (`clone --url`) can neither fix a divergent registered path nor finish the job alone — it still needs a follow-up sync.
- Fix: Split the signal and disclose the mutation: give `missing` entries a reason/error field (or add `path_repointed` to the repo row), teach SKILL.md to show clone errors instead of re-offering the same flag, and route single-repo fetches through `sync --repo <name> --clone-missing` — or extend the `clone --url` clause with 'then sync --repo <name>'.
- Findings:
  - `enhancement-1` Add: distinguish 'not yet cloned' from 'clone failed' in the missing flow — `sets/srm/srm-sync/SKILL.md:51 + scripts/sync.py:588-594`
  - `enhancement-2` Add: surface the silent registry path rewrite --clone-missing performs — `sets/srm/srm-sync/SKILL.md:45-51 + scripts/sync.py:596-599`
  - `architecture-1` --clone-missing silently rewrites the registered path when it differs from the URL-derived location — `srm-sync/scripts/sync.py:587-600; srm-sync/SKILL.md:51`
  - `enhancement-3` Add: `clone --url` alternative for a single repo cannot fix a divergent registered path — `sets/srm/srm-sync/SKILL.md:51`
  - `architecture-4` Single-repo fetch guidance stops one step short of done — `srm-sync/SKILL.md:51`

### 2. The seeded-clone check is hand-rolled where a script already computes it

- Root cause: srm-setup instructs the model to parse sources.yaml, resolve nested `{skills_repo_root}`/`{project-root}` tokens, stat six paths, and count — deterministic work sync.py's `missing` array already performs. The paragraph also restates srm-sync's flag mechanics in the wrong file and is written only against the fresh-seed branch, missing the preserved-registry path.
- Fix: Emit the clone-status check from a read-only sync mode (e.g. `sync.py missing` or `sync --dry-run` emitting `{cloned, missing}` via module_vars/resolve), apply it to every registered entry rather than just seeds, and compress the srm-setup paragraph to one goal sentence.
- Findings:
  - `determinism-1` Prompt stats seeded repo paths and counts cloned sources by hand — `sets/srm/srm-setup/SKILL.md:66 ('Check which seeds are already cloned')`
  - `leanness-1` Seed-clone check paragraph restates srm-sync's mechanics — `sets/srm/srm-setup/SKILL.md:66`
  - `enhancement-5` Opportunity: 'stat each seeded path' doesn't cover the preserved-registry branch — `sets/srm/srm-setup/SKILL.md:62-66`

### 3. Schema-of-record text drifted from the new behavior

- Root cause: Two canonical descriptions still describe the pre-feature world: adaptation.md's registry schema calls `url` 'informational' while it is now the clone source, and SKILL.md's hard-rules line scopes `git clone` to 'the clone command' while sync --clone-missing also runs it.
- Fix: Update adaptation.md's url comment to match sources-seed.yaml ('clone URL — sync --clone-missing fetches a missing repo from here; empty = hand-managed checkout') and broaden the hard-rule parenthetical to 'via the clone command or sync --clone-missing'.
- Findings:
  - `architecture-2` adaptation.md registry schema still documents url as 'informational' — `srm-sync/references/adaptation.md:14`
  - `architecture-3` Hard-rules line still scopes git clone to 'the clone command' — `srm-sync/SKILL.md:14`

### 4. Author-specific seed registry has no customization surface

- Root cause: srm-setup hardcodes './assets/sources-seed.yaml' — the author's own repo picks — and neither srm skill ships a customize.toml, so an org wanting its own standard source list (now load-bearing on fresh workspaces) must fork.
- Fix: Opt srm-setup into customize.toml with `sources_seed_template = "assets/sources-seed.yaml"` under [workflow] and read `{workflow.sources_seed_template}` at seed time; the free `on_complete` scalar then also covers post-install hooks (e.g. auto `srm-sync --clone-missing`).
- Findings:
  - `customization-1` Author-specific seed registry hardcoded, not exposed as a template — `srm-setup/SKILL.md:62 → assets/sources-seed.yaml`
  - `customization-2` One-shot install ends with a fixed 'do not sync' boundary — on_complete candidate — `srm-setup/SKILL.md:64-66`

## Strengths

- clone_into() extraction is a clean deduplication — cmd_clone becomes a thin wrapper and cmd_sync reuses identical clone semantics.
- The confirm-gate is correctly mirrored: 'do not clone uninvited' matches the established 'do not prune uninvited' pattern, keeping the clone decision in user hands while the script stays pure plumbing.
- Seeded registry paths are pre-aligned to the canonical <skills_repo_root>/<owner>/<repo> convention, so the path-rewrite edge case never fires for the shipped six.
- missing[] entries carry name/path/url — enough for a model to act without re-deriving anything.

## Recommendations

1. Split clone outcomes in the report (reason on missing entries, path_repointed on repo rows) and teach the SKILL.md to show clone errors rather than re-offer the same flag (resolves: enhancement-1, enhancement-2, architecture-1)
2. Move the cloned/missing check into a read-only sync.py mode emitting compact JSON, cover registered (not just seeded) entries, and compress the srm-setup paragraph to a goal sentence (resolves: determinism-1, leanness-1, enhancement-5)
3. Fix the two drifted descriptions (adaptation.md url comment, hard-rule clone scope) and complete the single-repo guidance ('then sync --repo <name>' or route via --repo --clone-missing) (resolves: architecture-2, architecture-3, architecture-4, enhancement-3)
4. Add customize.toml to srm-setup exposing sources_seed_template (resolves: customization-1, customization-2)
5. Pre-existing debt worth a separate pass: bare-path conversion + '## Resolution rules' blocks in both SKILL.mds, and scope the add-flow 'always ask prefix' rule to only when none was supplied (resolves: architecture-5, architecture-6, enhancement-4)

## Experience

- **Fresh workspace** — srm-setup → seed review → clone-status report → srm-sync → sees missing[] → confirms → sync --clone-missing → cloned + mapped
- **Single new repo** — srm-sync add <url> → clone → detect → prefix ask → add → sync --repo
- Headless: sync/add flags are fully parameterizable except the add-time prefix ask, which has no 'use supplied value' escape hatch (enhancement-4).

## Findings

### Medium (8)

#### architecture-1 — --clone-missing silently rewrites the registered path when it differs from the URL-derived location

- Lens: architecture
- Location: `srm-sync/scripts/sync.py:587-600; srm-sync/SKILL.md:51`
- Evidence: clone_into() always targets <skills_repo_root>/<owner>/<repo> derived from the git URL, not the registry path. When cl['resolved'] != rroot, cmd_sync mutates repo['path'] and calls save_yaml(reg_path, data) — rewriting the user-managed sources.yaml mid-sync with no mention in the report or SKILL.md. The new SKILL.md guidance ('offer to re-run with --clone-missing to fetch them all') discloses nothing about this repoint, and the same issue surfaces via 'clone --url <url> for one': cloning a registered entry whose path differs lands the checkout where sync still won't look, so the entry reports missing again. Seed entries are pre-aligned (e.g. url BlackUnicornSecurity/BMAD-CYBERSEC.git → path {skills_repo_root}/BlackUnicornSecurity/BMAD-CYBERSEC), so the seeded six never trigger it — only hand-registered entries with custom paths do.
- Recommendation: Either clone to the registered path (git clone <url> <rroot>) so the registry stays authoritative, or surface the repoint in the JSON report (e.g. 'path_repointed': {from, to}) and add one clause to the SKILL.md missing-block guidance noting that entries whose path differs from <owner>/<repo> get repointed to the clone location.

#### architecture-2 — adaptation.md registry schema still documents url as 'informational'

- Lens: architecture
- Location: `srm-sync/references/adaptation.md:14`
- Evidence: The carved schema reference reads `url: https://github.com/...git      # informational`. The feature made url load-bearing: --clone-missing fetches from it, entries with empty url 'can't be fetched' per the new SKILL.md guidance, and sources-seed.yaml's comment was updated to say exactly that — but the schema file of record was not. A model that loads adaptation.md to edit the registry by hand (the seed file itself points there for the schema) learns the field is decorative.
- Recommendation: Update the schema comment in adaptation.md to match sources-seed.yaml: 'clone URL — sync --clone-missing fetches a missing repo from here; empty = hand-managed checkout'.

#### architecture-3 — Hard-rules line still scopes git clone to 'the clone command'

- Lens: architecture
- Location: `srm-sync/SKILL.md:14`
- Evidence: The stated hard rule reads: 'The only operations performed on sources are `git clone` (first fetch into `skills_repo_root`, via the `clone` command) and `git pull --ff-only`'. sync --clone-missing now runs git clone inside the sync flow — outside the enumerated 'via the clone command' scope. The principle stated in the Overview no longer matches the execution instructions added two sections later; on a literal read the new option contradicts the hard rule.
- Recommendation: Broaden the parenthetical to cover both entry points, e.g. '`git clone` (first fetch into `skills_repo_root`, via the `clone` command or `sync --clone-missing`)'.

#### determinism-1 — Prompt stats seeded repo paths and counts cloned sources by hand

- Lens: determinism
- Location: `sets/srm/srm-setup/SKILL.md:66 ('Check which seeds are already cloned')`
- Evidence: "Resolve `{skills_repo_root}` from the config just written and stat each seeded `path`. Report plainly — '2 of 6 sources cloned locally'" — this asks the LLM to parse sources.yaml, resolve the `{skills_repo_root}` token (whose stored value itself contains the literal `{project-root}` token, per the warning at line 18 and `module_vars()`'s nested resolve at scripts/sync.py:70), stat 6 paths, and count. Each step has one correct answer for a given input — a unit test could verify it — and the nested-token resolution is easy to fumble into a literal-`{project-root}` stat that misreports every seed as missing on re-setup runs.
- Recommendation: Determinism leak — push into a script. Apply the determinism test (resolve/stat/count are all pass-fail operations) and the signal-verb scan ('check which seeds are cloned', 'stat each path', 'report N of 6'). Add a read-only mode to srm-sync's engine — e.g. `sync.py missing` or `sync --dry-run` — that resolves tokens via the existing `module_vars()`/`resolve()` and emits compact JSON `{cloned: [...], missing: [...]}` (pre-pass JSON pattern; the `missing` array already exists in cmd_sync's report). srm-setup then runs one script call and reports the count instead of re-deriving it.

#### customization-1 — Author-specific seed registry hardcoded, not exposed as a template

- Lens: customization
- Location: `srm-setup/SKILL.md:62 → assets/sources-seed.yaml`
- Evidence: SKILL.md copies './assets/sources-seed.yaml' verbatim into {project-root}/_bmad/srm/sources.yaml. The seed ships the author's own picks (BMAD-CYBERSEC plus five named third-party repos). An org adopting srm would plausibly want to seed its own standard source list — especially now that the new 'check which seeds are already cloned' step makes the seed's contents load-bearing on fresh workspaces — but must fork the whole skill to swap it. This is the guide's '<purpose>_template' case: the skill loads a template the user might want to swap.
- Recommendation: Opt srm-setup into customize.toml (the one template alone justifies it) with `sources_seed_template = "assets/sources-seed.yaml"` under [workflow], and have the Seed the Sources Registry section read `{workflow.sources_seed_template}` instead of the hardcoded path. module.yaml and module-help.csv stay hardcoded — they are module manifests, not user-swappable templates.

#### enhancement-1 — Add: distinguish 'not yet cloned' from 'clone failed' in the missing flow

- Lens: enhancement
- Location: `sets/srm/srm-sync/SKILL.md:51 + scripts/sync.py:588-594`
- Evidence: Pattern involved: confirm-then-rerun offer (the stale/prune pattern applied to `missing`). When `--clone-missing` is supplied and a clone fails (private repo, bad URL, non-git dir blocking the target), the repo lands in `missing` anyway — the failure lives only in `repos.<name>.error` and `warnings`. SKILL.md then instructs the model to 'offer to re-run with --clone-missing' — the exact flag the user just ran, producing a dead-end retry loop for persistent failures like auth errors.
- Recommendation: Split the signal: either give `missing` entries a `reason`/`error` field in the report, or extend the SKILL.md paragraph — 'entries under `missing` whose `repos.<name>.error` is set failed to clone this run; show the error and its fix (auth, URL), do not re-offer the same command.'

#### enhancement-2 — Add: surface the silent registry path rewrite --clone-missing performs

- Lens: enhancement
- Location: `sets/srm/srm-sync/SKILL.md:45-51 + scripts/sync.py:596-599`
- Evidence: Pattern involved: gate-and-disclose on mutation (the skill's own convention — prune and --delete-skills both require user confirmation and are reported). On `--clone-missing`, if the clone's canonical location (`{skills_repo_root}/<owner>/<repo>`) differs from the registered `path`, sync.py writes `repo['path'] = cl['path']` and calls `save_yaml` — sync now mutates sources.yaml, invisible to the user and unmentioned in SKILL.md. A user who hand-set `path` to a non-canonical checkout (with `url` recorded) gets their entry silently 'corrected'.
- Recommendation: Disclose it: add a `path_updated` field (or teach the model 'when `cloned` appears alongside a changed `path`, tell the user the registry entry was corrected to the clone location'). If the rewrite is meant as an auto-fix rather than a guarantee, gate it behind the same offer used for missing itself.

#### enhancement-3 — Add: `clone --url` alternative for a single repo cannot fix a divergent registered path

- Lens: enhancement
- Location: `sets/srm/srm-sync/SKILL.md:51`
- Evidence: Pattern involved: complete-the-remediation (an offered fix must actually resolve the reported condition). The missing paragraph offers '`clone --url <url>` for one', but `cmd_clone`/`clone_into` only clones into `{skills_repo_root}/<owner>/<repo>` and returns path info — it never updates the registry `path`, and no path-edit command exists (remove + re-add is the only route). For any entry whose registered `path` isn't the canonical `<owner>/<repo>` location — e.g. a hand-managed or custom-located checkout with a url — the repo stays `missing` on the next sync even after a successful clone.
- Recommendation: Complete the instruction: 'or `clone --url <url>` for one — if the clone lands somewhere other than the registered `path`, update the entry's `path` to the returned value (remove + `add`, or a registry edit) before re-syncing.' Better still, route single-repo fetches through `sync --repo <name> --clone-missing`, which already fixes the path.

### Low (7)

#### leanness-1 — Seed-clone check paragraph restates srm-sync's mechanics

- Lens: leanness
- Location: `sets/srm/srm-setup/SKILL.md:66`
- Evidence: The new paragraph's parenthetical — `(--clone-missing` fetches each via its registry `url`; a plain `srm-sync` lists them as `missing` and offers the same)` — spells out another skill's flag mechanics and report-field names. A model running srm-setup only needs to tell the user that srm-sync will fetch missing repos on demand; the flag detail is then re-delivered by srm-sync itself at run time (the parenthetical even admits a plain sync offers it). This is downstream mechanics living in the wrong file plus a fact now restated across both skills' docs — if the flag is renamed, two files must change. The explicit procedure ('resolve {skills_repo_root}... stat each seeded path') and the meta-clause 'This sets expectations...' are also inferable around the core goal.
- Recommendation: Compress the paragraph to one goal sentence that keeps the non-inferables (the check, the on-demand message, the 'none is normal' calibration): '**Report clone status for the seeded sources.** Resolve `{skills_repo_root}` from the config just written, report plainly how many seeded `path`s exist locally (e.g. "2 of 6 sources cloned locally"), and note that `srm-sync` fetches the rest on demand — on a fresh workspace, typically none exist yet.'
- Proposed smallest: **Report clone status for the seeded sources.** Resolve `{skills_repo_root}` from the config just written, report plainly how many seeded `path`s exist locally (e.g. "2 of 6 sources cloned locally"), and note that `srm-sync` fetches the rest on demand — on a fresh workspace, typically none exist yet.
- Predicted delta: The user-facing message loses the `--clone-missing` flag name and the `missing` field name — both re-surfaced by srm-sync itself when the user runs it (plain sync lists missing and offers the clone). Expected loss is effectively nil. Route to variant eval to confirm.

#### architecture-4 — Single-repo fetch guidance stops one step short of done

- Lens: architecture
- Location: `srm-sync/SKILL.md:51`
- Evidence: The new missing-block guidance offers 'clone --url <url> for one' as an alternative to --clone-missing, but clone only fetches — the repo still isn't mapped until a follow-up `sync --repo <name>` runs. A literal reading can end the flow with the fetch complete and nothing materialized.
- Recommendation: Extend the clause to 'clone --url <url> for one, then sync --repo <name>'.

#### architecture-5 — Missing canonical Resolution-rules block; non-canonical ./ prefixes on internal paths (pre-existing)

- Lens: architecture
- Location: `srm-sync/SKILL.md:23,62,108; srm-setup/SKILL.md:10,22,35,39,54,62,82,86`
- Evidence: Both SKILL.mds route to multiple internal files (references/adaptation.md, assets/, scripts/) but carry no '## Resolution rules' block, which the principles require to be stamped into any multi-file SKILL.md. The collected path-standards prepass shows the same root cause as lint: 4 cross-dir ./ findings in srm-sync (prepass-paths-sync.json) and 10 in srm-setup plus one absolute-path example (prepass-paths-setup.json). Pre-existing — the diff added no internal file references — but both touched files still carry it.
- Recommendation: Drop the ./ prefixes in favor of bare paths (scripts/sync.py, references/adaptation.md, assets/module.yaml) and add the canonical '## Resolution rules' block to each SKILL.md; srm-setup:45's real-path example (/home/me/myapp) can stay as an illustration, not a reference.

#### architecture-6 — Both SKILL.mds sit in the token warn band; the new paragraph grows srm-setup's heaviest section

- Lens: architecture
- Location: `srm-setup/SKILL.md:60-68; srm-sync/SKILL.md`
- Evidence: srm-setup is 2281 tokens and srm-sync 1804 against budgets [1500 desired / 2500 hard]. The 'Seed the Sources Registry' section absorbed the new clone-check paragraph plus the prior prefix-review paragraph, making it the densest section in the warn-band file. Under the tier rules this is warn-not-block, but the drift direction is toward budget and the seed section is the named lift candidate.
- Recommendation: No carve needed yet; if srm-setup crosses 2500, lift 'Seed the Sources Registry' (seed review + clone check + schema summary) to references/ and leave a one-line pointer. For srm-sync, 'What the script does (reference)' is the lift candidate if it grows.

#### customization-2 — One-shot install ends with a fixed 'do not sync' boundary — on_complete candidate

- Lens: customization
- Location: `srm-setup/SKILL.md:64-66`
- Evidence: The skill produces its config artifacts and stops, with an explicit rule: 'Do not run srm-sync as part of setup; mapping is the user's explicit next step.' That is a deliberate default, but an org wanting post-install behavior (auto-run srm-sync --clone-missing on fresh workspaces, notification, audit step) can only fork.
- Recommendation: If customization-1 is adopted, the universal `on_complete` scalar comes with it for free and covers this case — no extra surface needed. Not worth a customize.toml on its own.

#### enhancement-4 — Opportunity: let a supplied prefix satisfy the add-time ask (headless readiness)

- Lens: enhancement
- Location: `sets/srm/srm-sync/SKILL.md:17,63`
- Evidence: Pattern involved: parameter-replaces-the-question (headless adaptability). Hard rule 'During `add`, always ask' plus step 2 'ask the user for the prefix' — but `sync.py add` accepts `--prefix` and errors only when absent ('--prefix is required (ask the user)'). A headless caller or a user who supplies 'add <url> with prefix foo' is still marched through the question. The rest of srm-sync is easily adaptable (every intent is flag-driven); `add` is the lone holdout — pre-existing, not introduced by this diff, but now adjacent to the new clone flow it touches.
- Recommendation: Scope the rule, don't remove it: 'ask for the prefix unless one was supplied with the invocation — prefixes are never guessed.' Keeps the never-guessed constraint while making `add` fully parameterizable.

#### enhancement-5 — Opportunity: 'stat each seeded path' doesn't cover the preserved-registry branch

- Lens: enhancement
- Location: `sets/srm/srm-setup/SKILL.md:62-66`
- Evidence: Pattern involved: complete-the-branch (the new check is written against the seed-copy path). The paragraph says 'stat each seeded `path`', but two sentences earlier the flow splits: if `sources.yaml` already exists it is preserved untouched, and there are no seeded entries to stat. A literal reader on the update path checks nothing, or checks seed paths that aren't in the user's actual registry.
- Recommendation: Change 'each seeded `path`' to 'each registered `path`' (or 'each entry in sources.yaml') so the clone-status report works identically on fresh-seed and preserved-registry runs.
