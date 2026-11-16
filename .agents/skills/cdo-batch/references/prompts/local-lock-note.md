<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
-->

Final act: remove `locks/{drain_id}.lock` — the spawn-time marker that held your queue against double-dispatch. Your per-key claims did the real locking; the janitor only clears it on the 24h horizon if you die.