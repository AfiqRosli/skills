# skills

House skill modules, installable into any project's `.agents/skills` via the exec runner of your choice. Each set is an independent bin — install only what you need.

**This repo is the authoring source of truth.** Skills are edited directly under `sets/`; consuming projects (including `prto`) install managed copies and should never edit `.agents/skills/<managed>` locally — those changes are overwritten on the next install.

## Sets

| Bin        | Skills                                                        | Purpose                                        |
| ---------- | ------------------------------------------------------------- | ---------------------------------------------- |
| `srm`      | `srm-setup`, `srm-sync`                                       | Skills Repo Manager — maps external skill repos  |
| `cdo`      | `cdo-*` (27)                                                  | Autonomous Delivery Org — departments + pipeline |
| `scaffold` | `project-greenfield-scaffold`                                 | Greenfield project scaffold on the house spine   |

## Install

**Prerequisite — official BMAD.** These sets are BMad modules and expect a real BMAD install at `_bmad/config.yaml` (`cdo` refuses to set up without one). Install it manually first, from your project root — follow the interactive installer from [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD):

```bash
bunx bmad-method install
```

Then install the sets in order:

```bash
# 1. Skills Repo Manager — manages external skill repos
bunx -p github:AfiqRosli/skills srm

# 2. Autonomous Delivery Org — departments + pipeline
bunx -p github:AfiqRosli/skills cdo

# 3. Greenfield scaffold — optional, only when starting a new project
bunx -p github:AfiqRosli/skills scaffold
```

Other runners work the same way:

```bash
# npm
npx -y -p github:AfiqRosli/skills srm

# pnpm / yarn
pnpm dlx -p github:AfiqRosli/skills srm
yarn dlx -p github:AfiqRosli/skills srm
```

Run from your project root. Skills land in `.agents/skills/`; a `.agents/skills-manifest.json` tracks what each set installed for upgrade/uninstall.

Pinned version (recommended for release tags):

```bash
bunx -p github:AfiqRosli/skills#v0.6.0 cdo
```

### Flags

```
<set> --list            # show what the set ships
<set> --version         # print the fetched package version (verify the runner didn't serve a cached old one)
<set> --dir <path>      # install into a different project root
<set> --uninstall       # remove the set's skills from this project
<set> --dry-run         # preview without writing
<set> --no-setup        # skip the post-install upgrade leg (cdo)
```

### Upgrading

Re-run the same command with the new tag. The pin matters — an unpinned fetch can be served from the runner's cache and silently reinstall the old version (the manifest then correctly records that old version again).

```bash
bunx -p github:AfiqRosli/skills#v0.6.0 cdo
```

For `cdo`, when the bin detects a prior install (`cdo:` in `_bmad/config.yaml` or an existing orchestration tree) it also runs the setup chain headlessly — detect, propose, scaffold repair, config merge, help CSV, ship lane — using stored config, so a re-run is a complete upgrade with no agent round-trip. New `module.yaml` keys are applied with their defaults and listed in the output; change them via the `cdo-setup` skill (`--set key=value`). Fresh installs still route to the `cdo-setup` skill, where the config proposal earns its prompts. Requires `uv` or `python` on PATH for the setup leg; without it the skill files still install and the hint prints.

### After install

- `srm` → invoke `srm-setup`, then `srm-sync`
- `cdo` → invoke the `cdo-setup` skill (requires a git repo and an official BMAD install at `_bmad/config.yaml`)
- `scaffold` → invoke `project-greenfield-scaffold`

## This repo runs the org

The cdo module is installed here — `docs/orchestration/` is the operation's home:

- `backlogs/*.md` — work intake, one queue per department
- `alignment-checklist.md` — the Operator surface: card reviews, sign-offs, requisitions
- `flow-ledger.yaml`, `handover.md` — live state; the next session cold-starts from these

Work ships on the `preview` lane; pushes to `origin main` + release tags are Operator-gated (Deploy Sign-offs on the checklist). Talk to `cdo-orchestrator` (Marshal) to run the operation.

## Authoring & releasing

Edit skills under `sets/<set>/<skill>/`. To add a new set, create `sets/<name>/`, add a `bin/<name>.js` wrapper calling `lib/install.js#run('<name>')`, and register the bin in `package.json`.

Cut a release:

```bash
node tools/release.mjs patch "what changed"   # or minor | major
git push --follow-tags origin main
```

(Releases are cut on `preview`; the push is the gated publish leg — see Deploy Sign-offs.)

Consumers then pull the new version with `bunx -p github:AfiqRosli/skills#vX.Y.Z <set>` — or unpinned, accepting the runner's cache window.
