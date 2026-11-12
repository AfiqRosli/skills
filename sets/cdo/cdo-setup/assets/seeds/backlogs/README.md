# Backlogs

One file per department — `cdo-setup` derives the `backlog_map` config from
which `cdo-*` department modules are installed.

Convention: `backlogs/{dept}.md` where `{dept}` is the module name minus the
`cdo-` prefix (`cdo-growth` → `content.md` is the exception — see the map below).
A department module's setup should place its queue here so `cdo-batch` can
drain it through the shared align → dispatch → produce → review machinery.

| Module | Backlog |
|---|---|
| code pipeline (`cdo-code-e2e`) | `code.md` |
| `cdo-growth` | `content.md` |
| `cdo-academy` | `curriculum.md` |
| other `cdo-{dept}` | `{dept}.md` |

## Item markers

| Marker | Meaning |
|---|---|
| `- [ ]` | unaligned — candidate for `cdo-align` to draft |
| `- [A]` | alignment draft filed — awaiting Operator decision in `alignment-checklist.md` |
| `- [x]` | confirmed — dispatchable; the card moved to `alignment/YYYY/MM/DD/` |
| `- [-]` | deferred/quarantined — reason recorded |
