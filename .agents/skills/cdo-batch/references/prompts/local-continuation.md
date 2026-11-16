<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
-->

6a. Continuation contract — your story budget is {story_budget}. After completing that many story outcomes (ship legs included): write `sessions/drain.md` with `continuation: true` — stories completed, burn so far, the remaining queue — then spawn your successor `python .agents/skills/cdo-batch/scripts/spawn-dispatch.py --orchestration-dir "{orch}" --project-root "{project_root}" --local --kind dispatch --keys {{remaining}} --continuation` (recompute via ready-set first — newly confirmed keys fold in). Keep your own `locks/{drain_id}.lock` until the successor's `g-*` marker lands — no double-drain window, no dropped queue — then release it and exit. A queue shorter than the budget behaves exactly as today.