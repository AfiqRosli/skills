# Grounding Catalog

What "grounded" looks like per source. Outcome over ritual: the goal is that no load-bearing claim on the card rests on unverified assertion — not that every source gets touched for every item. Small items ground cheap; the read scales with blast radius.

## Codebase

- **Integration points** — where the work actually lands: routes, services, stores, schema tables, hooks, emit points. Cite `file:line`; `no anchor found` is a flag, not a sentence on the card.
- **Existing machinery** — what already does part of the job (emitters, senders, schedulers, util modules). Reuse beats rebuild; duplication gets named in Marshal's Read, not smuggled into scope.
- **Spec deltas** — hooks, events, tables, or routes the spec assumes that don't exist. Each is a scope challenge or a flag — never silently absorbed into "the spec says so".
- **UI surfaces** — for UI-touching items, open the actual page/component: the Visual Preview wire must reproduce its current layout and mark the delta (see `./wireframe.md`). A wire sketched from spec prose is commentary, not design.
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
