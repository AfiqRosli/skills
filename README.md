# skills

House skill modules, installable into any project's `.agents/skills` via the exec runner of your choice. Each set is an independent bin — install only what you need.

**This repo is the authoring source of truth.** Skills are edited directly under `sets/`; consuming projects (including `prto`) install managed copies and should never edit `.agents/skills/<managed>` locally — those changes are overwritten on the next install.

## Sets

| Bin        | Skills                                                        | Purpose                                        |
| ---------- | ------------------------------------------------------------- | ---------------------------------------------- |
| `cdo`      | `cdo-*` (26)                                                  | Autonomous Delivery Org — departments + pipeline |
| `srm`      | `srm-setup`, `srm-sync`                                       | Skills Repo Manager — maps external skill repos  |
| `scaffold` | `project-greenfield-scaffold`                                 | Greenfield project scaffold on the house spine   |

## Install

```bash
# bun
bunx -p github:AfiqRosli/skills cdo
bunx -p github:AfiqRosli/skills srm
bunx -p github:AfiqRosli/skills scaffold

# npm
npx -y -p github:AfiqRosli/skills cdo

# pnpm / yarn
pnpm dlx -p github:AfiqRosli/skills cdo
yarn dlx -p github:AfiqRosli/skills cdo
```

Run from your project root. Skills land in `.agents/skills/`; a `.agents/skills-manifest.json` tracks what each set installed for upgrade/uninstall.

Pinned version (recommended for release tags):

```bash
bunx -p github:AfiqRosli/skills#v0.1.0 cdo
```

### Flags

```
cdo --list              # show what the set ships
cdo --dir <path>        # install into a different project root
cdo --uninstall         # remove the set's skills from this project
cdo --dry-run           # preview without writing
```

### After install

- `cdo` → invoke the `cdo-setup` skill (requires a git repo and an official BMAD install at `_bmad/config.yaml`)
- `srm` → invoke `srm-setup`, then `srm-sync`
- `scaffold` → invoke `project-greenfield-scaffold`

## Authoring & releasing

Edit skills under `sets/<set>/<skill>/`. To add a new set, create `sets/<name>/`, add a `bin/<name>.js` wrapper calling `lib/install.js#run('<name>')`, and register the bin in `package.json`.

Cut a release:

```bash
node tools/release.mjs patch "what changed"   # or minor | major
git push --follow-tags origin main
```

Consumers then pull the new version with `bunx -p github:AfiqRosli/skills#vX.Y.Z <set>` — or unpinned, accepting the runner's cache window.
