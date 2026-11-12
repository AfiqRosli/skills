# skills

House skill modules, installable into any project's `.agents/skills` via the exec runner of your choice. Each set is an independent bin — install only what you need.

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

## Private repo variant

If the repo is private, use the SSH form (requires your SSH keys):

```bash
bunx -p git+ssh://git@github.com/AfiqRosli/skills.git cdo
```

## Releasing

Skills are authored in the source repo (`prto` at `.agents/skills/`). Re-stage and release:

```bash
node tools/stage.mjs --from C:\Core\Businesses\PRTO\prto
# bump version in package.json
git add -A && git commit -m "release: <notes>"
git tag v0.2.0
git push --tags origin main
```
