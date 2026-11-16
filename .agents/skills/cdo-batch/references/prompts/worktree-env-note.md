<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
- 2026-10-23 — stale base doc: worktrees detach at refs/heads/cdo-lane (local integration tip), not origin/{lane}
-->

You run in an isolated git worktree at `{work_dir}` — detached at `refs/heads/cdo-lane` (the local integration tip — landed-but-unpushed work lives there), not the shared checkout. Deny zones are filesystem-real here: everything outside this worktree is off-limits. Orchestration state (`docs/orchestration/`, devlogs, locks, sessions) lives in the MAIN checkout at the absolute path `{orch}` — always use it verbatim; never touch the worktree's own copy of `docs/orchestration/`.