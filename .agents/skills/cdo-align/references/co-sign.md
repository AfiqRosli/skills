# Co-sign — the P&D second signature

Every card needs a second signature **before filing** — co-sign reviews the drafted card body, so the file lands already stamped; refiling after the fact would erase the stamp. This reference loads only when `{project-root}/.agents/skills/cdo-product/SKILL.md` exists (SKILL.md gates the branch).

Pass each drafted card body through `cdo-product`'s `co-sign` capability:

- `sign` → file with `- **P&D co-sign:** sign — {notes}` in the card's header.
- `revise` → fix the card and re-submit once — a second `revise` files flagged `P&D disputed` for the Operator to adjudicate.
- `reject` → don't file it; report the rejection.

Missing `cdo-product` → file unsigned and say so — the dept is a gap, not a block; `apply-decisions` warns on unsigned cards when the dept is installed.

The filer enforces the stamp's shape, not its content: the check is the contracted header line `- **P&D co-sign:** {verdict}` — a body mention of `P&D co-sign:` or the template's unsubstituted `{sign|revise|reject — rationale}` placeholder is not a signature and routes `unsigned-cosign`.
