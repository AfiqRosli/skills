---
name: bmad-bus-cybersec-team
description: Router for the cybersec-team module imported from BMAD-CYBERSEC — 15 agents, 13 workflows.
---

# Cybersecurity Team (Cybersec-Team)

Imported by srm-sync from `BMAD-CYBERSEC` (`src/cybersec-team`). This folder is a verbatim copy of the source module — agents, workflows, tasks, templates and config keep their original relative layout.

Each agent and workflow is also installed as an individual skill.

## Agents (15)

| Skill | Persona |
|---|---|
| `bmad-bus-cybersec-team-api-security-expert` | Gateway — API &amp; Integration Security Specialist |
| `bmad-bus-cybersec-team-blockchain-security-expert` | Ledger — Web3 &amp; Smart Contract Security Specialist |
| `bmad-bus-cybersec-team-blue-team-lead` | Shield — Defensive Security Operations Leader |
| `bmad-bus-cybersec-team-cloud-security-specialist` | Nimbus — Cloud Security Architect |
| `bmad-bus-cybersec-team-compliance-guardian` | Sentinel — Risk & Regulatory Compliance Expert |
| `bmad-bus-cybersec-team-forensic-investigator` | Trace — Digital Forensics & Evidence Analyst |
| `bmad-bus-cybersec-team-incident-commander` | Phoenix — Incident Response Lead |
| `bmad-bus-cybersec-team-llm-ai-security-expert` | Oracle — AI &amp; Machine Learning Security Specialist |
| `bmad-bus-cybersec-team-mobile-security-expert` | Phantom — Mobile Application Security Specialist |
| `bmad-bus-cybersec-team-penetration-tester` | Spectre — Offensive Security Expert |
| `bmad-bus-cybersec-team-security-architect` | Bastion — Defense & Infrastructure Design |
| `bmad-bus-cybersec-team-soc-analyst` | Watchman — Security Operations Center Analyst |
| `bmad-bus-cybersec-team-social-engineer` | Ghost — Social Engineering Specialist |
| `bmad-bus-cybersec-team-threat-analyst` | Cipher — Threat Intelligence Specialist |
| `bmad-bus-cybersec-team-web-app-security-expert` | Weaver — Web Application Security Specialist |

## Workflows (13)

| Skill | Description |
|---|---|
| `bmad-bus-cybersec-team-blockchain-security-assessment` | Workflow 'blockchain-security-assessment' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-cloud-security-assessment` | Workflow 'cloud-security-assessment' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-compliance-audit-prep` | Workflow 'compliance-audit-prep' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-incident-response-playbook` | Workflow 'incident-response-playbook' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-infrastructure-security-testing` | Workflow 'infrastructure-security-testing' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-mobile-security-testing` | Workflow 'mobile-security-testing' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-network-assessment` | Workflow 'network-assessment' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-security-architecture-review` | Workflow 'security-architecture-review' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-security-awareness-training` | Workflow 'security-awareness-training' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-threat-modeling` | Workflow 'threat-modeling' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-virtual-ciso-consulting` | Workflow 'virtual-ciso-consulting' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-vulnerability-management` | Workflow 'vulnerability-management' imported from BMAD-CYBERSEC:cybersec-team |
| `bmad-bus-cybersec-team-web-app-security-testing` | Workflow 'web-app-security-testing' imported from BMAD-CYBERSEC:cybersec-team |

## Note

Agents may reference `{project-root}/_bmad/<module>/config.yaml` at runtime — if a mapped agent asks for config that doesn't exist, register the module's config or provide values directly.
