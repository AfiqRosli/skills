<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
- 2026-10-19 — pre-deploy gate noted: cloud keeps pushing (clone isolation); local drains land unpushed on cdo-lane
- 2026-11-04 — extraction goes manual: workers never spawn a-* sessions (academy is Marshal/Operator-invoked only) — push only needs to precede spawn-review
-->

After each story's release: `git add -A && git commit -m "cdo {{key}}: <terminal status>" && git push origin HEAD:{lane}` — verify BEFORE the push; unverified code never lands on the lane. Push refused (someone pushed meanwhile) → `git fetch && git rebase origin/{lane}`, push again. Push before every spawn-review too — detached sessions clone `origin/{lane}` and must see your state.

(Cloud is the exception to the org's pre-deploy gating — a clone's only way home is pushing. Local drains land on the local-only `cdo-lane` ref instead and wait for the Operator's pre-deploy sign-off; don't carry this step's push habit anywhere else.)
