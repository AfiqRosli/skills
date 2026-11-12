---
department: engineering
temporal_pattern: audit-trail
content_type: dev-log
status: current-stable
title: "Dev Log — {story-key}"
description: "CDO dispatch log for {story-key} ({release})"
lastUpdated: true

pipeline:
  story_key: "{story-key}"
  release: "{release}"
  sprint_status: "{sprint_status_path}"
{pipeline_steps}
dispatch:
  readiness: pending
  claim: pending
  produce: pending
  verify: pending
  ship: pending
  extract: pending
  feed: pending
  release: pending
cdo:
  session: "{session}"
  department: "{dept}"
  backlog: "{backlog}"
  card: "{card_path}"
---

# Dev Log — {story-key}

**Release:** {release} · **Story doc:** `{story_file_path}` · **Card:** `{card_path}` · **Session:** `{session}`

## Journal

<!-- Append-only. Newest entries at the bottom. Entries use #### titles only — ## Journal is the sole outline heading. -->
<!-- Changes need decision entries — Context / File / Goal / Gap / Before / After (literal code in language-tagged fences, one field per line) / Why this approach / Alternatives considered / Watch out for. Format: .agents/skills/cdo-batch/references/devlog-conventions.md -->
