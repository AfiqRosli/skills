---
name: bmad-bus-intel-team
description: Router for the intel-team module imported from BMAD-CYBERSEC — 11 agents, 19 workflows.
---

# Intelligence Operations Team

Imported by srm-sync from `BMAD-CYBERSEC` (`src/intel-team`). This folder is a verbatim copy of the source module — agents, workflows, tasks, templates and config keep their original relative layout.

Each agent and workflow is also installed as an individual skill.

## Agents (11)

| Skill | Persona |
|---|---|
| `bmad-bus-intel-team-corporate-intel-specialist` | Proxy — Corporate Intelligence Specialist |
| `bmad-bus-intel-team-dark-web-analyst` | Shadow — Dark Web Intelligence Analyst |
| `bmad-bus-intel-team-domain-intel-specialist` | Resolver — Network & Domain Intelligence Specialist |
| `bmad-bus-intel-team-field-operative` | Specter — Field Operations Specialist |
| `bmad-bus-intel-team-geospatial-analyst` | Atlas — Geospatial Intelligence Analyst |
| `bmad-bus-intel-team-humint-specialist` | Viper — Human Intelligence Specialist |
| `bmad-bus-intel-team-osint-lead` | Vector — Intelligence Operations Director |
| `bmad-bus-intel-team-sigint-specialist` | Sigil — Signals Intelligence Specialist |
| `bmad-bus-intel-team-social-media-analyst` | Echo — Social Media Intelligence Analyst |
| `bmad-bus-intel-team-technical-researcher` | Probe — Technical Intelligence Researcher |
| `bmad-bus-intel-team-threat-actor-profiler` | Dossier — Threat Actor Profiler |

## Workflows (19)

| Skill | Description |
|---|---|
| `bmad-bus-intel-team-approach-vector` | Workflow 'approach-vector' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-attribution-chain` | Workflow 'attribution-chain' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-breach-archaeology` | Workflow 'breach-archaeology' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-campaign-ai` | Workflow 'campaign-ai' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-campaign-planner-org` | Workflow 'campaign-planner-org' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-campaign-planner-person` | Workflow 'campaign-planner-person' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-counter-intel-audit` | Workflow 'counter-intel-audit' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-digital-necromancy` | Workflow 'digital-necromancy' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-doppelganger-hunt` | Workflow 'doppelganger-hunt' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-flash-assessment` | Workflow 'flash-assessment' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-ground-truth` | Workflow 'ground-truth' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-infrastructure-genealogy` | Workflow 'infrastructure-genealogy' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-operation-mosaic` | Workflow 'operation-mosaic' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-pattern-of-life` | Workflow 'pattern-of-life' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-signal-landscape` | Workflow 'signal-landscape' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-spider-web` | Workflow 'spider-web' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-the-synthesis` | Workflow 'the-synthesis' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-threat-constellation` | Workflow 'threat-constellation' imported from BMAD-CYBERSEC:intel-team |
| `bmad-bus-intel-team-tripwire` | Workflow 'tripwire' imported from BMAD-CYBERSEC:intel-team |

## Note

Agents may reference `{project-root}/_bmad/<module>/config.yaml` at runtime — if a mapped agent asks for config that doesn't exist, register the module's config or provide values directly.
