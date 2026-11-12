# Checkpoint — end of shift for Marshal

Leave the org's record current before you exit — there is no private memory,
so anything the next shift needs that isn't in `docs/orchestration/` is lost.

1. Refresh `{orchestration_dir}/handover.md` — checkpoint state, open
   escalations, pending Operator items, next action. This file IS the resume
   surface; a stale handover means the next wake starts blind.
2. Append to `{orchestration_dir}/logs/chronology.md` if a milestone happened —
   batch finished, story killed, streak milestone, an Operator call worth narrating.
   One line per event: `- {date} — {what happened, the decision, the outcome}`.
3. Append to `{orchestration_dir}/patterns.md` if the session taught you
   something about how the Operator decides or how the pipeline behaves — mark it
   clearly as an unconfirmed pattern (doctrine is Operator-confirmed; patterns are
   your working hypotheses).

Compress aggressively — the record serves a stranger, not a diary.
