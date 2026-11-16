---
name: bmad-bus-legal-team
description: Router for the legal-team module imported from BMAD-CYBERSEC — 13 agents, 7 workflows.
---

# Legal Team - Multi-Jurisdictional Legal Advisory

Imported by srm-sync from `BMAD-CYBERSEC` (`src/legal-team`). This folder is a verbatim copy of the source module — agents, workflows, tasks, templates and config keep their original relative layout.

Each agent and workflow is also installed as an individual skill.

## Agents (13)

| Skill | Persona |
|---|---|
| `bmad-bus-legal-team-advocate` | Advocate — Litigation Strategist - Civil Dispute Resolution Expert |
| `bmad-bus-legal-team-baltic` | Baltic — Estonia Corporate Counsel - e-Residency and Digital Business Specialist |
| `bmad-bus-legal-team-castile` | Castile — Spain Corporate Counsel - Spanish Business Law Specialist |
| `bmad-bus-legal-team-charter` | Charter — Corporate Governance Counsel - Board and Compliance Specialist |
| `bmad-bus-legal-team-counsel` | Counsel — General Counsel - Legal Team Director |
| `bmad-bus-legal-team-covenant` | Covenant — Contract Specialist - Cross-Jurisdictional Contract Expert |
| `bmad-bus-legal-team-deed` | Deed — Real Estate Counsel - Property and Lease Specialist |
| `bmad-bus-legal-team-europa` | Europa — EU Counsel - European Union Law Specialist |
| `bmad-bus-legal-team-gremio` | Gremio — Spain Labor Law Counsel - Spanish Employment Specialist |
| `bmad-bus-legal-team-iberia` | Iberia — Spain Civil Law Counsel - Spanish Civil Code Specialist |
| `bmad-bus-legal-team-insignia` | Insignia — IP Counsel - Intellectual Property Specialist |
| `bmad-bus-legal-team-liberty` | Liberty — US Counsel - American Corporate &amp; Civil Law Specialist |
| `bmad-bus-legal-team-tribute` | Tribute — Tax Counsel - Cross-Jurisdictional Tax Specialist |

## Workflows (7)

| Skill | Description |
|---|---|
| `bmad-bus-legal-team-contract-drafting` | Workflow 'contract-drafting' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-contract-review` | Workflow 'contract-review' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-corporate-formation` | Workflow 'corporate-formation' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-cross-border-matter` | Workflow 'cross-border-matter' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-dispute-strategy` | Workflow 'dispute-strategy' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-legal-matter-intake` | Workflow 'legal-matter-intake' imported from BMAD-CYBERSEC:legal-team |
| `bmad-bus-legal-team-tax-planning` | Workflow 'tax-planning' imported from BMAD-CYBERSEC:legal-team |

## Note

Agents may reference `{project-root}/_bmad/<module>/config.yaml` at runtime — if a mapped agent asks for config that doesn't exist, register the module's config or provide values directly.
