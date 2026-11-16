---
name: bmad-bus-strategy-team
description: Router for the strategy-team module imported from BMAD-CYBERSEC — 14 agents, 16 workflows.
---

# Strategic Advisory Team

Imported by srm-sync from `BMAD-CYBERSEC` (`src/strategy-team`). This folder is a verbatim copy of the source module — agents, workflows, tasks, templates and config keep their original relative layout.

Each agent and workflow is also installed as an individual skill.

## Agents (14)

| Skill | Persona |
|---|---|
| `bmad-bus-strategy-team-communications-director` | Giuseppe — Public Messaging & Media Strategy |
| `bmad-bus-strategy-team-debate-coach` | Cicero — Argumentation & Rhetoric Master |
| `bmad-bus-strategy-team-ethics-advisor` | Sophia — Political Ethics & Values Counsel |
| `bmad-bus-strategy-team-policy-analyst` | Augustus — Evidence-Based Policy Expert |
| `bmad-bus-strategy-team-political-strategist` | Magnus — Campaign & Political Strategy |
| `bmad-bus-strategy-team-stakeholder-mediator` | Geneva — Negotiation & Consensus Builder |
| `bmad-bus-strategy-team-the-conservative` | Burke — The Conservative - Guardian of Tradition |
| `bmad-bus-strategy-team-the-liberator` | Charles — The Liberator - Moral Transformer |
| `bmad-bus-strategy-team-the-master-strategist` | Sun — The Master Strategist - Supreme Strategist |
| `bmad-bus-strategy-team-the-principled-commander` | Jean-Luc — The Principled Commander - Diplomat Captain |
| `bmad-bus-strategy-team-the-realist` | Niccolo — The Realist - Master of Realpolitik |
| `bmad-bus-strategy-team-the-revolutionary` | Maximilien — The Revolutionary - Agent of Change |
| `bmad-bus-strategy-team-the-strategist-warrior` | Musashi — The Strategist-Warrior - Master of Timing |
| `bmad-bus-strategy-team-the-technocrat` | Lee — The Technocrat - Builder of Systems |

## Workflows (16)

| Skill | Description |
|---|---|
| `bmad-bus-strategy-team-board-presentation-prep` | Workflow 'board-presentation-prep' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-board-relations-management` | Workflow 'board-relations-management' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-competitive-warfare` | Workflow 'competitive-warfare' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-conflict-resolution` | Workflow 'conflict-resolution' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-corporate-political-game` | Workflow 'corporate-political-game' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-crisis-response-planning` | Workflow 'crisis-response-planning' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-ethical-dilemma-resolution` | Workflow 'ethical-dilemma-resolution' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-leadership-philosophy` | Workflow 'leadership-philosophy' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-leadership-transition-planning` | Workflow 'leadership-transition-planning' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-ma-due-diligence` | Workflow 'ma-due-diligence' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-performance-review-preparation` | Workflow 'performance-review-preparation' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-policy-development` | Workflow 'policy-development' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-political-risk-assessment` | Workflow 'political-risk-assessment' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-stakeholder-negotiation-prep` | Workflow 'stakeholder-negotiation-prep' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-strategic-decision-workshop` | Workflow 'strategic-decision-workshop' imported from BMAD-CYBERSEC:strategy-team |
| `bmad-bus-strategy-team-strategic-planning-session` | Workflow 'strategic-planning-session' imported from BMAD-CYBERSEC:strategy-team |

## Note

Agents may reference `{project-root}/_bmad/<module>/config.yaml` at runtime — if a mapped agent asks for config that doesn't exist, register the module's config or provide values directly.
