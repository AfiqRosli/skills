# Capability: version-upgrade — sprint boundary migration

The sprint-boundary leg of release bookkeeping. When the Operator starts a new sprint, delegate wholesale to `cdo-version-upgrade` — it owns the deterministic partition + renumber (non-done stories → the new sprint's epics doc, sprint yaml, and spec folder; terminal stories stay archived). Invoke, don't re-implement. Missing `cdo-version-upgrade` → report the gap; don't attempt the migration by hand.

**Boundary doctrine:** a production deploy is a *deploy* boundary — `cdo-version-change-for-production` tags the real date and leaves sprint artifacts untouched. A sprint boundary is *this* capability — Operator-initiated only, never a deploy side-effect. Two boundaries, two skills; routing wrong corrupts both ledgers.

**Headless (`-H`):** `cdo-platform version-upgrade -H` only runs when the caller supplies `--new-version {sprint-id}` plus `--yes` (optional `--epic-order`, `--reclassify`) — the delegate then runs its scripted chain non-interactively and returns its JSON result verbatim. Missing either input → `{"status": "blocked", "reason": "sprint migration requires an explicit new-version and confirmation"}`; never prompt.

## Output

The `cdo-version-upgrade` summary report verbatim (old→new version pair, story counts, reclassifications, flags) — sprint transitions are Operator-visible events, so surface it whole rather than paraphrasing.
