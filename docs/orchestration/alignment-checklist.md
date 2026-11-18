# Alignment Checklist — Pending Operator Review

The single surface for everything awaiting the Operator's eye: alignment drafts,
escalations, pre-deploy + deploy sign-offs, env-var requisitions. Sorted by
confidence — what the machine knows it's unsure about goes first.

<!-- Card item format (written by cdo-align's file-cards.py):
     - [ ] {key} — {title} | conf {pct}% | flags: {uncertainties} | asks: {n} | wire: {wiretext-url} | draft: alignment/drafts/{key}.md
     (`wire:` segment appears only on UI-touching cards — the Operator's visual check-off)
     Confirmed/rejected cards move to alignment/YYYY/MM/DD/ by cdo-review.
     Deferred cards park under alignment/parked/ (drafts/ = unexamined only)
     until a resurface or unpark verdict brings them back. Delivery
     reviews stage at alignment/reviews/ while Operator-pending — the
     verdict on their line graduates the doc beside the card. Non-card
     items (escalations, sign-offs, requisitions) use the
     same - [ ] checkbox form under their sections. -->

## Needs Attention

<!-- flagged or confidence < 80% — Operator attention first -->

- [ ] version-upgrade-01 — Upgrade project version (cut v0.4.0 carrying the cdo-align hardening) | conf 87% | flags: ungrounded:source, contract-break, dirty-tree, calibration-thin, es-declaration | asks: 2 | draft: alignment/drafts/version-upgrade-01.md
## Routine Review

<!-- confident drafts awaiting sign-off -->

- [x] platform-01 — Release train: ship cdo-align set update as v0.3.0 | conf 85% | flags: dirty tree spans 3 concerns, version call is Operator's | asks: 5 | draft: alignment/drafts/platform-01.md → confirm 2026-11-17 — confirmed as drafted

## Delivered

<!-- post-delivery review — filed by Marshal's delivery-note pass after
     reading the evidence (ledger findings, sessions/{key}.md, transcript).
     Never the worker's self-report. Format:
     - [ ] {key} — {Marshal's one-line assessment} | verdict: sound|flagged
           | review: alignment/reviews/{key}.review-{n}.md | filed {ts}
     Operator verdicts: confirm = accept delivery · reject = rollback escalation.
     Either verdict graduates the review doc beside the card's dated archive. -->

## Escalations

## Pre-deploy Sign-offs

<!-- preview-lane push gate — filed by cdo-review when a ## Delivered item is
     accepted. Local ship lands on the cdo-lane ref; nothing reaches origin
     until an item here is signed (every push spends a remote build).
     Format: - [ ] {key} — push to origin/{lane} | lane {sha8} | marked {date}
     confirm/granted = push it · reject/blocked = stays local -->

## Deploy Sign-offs

- [x] platform-01 — publish v0.3.0: merge preview → main, push origin main + tag v0.3.0 | lane ccef75d | marked 2026-11-17 → granted 2026-11-17 — Operator: push v0.3.0 — merge preview to main, push main + tag
      confirm/granted = push it · reject/blocked = stays local

## Requisitions (env vars, credentials, accounts)

- [ ] req-01 — `DEVIN_API_KEY` for dispatch workers (`devin acp` auth). Set the env var, write `{project-root}/.env`, or run `devin auth login`. Blocks: platform-01 drain spawn. | filed 2026-11-17
