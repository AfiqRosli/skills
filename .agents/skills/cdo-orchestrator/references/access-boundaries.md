# Access Boundaries for Marshal

Load on every activation — the deny zones are load-bearing, especially on
unattended wakes. These are contract, not memory; they ship with the skill.

## Read Access

- `{orchestration_dir}/**`           # all orchestration artifacts
- sprint state archives            # e.g. `_bmad-output/implementation-artifacts/sprint-status-*.yaml`
- story specs                      # `{story_location}/**`
- per-story devlogs                # `{devlog_dir}/**` (default `docs/orchestration/devlog/**`)
- `{project-root}/_bmad/**`         # config, manifests (read-only)
- backlog sources                  # per `{backlog_map}` in config

## Write Access

- `{orchestration_dir}/**`          # ledgers, checklists, doctrine, intent, patterns, logs, handover, journals

## Deny Zones

- production databases — never, structurally (no prod creds in pipeline)
- `{project-root}/.env*` secrets — read keys only via dept workflows, never print values
- code changes — Marshal directs; dept skills write code
- `{project-root}/_bmad/**` writes — config belongs to setup/the Operator, not the duty officer

## Enforcement layer (13-29)

Drain workers run in isolated git worktrees (`.cdo-work/{drain_id}`, detached `origin/{lane}`) — these deny zones are now **path-level, not just prompt-level**: anything outside the worktree is off-limits to the worker's file ops except the absolute `docs/orchestration/` path pinned in the prompt, which always resolves to the main checkout.
