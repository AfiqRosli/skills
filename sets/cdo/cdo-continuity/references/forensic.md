# Capability: forensic — assemble the case file

Post-mortem on a killed, failed, or weird story. The file gathers itself — the analysis is yours.

## Flow

```bash
uv run ./scripts/case-file.py --orchestration-dir "{orch}" {key}
```

Writes `learning/cases/{key}-{date}.md` with the timeline evidence collected; you fill the **Analysis** section: what happened, the root cause (not the proximate), and — this is the point — **what doctrine changes**.

Feed the doctrine change back to `doctrine.md`: forensics that don't update doctrine are history essays. A case file is complete when its lesson is journaled.

## Escalation

Evidence pointing beyond a story bug — a systemic pattern, a repeated failure mode across keys — is an escalation finding: journal it to doctrine as a standing-policy candidate and flag the checklist for the Operator. When the failure smells like an incident (unauthorized state changes, destructive ops), hand off to `incident`.

## Output

`{case_file, timeline}` — script JSON verbatim + journaled doctrine entry id.

