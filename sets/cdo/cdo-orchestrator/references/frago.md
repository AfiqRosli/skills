# Capability: FRAGO Processing

The Operator's override channel — `{orchestration_dir}/frago-inbox.md`. An interrupt, not a queue: directives land any time and you consume them at story boundaries *and* mid-story checkpoints.

**Chat is an intake surface too.** A directive spoken in conversation ("halt after this", "deprioritize story 8") gets journaled into `frago-inbox.md` timestamped — the file is the ledger of record even when the directive arrived verbally. Nothing spoken should live only in chat.

## Processing

For each unconsumed directive:

1. **Acknowledge** — mark it consumed with timestamp and your reading of it.
2. **Re-plan** — what changes: reprioritized items, halted work, kills needed, invalidated alignment drafts. If the directive invalidates confirmed work, say what stops and what survives.
3. **Execute** within authority — reorders and skips are yours; kills get the full treatment (pre-landing: outcome `killed` + discard the tree; landed: `git revert` the story's `cdo-lane` commits; then journal + roll status). Directives you can't execute (e.g., "also deploy to prod") → escalate, don't silently drop.
4. **Journal** — directive + interpretation + actions taken, timestamped.

## Semantics that matter

- **Interrupts, not votes.** A directive applies from the moment you read it — in-flight work gets aborted if directed; it never "finishes first" unless the directive says so.
- **Ambiguity → narrowest reading + flag.** "Skip the UI stories" — you decide which items count, state your interpretation, and leave it reversible. When genuinely torn, escalate rather than guess on scope.
- **Silence isn't consent.** No new directives = keep executing the current manifest. An empty inbox means "as you were," not "fill the gap."

## Outputs

Consumed markers + re-planned manifest + kill journals (if any) + journal entry in the ledger. The Operator should be able to drop one line and trust the org re-shaped around it.
