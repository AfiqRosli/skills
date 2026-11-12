<!-- cdo-prompt v1 — extracted verbatim from spawn-dispatch.py
changelog (one line per edit: date — key/cause):
- 2026-10-18 — 13-30 extracted verbatim (drain-body carries the 13-27 continuation clause)
-->

The drain lock `locks/{drain_id}.lock` lives on Marshal's checkout, not in your clone — your pushed `sessions/drain.md` is its expiry signal; the janitor clears it.