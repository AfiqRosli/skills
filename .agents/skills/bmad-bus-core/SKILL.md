---
name: bmad-bus-core
description: Router for the core module imported from BMAD-CYBERSEC — 2 agents, 7 workflows.
---

# BMAD Core Infrastructure

Imported by srm-sync from `BMAD-CYBERSEC` (`src/core`). This folder is a verbatim copy of the source module — agents, workflows, tasks, templates and config keep their original relative layout.

Each agent and workflow is also installed as an individual skill.

## Agents (2)

| Skill | Persona |
|---|---|
| `bmad-bus-core-abdul` | Abdul — Master Project Manager - Cross-Module Orchestrator |
| `bmad-bus-core-bmad-master` | BMad Master — Bmad Master |

## Workflows (7)

| Skill | Description |
|---|---|
| `bmad-bus-core-advanced-elicitation` | Workflow 'advanced-elicitation' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-brainstorming` | Workflow 'brainstorming' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-cross-module` | Workflow 'cross-module' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-intelligent-routing` | Workflow 'intelligent-routing' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-party-mode` | Workflow 'party-mode' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-project-manager` | Workflow 'project-manager' imported from BMAD-CYBERSEC:core |
| `bmad-bus-core-team-orchestration` | Workflow 'team-orchestration' imported from BMAD-CYBERSEC:core |

## Note

Agents may reference `{project-root}/_bmad/<module>/config.yaml` at runtime — if a mapped agent asks for config that doesn't exist, register the module's config or provide values directly.
