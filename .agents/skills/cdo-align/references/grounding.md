# Grounding Catalog

What "grounded" looks like per source. Outcome over ritual: the goal is that no load-bearing claim on the card rests on unverified assertion — not that every source gets touched for every item. Small items ground cheap; the read scales with blast radius.

## Codebase

- **Integration points** — where the work actually lands: routes, services, stores, schema tables, hooks, emit points. Cite `file:line`; `no anchor found` is a flag, not a sentence on the card.
- **Existing machinery** — what already does part of the job (emitters, senders, schedulers, util modules). Reuse beats rebuild; duplication gets named in Marshal's Read, not smuggled into scope.
- **Spec deltas** — hooks, events, tables, or routes the spec assumes that don't exist. Each is a scope challenge or a flag — never silently absorbed into "the spec says so".
- **UI surfaces** — for UI-affecting items, open the actual page/component, its design tokens (global CSS, font/spacing scales, component names), *and the dominant environment the surface is experienced in* (browser route vs phone host-app — the frame matches it): the Visual Preview wire and mock frame the to-be inside that environment's chrome. For backend items, trace **which surface consumes the changed state** — the component rendering the affected data, the state a lifecycle implies (pending/empty/error) — and wire/mock that surface's new state. `n/a — no UI surface` is a claim you justify, not a default: if a surface reflects the change, it gets artifacts. A wire or mock sketched from spec prose is commentary, not design.
- **Tree state** — `git rev-parse HEAD` at draft time feeds `grounded_against.commit`. A card verified against a three-week-old tree is detectable at dispatch; an unanchored card isn't.

## Externals (third-party platforms, APIs, libraries)

For each named external, verify at draft time:

- **Capability & plan gating** — does the feature exist, on which tier, at what quota.
- **API surface** — the endpoint/step/field names the design assumes.
- **Failure & edge semantics** — timeouts, retries, rate limits, lifecycle boundaries that shape the design.

Verified → fact on the card (System Context's `owns vs platform` carries the split). Unverifiable → flag naming what resolves it. Asks are for judgment calls — never spend an Operator question on a lookup.

## Card corpus

- **`alignment/drafts/` + `alignment/YYYY/MM/DD/`** — pending and archived cards in the same systems/domain: conventions to inherit (name them in Doctrine Grounding or the read), contradictions and duplicates to name, dep edges to declare in frontmatter `deps`.
- **`alignment/superseded/`** — replaced drafts of this key. Diff old vs new before drafting: what was wrong last time is the cheapest calibration there is.

## Calibration

- **`flow-ledger.yaml` `stories.*`** — attempts, quarantine reasons, `delivery_review` verdicts for work in the same systems: the empirics behind the confidence score.
- **`patterns.md`** — Marshal's unconfirmed working hypotheses (escalation types, shapes that stall, how the Operator decides). Draft-aware; cite when relevant.
- **`learning/knowledge/*.yaml`** — extracted lessons from shipped stories.
- **Doctrine Decision Log corrections** — `confirm-edited` notes record *what* the Operator changed on past cards; recurring corrections are your score's prior.

## The sixth read — interrogate, then position

The catalog grounds the item; this read is where the card's *position* comes from. Interrogate before compiling:

- What business intent does this serve — name the outcome, or flag that none is legible.
- Who's the user and what would they notice?
- Do the epic's acceptance criteria measure the outcome or just the output?
- Is the decomposition hiding scope, smuggling a decision, or sequencing things backwards?
- Is there a materially cheaper route to the same intent the spec doesn't consider?

Then compile holistically, not item-local — an item that duplicates or contradicts a sibling gets that named on the card — and discharge two closing duties:

- **Self-adversarial** — the strongest argument *against* your read goes on the card; if you can't write one, the read isn't finished.
- **Gap-surfacing** — adjacent work the backlog doesn't carry (missing stages, unnamed edges) lands in `gaps` on the filing payload, flagged on the card; you're the one pair of eyes that sees the whole backlog fresh.

### Strategic axes rubric

The card's Marshal's Read answers six named questions — argue each, don't hand-wave:

- `intent-fit` — does it advance intent.md's thrust?
- `user-value-chain` — which user, what outcome? Internal work names its *chain* (e.g. bundle-size→load-time→trust); "no chain legible" is a finding.
- `spec-honesty` — is the product office's framing true, or inflated?
- `reversibility` — can a bad call be unmade cheaply?
- `precedent` — does confirming this set a rule for everything after?
- `timing` — why now vs later? Sequencing counts.

A trip on any axis is flag `axis-trip:{axis}` — a verdict the Operator must see, not a rhetorical flourish.
