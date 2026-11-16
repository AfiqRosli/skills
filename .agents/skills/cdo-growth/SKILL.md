---
name: 'cdo-growth'
description: 'Growth & Content Office — inbound-only content operation: shipped work feeds the content backlog, produce authors posts/guides, calendar maintains the editorial view. Use when the user requests "content", "write a post", "editorial calendar", or runs the growth leg of the cdo pipeline.'
---

# cdo-growth — Growth & Content Office

## Overview

The publishing desk — **inbound only**. Source material is what the org actually shipped: `feed` pulls done/verified stories into the content queue automatically, `produce` authors pieces that cite their source stories, `calendar` tracks what's going out.

**Args:** `feed` · `produce {key}` · `calendar` · `consult {question}` · `setup` · `--headless`/`-H`

## Role

Act as an editorial lead with a hard rule: real work is the content. No vapor, no outbound spam — a piece that can't cite what shipped doesn't publish.

## On Activation

1. Load config (`{project-root}/_bmad/config.yaml` `cdo:` section → `{orchestration_dir}`). Missing → `cdo-setup`.
2. Verify registration — `capabilities.yaml` `departments.cdo-growth`. Missing → `./scripts/setup.py`.

4. Messaging frameworks — `wdl-storybrand-messaging`, `wdl-made-to-stick`, `wdl-contagious`, `wdl-grow-*` per `delegates_probe`.

## Capability Routing

| Invocation | Route | Job |
|---|---|---|
| `setup` | `./scripts/setup.py` | install — content backlog, manifest |
| `feed` | `./references/feed.md` | `feed.py` — shipped stories → content items (idempotent) |
| `produce {key}` | `./references/produce.md` | confirmed item → `content/{key}/` + meta |
| `calendar` | `./references/calendar.md` | maintain `content/calendar.md` |
| `consult {…}` / no args | `./references/consult.md` | office-hours — advisory, read-only, notes → `consult/growth.md` |