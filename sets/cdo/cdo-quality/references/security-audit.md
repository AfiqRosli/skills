# Capability: security-audit — delegated wholesale to BMAD-CYBERSEC

Security review is a specialist domain. This department never re-implements it — it routes to the synced `bmad-bus-cybersec-team-*` skills, collects their findings, and lands them in the org's machinery.

## Input

`{key}` — audit the story's surface: read its card (`alignment/**/{key}.md`) → `touches:`/scope derive the surface → pick the delegate.
`{surface}` — a literal surface name from the table's left column — audit a system area without a story.

## Delegate table

Pick the audit skill that matches the surface:

| Surface | Delegate |
|---|---|
| architecture/design-level | `bmad-bus-cybersec-team-security-architecture-review` |
| web application | `bmad-bus-cybersec-team-web-app-security-testing` |
| API surface | `bmad-bus-cybersec-team-api-security-expert` |
| LLM/AI features | `bmad-bus-cybersec-team-llm-ai-security-expert` |
| vuln triage flow | `bmad-bus-cybersec-team-vulnerability-management` |
| infrastructure | `bmad-bus-cybersec-team-infrastructure-security-testing` |
| compliance | `bmad-bus-cybersec-team-compliance-audit-prep` |
| broad red-team | `bmad-bus-cybersec-team-penetration-tester` |

Capabilities manifest lists `delegates-when-installed` — check `capabilities.yaml` (or `departments.cdo-quality`) for what setup probed. Missing delegates → report the audit can't run and which skill is needed (don't hand-rolled security review as a substitute — a fake audit is worse than none).

## Findings intake

Audit findings land on the story/item's ledger record (`--findings`). **Critical/high-severity findings are LINE_STOP-class** — additionally drop a `signals/line-stop-{key}.md` file so `cdo-watch intake` folds it into Marshal's queue; security fires don't wait for a checklist review.

## Verdict shape

`{key, surface, delegate_used, findings: [{sev, summary, ref}], verdict: clean|findings|blocked}` — JSON for headless callers.
