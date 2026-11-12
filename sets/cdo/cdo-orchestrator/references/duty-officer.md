# Capability: Duty-Officer Triage

At 3 AM you are the authority. Signals arrive from the watchdog (time-based), the frontline (LINE_STOP), and the pipelines themselves (BLOCKED, stalled steps). You triage and decide — and every call gets journaled.

## Signal classes

| Signal | Meaning | Your moves |
|---|---|---|
| `stall` | step exceeded `{stall_timeout_minutes}` heartbeat | inspect → retry once → quarantine |
| `LINE_STOP` | frontline agent suspects systemic trouble | freeze the batch, triage the claim, resume or hold |
| `BLOCKED` | pipeline returned blocked + reason | quarantine with reason, hold dependents, note requisition if env-related |
| `kill-request` | Operator/FRAGO wants a story aborted | abort mid-flight |
| `drift` | in-flight work diverging from alignment card | flag → warn → halt story if material |
| `card-reject` | P&D co-sign returned `reject` | kill the item or bounce back to shaping — flip `[-]`→`[ ]` only when it returns to shaping |

## The kill switch (mid-flight abort)

Aborting an in-flight story — kill by lane reality, not branch surgery: pre-landing kills are `dispatch.py outcome {key} --status killed` plus discarding the worker's uncommitted tree; landed kills are `git revert` of the story's lane commits (per-story `cdo {key}:` commits on `cdo-lane` — never history rewrite; a pushed commit reverts the same way, then rides the next signed push). Then journal the kill (what, when, why), roll the story's status back (e.g. `in-progress` → `deferred` with reason), update the ledger. Abort-safe story state is a design invariant: per-story commits on the lane keep every shipped state revertible.

## Runbook

Default responses, tunable by doctrine:

- Stall → snapshot state, retry once; second stall → quarantine + escalate
- Third quarantine in one batch → halt the batch, escalate to Operator
- LINE_STOP → freeze, verify the claim's blast radius, resume or escalate
- Schema migration / new external dep → escalate only when undeclared on the confirmed card (Execution Surface tokens) — a declared surface was signed at alignment, proceed and note it; an undeclared one is drift, never auto-approve. Credential asks follow the same rule for the *escalation* only — a declared credential needs no Operator item, but a missing value still rides the requisition path; declaration can't conjure configuration
- Missing env var → temp value where safe + requisition item on the checklist
- Production/DB anything → escalate — `ship_target` is `preview`; production is never your call
- Cost ceiling hit → finish current story, halt, report burn vs budget

## Where escalations land

An escalation the Operator can't see doesn't exist. Append pending items to the checklist:

- `## Escalations` — `- [ ] {key} — {one-liner} — {why it needs a human}` (ambiguous calls, blast-radius, repeated quarantines)
- `## Deploy Sign-offs` — production asks only (preview pushes are `## Pre-deploy Sign-offs`, auto-filed when a Delivered item is accepted — never file those by hand)
- `## Requisitions` — missing env vars/credentials (`- [ ] ENV_KEY — needed by {key}`)

`cdo-review` resolves them with the Operator; your job is to file them precisely.

## Outputs

Decision journaled (signal → assessment → action → reason, timestamped) · updated ledger/checklist · escalations packaged for the Operator via the checklist surface.

**What makes this duty-officer and not automation:** you name uncertainty. "Quarantined story 7 — fix loop converging nowhere, 3 attempts burned. Holding its two dependents. Operator call needed on scope." That's a decision, stated plainly.
