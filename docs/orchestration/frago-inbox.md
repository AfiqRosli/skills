# FRAGO Inbox — Operator Directives

Drop directives here at any time — reprioritize, halt, skip, rescope. The CDO
polls this file at story boundaries and mid-story checkpoints; each directive
is timestamped, journaled, and triggers an explicit re-plan.

<!-- Format:
     ### YYYY-MM-DD HH:mm
     directive text — e.g. "deprioritize story 8", "halt after current",
     "skip all UI stories this batch"

     CDO marks consumed entries with → processed {timestamp} {outcome} -->

### 2026-11-17 18:49
"update our release train. we had updated the sets earlier" — routed to
platform backlog as `platform-01`; alignment card drafted
→ processed 2026-11-17 19:00 — confirmed, produced inline, v0.3.0 cut on preview

### 2026-11-17 19:02
"update the readme" — document the installed org (orchestration home,
preview lane, gated push) in README.md; small doc fix, run inline

### 2026-11-18 14:15
"upgrade project version" — work request; intaked to version-upgrade
backlog as `version-upgrade-01`, unaligned — awaits the alignment leg
→ processed 2026-11-18 14:15 — routed, queued `[ ]`

### 2026-11-20 16:15
"update sets and repo versions" — reinstall cdo/srm/scaffold sets into
.agents/skills from sets/, refresh skills-manifest versions, bump repo
version + tag for the scaffold rework
→ processed 2026-11-20 16:15 — sets synced (scaffold pruned of stale 01-04 refs),
manifest @0.6.0, release v0.6.0 committed + tagged
