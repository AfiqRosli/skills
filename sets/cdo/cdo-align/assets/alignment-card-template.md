---
key: "{key}"
backlog: "{backlog-file}"
deps: [] # item keys this card depends on — declared, not implied
touches: [] # dirs/systems the work lands on
emits: [] # events/signals the work produces — [] if none
externals: [] # platform/credential/account names it needs
declared_surface: [] # must match the ## Execution Surface risk tokens
grounded_against:
  commit: "" # git SHA at draft time — staleness is detectable from here
  drafted: "" # YYYY-MM-DD
---

# Alignment Card — {key}: {title}

<!-- Machine-comparable contract. Filed by cdo-align, decided by cdo-review.
     The frontmatter IS the diffable surface — dispatch, drift-watch, and
     future drafts read fields, not prose. Keep it literal and keep it
     YAML-safe (quote anything with colons/braces — this repo's docs build
     will eat unquoted values). If confirmed, the pipeline benchmarks
     against THIS card — precision here is what makes "aligned" enforceable. -->

- **Source:** `{backlog-file}` · drafted {YYYY-MM-DD HH:MM}
- **Confidence:** {pct}%
- **Sizing:** {lite|full}
- **P&D co-sign:** {sign|revise|reject — rationale}  <!-- required when cdo-product is installed; `apply-decisions` warns on unsigned cards -->

## Marshal's Read

<!-- The CDO's independent position — what the Operator is actually reviewing.
     Written fresh, not paraphrased from the product office's spec. -->

- **Business intent:** {the outcome this serves against `intent.md` — or "none legible", which is a flag}
- **User value:** {who benefits and what they'd notice; internal hygiene still needs a stated payoff}
- **Challenges to the source spec:** {where the epic/story is wrong, vague, over-scoped, or sequencing backwards — or "none"}
- **Alternatives weighed:** {cheaper/different routes considered and why they lost — or "none surfaced"}
- **Strongest objection:** {the best argument AGAINST confirming this card as drafted — if none comes, the read isn't finished}

### Strategic axes

<!-- One verdict each — these are the asks the Operator actually adjudicates.
     Any trip (irreversible / precedent / intent-ambiguous / user-visible)
     routes the card to Needs Attention regardless of confidence. -->

- `intent-fit`: {advances the current thrust? — verdict + one line}
- `user-value-chain`: {which user, what outcome — or the honest chain for internal work}
- `spec-honesty`: {is the product office's framing true — or inflated?}
- `reversibility`: {can a bad call be unmade cheaply?}
- `precedent`: {does confirming set a rule for everything after?}
- `timing`: {why now vs later — sequencing argument}

## System Context

<!-- The technical overview the Operator reviews alongside intent — the
     machinery this card rides, where it lands, what it owns. Grounded:
     claims carry anchors (`file:line`), not vibes.
     `n/a — no system surface` for pure content/docs items, same posture
     as Visual Preview's n/a for non-UI. -->

- **Current state:** {what exists today — the machinery already in place, anchored}
- **Flow:** {trigger → stages/gates → exits — one line per stage, legible at a glance}
- **Integration points:** {file:line where the work lands}
- **Owns vs platform:** {what we build vs what the external provides}

## Visual Preview

<!-- The wiretext URL the Operator opens to check the design off WITH the
     card — a confirmed card's URL is the pre-approved design; the
     pipeline's wireframe gate reuses it instead of re-asking. The wire
     reproduces the touched surface's CURRENT layout and marks the delta —
     a sketch the Operator can't hold against the live page is commentary,
     not design. Non-UI items fill `n/a — no UI surface`. -->

- **Wireframe:** {https://wiretext.app/w/… | `n/a — no UI surface` | `unavailable — wiretext MCP absent`}

## Questions for the Operator

<!-- Judgment calls only — each pairs with Marshal's recommended answer;
     confirm it or override it in your verdict note. Never spend an ask on
     what a codebase read or vendor doc would answer — asks are for
     decisions, not lookups.
     "None — recommend confirm as drafted" is a valid section. -->

- {question} — recommended: {answer}

## Acceptance Criteria

<!-- Each must be verifiable — a future auditor checks the work against these -->

- [ ] {AC 1}
- [ ] {AC 2}

## Scope Boundary

- **In:** {what's covered}
- **Out:** {explicitly not covered — what a wandering pipeline must not touch}

## Externals Needed

<!-- What only the Operator can procure — surfaces as a requisition at dispatch -->

- {ENV_VAR / platform / credential / account} — {what for}

## Execution Surface

<!-- Machine-checkable declarations — dispatch gates check these tokens.
     Routing: ANY non-`none` token routes this card to Needs Attention.
     `schema-migration` and `deps-changed` additionally pre-clear those
     dispatch gates once confirmed (package.json manifests only;
     services/APIs/credentials belong in Externals, not here).
     `env-changed`, `api-contract`, `data-backfill` are attention-only —
     gates still apply normally.
     Declared = pre-approved inside this card's scope; the same surface
     discovered undeclared mid-flight is drift and escalates. -->

- **Risk surface:** {none | `schema-migration` | `deps-changed` | `env-changed` | `api-contract` | `data-backfill` — comma list of all that apply}

## Flags

<!-- What you're NOT confident about, stated precisely — `oversized` when
     the scope implies more than one dispatch arc (per the drafter's
     sizing-flags guidance), `axis-trip:{axis}` when a strategic axis trips
     (any trip is Needs Attention by structure), `ungrounded:{store}` when
     a grounding source was missing. -->

- {flag}: {why uncertain} — resolves if {condition}

## Suggested Split

<!-- oversized cards only — recommended split into keys w/ clean deps -->

- {key}: {slice} — deps {deps}

## Doctrine Grounding

<!-- Which prior decisions informed this draft — precedent, not assertion -->

- {doctrine entry / correction cited}: {how it shaped this card}
