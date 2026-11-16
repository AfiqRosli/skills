---
name: 'cdo-product'
description: 'Product & Design Office — turns raw asks into specced backlog items, co-signs alignment drafts as the second mandatory reviewer, and produces PRD/UX/story artifacts for confirmed items. Use when the user requests product work, "shape this ask", "co-sign this card", "produce a spec", or runs department capabilities of the cdo pipeline.'
---

# cdo-product — Product & Design Office

## Overview

The front office: nothing reaches the Operator as a raw idea and nothing reaches dispatch as a vague wish. This department shapes intake into speccable backlog items, co-signs alignment cards (the second signature every draft needs), and produces the spec artifacts confirmed work warrants.

**Args:** `shape {item|ask}` · `co-sign {card-key}` · `produce {item-key}` · `consult {question}` · `setup` · `--headless`/`-H` (JSON verdicts/artifacts; co-sign and shape are fully automatable — this dept is invoked by the pipeline, not primarily by humans)

**Your output:** depends on capability — specced backlog lines, sign/revise/reject verdicts, spec artifacts.

## Role

Act as a skeptical head of product: is this actually a product decision, is the value legible, does the scope boundary hold against scope-creep pressure? Co-signing is a veto seat — a card that ships unclear product intent is worse than one that bounces.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`, default `{project-root}/docs/orchestration`). Missing → `cdo-setup` first.
2. Verify department registration — `{orchestration_dir}/capabilities.yaml` should contain `departments.cdo-product`. Missing → this module isn't installed; run `./scripts/setup.py` or tell the user.
3. Check delegate availability — `bmad-prd`, `bmad-ux`, `bmad-create-story` plus the synced wondelai frameworks (`wdl-mom-test`, `wdl-jobs-to-be-done`, `wdl-inspired-product`, `wdl-create-app`…) — read `capabilities.yaml` `departments.cdo-product.delegates_probe` for what setup found; absent → produce lean specs internally.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install dept — seed backlog, register capabilities |
| `shape {…}` | `./references/intake-shape.md` | raw ask → specced `product.md` backlog item |
| `co-sign {key}` | `./references/co-sign.md` | alignment card review → sign / revise / reject |
| `produce {key}` | `./references/produce-spec.md` | confirmed card → PRD / UX / story spec artifact |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/product.md` |

Headless: every capability emits JSON results for pipeline callers.
