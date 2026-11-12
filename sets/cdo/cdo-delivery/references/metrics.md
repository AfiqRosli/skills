# Capability: metrics — the takt scoreboard

Delivery-ops health read from the ledger, not vibes:

```bash
uv run ./scripts/metrics.py --orchestration-dir "{orch}"
```

## Reading the digest

- `cycle_minutes` — step_started → last-finding timestamp; the honest "how long does a story take"
- `attempts.avg` — re-dispatch burn; >1.5 means alignment or pipeline is bleeding
- `quarantine_rate` — fraction of touched work that ended in quarantine; high rate says drafts are being confirmed too loosely
- `throughput_24h` — completed in the last day
- `autonomy` block — streak visibility for the earned-autonomy question

Use in status briefings (Marshal's Operator brief consumes this), and as a leading indicator: rising cycle time + rising attempts = pipeline degradation worth a signal, not a shrug.

## Output

metrics.py JSON verbatim — the digest IS the deliverable.

