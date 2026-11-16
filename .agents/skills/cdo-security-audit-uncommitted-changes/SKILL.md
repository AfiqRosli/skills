---
name: cdo-security-audit-uncommitted-changes
description: Full 360 security audit of uncommitted changes using BMAD cybersec agents — CDO-owned copy invoked by the delivery org's pipeline
---

# Code Security Audit — Uncommitted Changes

## Overview

This workflow performs a comprehensive 360-degree security audit of git uncommitted changes. It deploys specialised BMAD cybersec agents to analyse changes from multiple security domains — OWASP Top 10, zero-trust architecture, threat modelling, API security, and more. The goal is to identify every security vulnerability, misconfiguration, and risk before code reaches production.

## Prerequisites

1. **Git status check** — Identify all uncommitted changes
2. **Change categorisation** — Group changes by security domain relevance
3. **Agent selection** — Match changed code to appropriate cybersec agents
4. **Audit scope definition** — Define boundaries and depth of audit

## Pipeline Invocation (cdo-code-e2e)

When invoked under `cdo-code-e2e` step 6 — usually inside a subagent — the invocation envelope supplies the changed-file list, the diff scope, the story spec, and a `checks_status` field (`not-run` when the step-8 health check hasn't run yet). Apply these bounds:

- **Skip Phase 2.3/2.4 automated checks when `checks_status` is `not-run`** — eslint/`tsc` haven't run yet; running them here duplicates step 8's authoritative pass. If the envelope carries a completed health-check result instead, the same bound applies — those results are already authoritative. `bun audit` + secret scan still run (security-specific).
- **Deploy Phase 3 agents as parallel subagents when invoked directly; inside a pipeline subagent — which cannot spawn subagents — run each agent's checklist as sequential in-context passes** over the same diff. Same agents, same checklists, same contract: each returns ONLY a compact verdict `{agent, findings: [{id, severity, domain, file, line, title, remediation}], verdict}`; full prose reports are written to `<devlog_dir>/audit-security.md`, not returned.
- **Phases 1–5 only** — Phase 6 remediation and regression testing are the orchestrator's step-7 fix loop, not this skill's. End at the report.
- Standalone invocation (no envelope): run all phases as written below.

## Workflow Phases

### Phase 1: Change Discovery & Triage

#### Step 1: Identify Uncommitted Changes

```bash
# Get all modified files (staged + unstaged)
git diff HEAD --name-only

# Get detailed diff for analysis
git diff HEAD

# Categorise by file type
git diff HEAD --name-only | grep -E '\.vue$'  # Frontend components
git diff HEAD --name-only | grep -E '\.ts$'   # TypeScript (stores, utils, server, composables)
git diff HEAD --name-only | grep -E '\.sql$'  # Database migrations
git diff HEAD --name-only | grep -E '\.ya?ml$' # Config files
git diff HEAD --name-only | grep -E '\.env'   # Environment files
```

#### Step 2: Security Domain Categorisation

Map each changed file to relevant security domains:

| File Type | Security Domains | Primary Agents |
|---|---|---|
| `components/**/*.vue` | XSS, CSRF, DOM manipulation, client-side state | `web-app-security-expert`, `frontend-security` |
| `server/**/*.ts` | API security, injection, auth bypass, rate limiting | `api-security-expert`, `web-app-security-expert` |
| `stores/**/*.ts` | State manipulation, data exposure, auth flows | `web-app-security-expert`, `security-architect` |
| `composables/**/*.ts` | Client-side logic, reactivity exploits | `web-app-security-expert` |
| `utils/**/*.ts` | Input validation, sanitisation, crypto | `web-app-security-expert`, `security-architect` |
| `interfaces/**/*.ts` | Type safety, data contracts | `security-architect` |
| `drizzle/**/*.sql` | SQL injection, migration safety | `web-app-security-expert` |
| `nuxt.config.ts` | Security headers, CSP, CORS | `security-architect`, `cloud-security-specialist` |
| `.env*` | Secret exposure, credential management | `security-architect`, `compliance-guardian` |
| `middleware/**/*.ts` | Auth middleware, route protection | `security-architect`, `api-security-expert` |
| `auth*.ts` | Authentication, session management | `api-security-expert`, `security-architect` |
| `netlify.toml` | Deploy security, access control | `cloud-security-specialist`, `security-architect` |

#### Step 3: Generate Audit Brief

Create a structured audit brief for agent deployment:

```markdown
## Security Audit Brief

### Changed Files
- [list all changed files with their security domain mapping]

### Change Summary
- [brief description of what the changes do]

### Attack Surface Assessment
- New endpoints? [yes/no]
- New auth flows? [yes/no]
- New data exposed to client? [yes/no]
- New external dependencies? [yes/no]
- Database schema changes? [yes/no]
- Configuration changes? [yes/no]
- File upload/download? [yes/no]
- Crypto/hash changes? [yes/no]
```

---

### Phase 2: Automated Security Scans

#### Step 2.1: Dependency Vulnerability Check

```bash
# Check for known vulnerabilities in dependencies
bun audit

# Check lockfile integrity
git diff HEAD -- bun.lock
```

#### Step 2.2: Secret Scanning

```bash
# Scan for hardcoded secrets, API keys, tokens
git diff HEAD | grep -iE "(api[_-]?key|secret|token|password|jwt|private[_-]?key|aws|stripe|sendgrid|resend)" | grep -v "test" | grep -v "\.example"

# Check for .env file changes
git diff HEAD -- .env*
```

#### Step 2.3: ESLint Security Rules

```bash
# Run ESLint with security-focused rules
bunx eslint --ext .ts,.vue,.js \
  --rule '{"no-eval": "error", "no-implied-eval": "error"}' \
  [changed-files]
```

#### Step 2.4: TypeScript Strict Security Check

```bash
# Type check for null/undefined safety
bunx tsc --noEmit --strict
```

---

### Phase 3: Agent-Deployed Deep Security Audit

> **Critical:** Each agent below must re-read the actual changed code line-by-line. Automated scans catch syntax-level issues; agents catch logic, pattern, and architectural vulnerabilities.

**Deployment:** launch every applicable agent as a **parallel subagent** (they are independent read-only passes over the same diff). Each returns a compact JSON verdict — `{agent, findings: [{id, severity, domain, file, line, title, remediation}], verdict}` — and writes its full report to file, not to chat. Skip an agent entirely (don't deploy it) when its domain has no changed files — e.g., no `server/**` changes → no Gateway; no infra/config changes → no Nimbus.

#### Agent 1: Web Application Security Expert (Weaver)

**Skill:** `bmad-cybersec-agent-web-app-security-expert`

**Focus:** OWASP Top 10 (2021) compliance for all changed code

Deploy Weaver to audit:

- [ ] **A01 — Broken Access Control**: Are authorisation checks present on every new server route? Are area/thing ownership checks enforced before returning data? Can a user access another user's things via ID manipulation?
- [ ] **A02 — Cryptographic Failures**: Are any new crypto operations using weak algorithms? Are passwords/tokens hashed with bcrypt/argon2? Is JWT secret stored securely? Are any secrets hardcoded?
- [ ] **A03 — Injection**: Are all database queries using parameterised Drizzle ORM? Any raw SQL strings? Are user inputs validated and sanitised before use in queries?
- [ ] **A04 — Insecure Design**: Are new features designed with security by default? Are there fail-open patterns? Is least-privilege enforced?
- [ ] **A05 — Security Misconfiguration**: Are security headers present? Is CORS configured correctly? Are debug endpoints disabled in production? Is `v-html` avoided?
- [ ] **A06 — Vulnerable & Outdated Components**: Are any new dependencies added? Are they pinned to safe versions? Are there known CVEs?
- [ ] **A07 — Identification & Authentication Failures**: Are session checks present? Can auth be bypassed? Are rate limits enforced on auth endpoints?
- [ ] **A08 — Software & Data Integrity Failures**: Are CI/CD pipelines protected? Are dependencies verified? Is there unsigned code?
- [ ] **A09 — Security Logging & Monitoring Failures**: Are security events logged? Are failed auth attempts tracked? Is PII excluded from logs?
- [ ] **A10 — Server-Side Request Forgery (SSRF)**: Do any new features make external HTTP requests? Are URLs validated? Are internal IPs blocked?

#### Agent 2: API Security Expert (Gateway)

**Skill:** `bmad-cybersec-agent-api-security-expert`

**Focus:** API-specific security for all `server/**/*.ts` changes

Deploy Gateway to audit:

- [ ] **Authentication**: Is every new endpoint behind auth middleware? Are session tokens validated? Are API keys checked?
- [ ] **Authorisation**: Is object-level authorisation enforced? Can users access other users' resources? Are IDOR vulnerabilities present?
- [ ] **Input Validation**: Are all request bodies validated with Elysia `t.Object()` schemas? Are query params validated? Are path params sanitised?
- [ ] **Rate Limiting**: Are new endpoints covered by rate limiting? Are auth endpoints more strictly limited?
- [ ] **Error Handling**: Do error responses leak stack traces? Are internal errors masked? Are status codes correct?
- [ ] **CORS**: Is CORS configuration appropriate? Are credentials allowed only for trusted origins?
- [ ] **GraphQL/REST**: Are batch attacks possible? Are query depth limits set? Are field suggestions disabled?
- [ ] **Token Security**: Are JWTs validated server-side? Are refresh tokens rotated? Are tokens stored securely (httpOnly cookies)?

#### Agent 3: Security Architect (Bastion)

**Skill:** `bmad-cybersec-agent-security-architect`

**Focus:** Zero-trust architecture, defence-in-depth, threat modelling

Deploy Bastion to audit:

- [ ] **Zero-Trust Principles**:
  - Never trust, always verify — are all requests authenticated regardless of source?
  - Least-privilege access — do new features request only the permissions they need?
  - Assume breach — if an attacker gains access, what's the blast radius of these changes?
  - Explicit verification — are trust decisions based on multiple signals (identity, device, context)?
  - Micro-segmentation — are new features isolated? Can a compromise in one area spread?
- [ ] **Defence-in-Depth**:
  - Are there multiple layers of security (validation, auth, rate limit, logging)?
  - If one layer fails, does the next layer catch the attack?
  - Are fail-secure (deny by default) patterns used?
- [ ] **Threat Modelling (STRIDE)**:
  - **S**poofing: Can an attacker impersonate a user or service?
  - **T**ampering: Can data be modified in transit or at rest?
  - **R**epudiation: Can actions be denied? Are they logged?
  - **I**nformation Disclosure: Can data leak to unauthorised parties?
  - **D**enial of Service: Can the new code be exploited to crash the service?
  - **E**levation of Privilege: Can a user gain higher access than intended?
- [ ] **Architecture Review**:
  - Are new components placed in the correct trust zone?
  - Are trust boundaries clearly defined?
  - Is sensitive data encrypted at rest and in transit?
  - Are secrets managed via environment variables, not hardcoded?

#### Agent 4: Cloud Security Specialist (Nimbus)

**Skill:** `bmad-cybersec-agent-cloud-security-specialist`

**Focus:** Deployment security, configuration, infrastructure

Deploy Nimbus to audit:

- [ ] **Deploy Configuration**: Is `netlify.toml` secure? Are deploy hooks protected? Are environment variables set via Netlify dashboard, not in code?
- [ ] **Security Headers**: Are CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy headers configured?
- [ ] **TLS/SSL**: Is HTTPS enforced? Are redirects from HTTP to HTTPS present?
- [ ] **CDN/Edge Security**: Are edge functions secured? Is DDoS protection active?
- [ ] **Environment Separation**: Are dev/staging/prod environments isolated? Are prod secrets different from dev?
- [ ] **Logging & Monitoring**: Are security events logged to a centralised system? Are alerts configured for suspicious activity?

#### Agent 5: LLM/AI Security Expert (Oracle) — Conditional

**Skill:** `bmad-cybersec-agent-llm-ai-security-expert`

**Deploy only if:** Changes involve AI/LLM features, prompt handling, or AI API calls.

Deploy Oracle to audit:

- [ ] **Prompt Injection**: Are user inputs sanitised before being sent to LLMs? Are system prompts protected?
- [ ] **Data Leakage**: Can LLM responses leak sensitive data from the context?
- [ ] **Model Security**: Are model outputs validated before use? Are hallucinations handled safely?
- [ ] **AI Governance**: Are AI features logged? Are there guardrails on outputs?

#### Agent 6: Compliance Guardian (Sentinel) — Conditional

**Skill:** `bmad-cybersec-agent-compliance-guardian`

**Deploy only if:** Changes involve user data, authentication, or data processing.

Deploy Sentinel to audit:

- [ ] **GDPR**: Are user data changes compliant? Is data minimisation practised? Are deletion requests honoured?
- [ ] **Data Retention**: Are retention policies enforced? Is old data purged?
- [ ] **Audit Trail**: Are security-relevant actions logged with timestamp, user ID, and action?
- [ ] **Privacy by Design**: Are new features designed with privacy as a default?

---

### Phase 4: Cross-Domain Security Analysis

#### Step 1: Attack Chain Analysis

Trace multi-step attack paths through the changed code:

- [ ] **Chain 1 — Auth bypass → Data exfiltration**: Can an unauthenticated user reach a new endpoint that returns sensitive data?
- [ ] **Chain 2 — IDOR → Privilege escalation**: Can a user manipulate IDs to access another user's data, then use that data to escalate privileges?
- [ ] **Chain 3 — XSS → Session hijack**: Can user input be rendered unsafely, enabling script injection that steals session tokens?
- [ ] **Chain 4 — SSRF → Internal access**: Can a user-supplied URL cause the server to make requests to internal services?
- [ ] **Chain 5 — Race condition → Data corruption**: Can concurrent requests cause inconsistent state or bypass checks?
- [ ] **Chain 6 — Client-side trust → Server bypass**: Does the server validate data that the client "guarantees", or does it trust the client?

#### Step 2: Data Flow Analysis

Trace how data flows through the changed code:

- [ ] **Input → Storage**: Are all user inputs validated before database writes? Is SQL injection impossible via Drizzle ORM parameterisation?
- [ ] **Storage → Output**: Are all database reads checked for ownership before returning to the client? Is data scoped to the user's organisation?
- [ ] **Client → Server**: Are all API calls authenticated? Are request bodies schema-validated?
- [ ] **Server → Client**: Are error messages sanitised? Do responses leak internal state, stack traces, or other users' data?

#### Step 3: State & Session Security

- [ ] **Session fixation**: Can session IDs be forced or reused?
- [ ] **CSRF**: Are state-changing operations protected against cross-site request forgery?
- [ ] **Race conditions**: Can concurrent operations cause security bypasses?
- [ ] **State manipulation**: Can client-side state (Vue refs, Pinia stores) be manipulated to bypass server-side checks?

---

### Phase 5: Security Audit Report

#### Report Template

```markdown
# Security Audit Report — [Date]

## Audit Scope
- **Changed Files**: [count] files
- **Security Domains**: [list]
- **Agents Deployed**: [list]
- **Audit Duration**: [duration]

## Executive Summary
- **Critical Vulnerabilities**: [count]
- **High Vulnerabilities**: [count]
- **Medium Vulnerabilities**: [count]
- **Low Vulnerabilities**: [count]
- **Informational**: [count]

## Findings

### Critical (Must Fix Before Commit)

| ID | Title | Domain | File | Line | Agent | Description | Remediation |
|---|---|---|---|---|---|---|---|
| C-1 | [title] | OWASP A01 | [file] | [line] | [agent] | [description] | [fix] |

### High (Should Fix Before Commit)

| ID | Title | Domain | File | Line | Agent | Description | Remediation |
|---|---|---|---|---|---|---|---|
| H-1 | [title] | [domain] | [file] | [line] | [agent] | [description] | [fix] |

### Medium (Should Fix Before Release)

| ID | Title | Domain | File | Line | Agent | Description | Remediation |
|---|---|---|---|---|---|---|---|
| M-1 | [title] | [domain] | [file] | [line] | [agent] | [description] | [fix] |

### Low (Track & Fix)

| ID | Title | Domain | File | Line | Agent | Description | Remediation |
|---|---|---|---|---|---|---|---|
| L-1 | [title] | [domain] | [file] | [line] | [agent] | [description] | [fix] |

### Informational (No Action Required)

| ID | Title | Domain | File | Line | Agent | Notes |
|---|---|---|---|---|---|---|
| I-1 | [title] | [domain] | [file] | [line] | [agent] | [notes] |

## OWASP Top 10 (2021) Compliance

| Category | Status | Findings |
|---|---|---|
| A01 — Broken Access Control | ✅/❌ | [details] |
| A02 — Cryptographic Failures | ✅/❌ | [details] |
| A03 — Injection | ✅/❌ | [details] |
| A04 — Insecure Design | ✅/❌ | [details] |
| A05 — Security Misconfiguration | ✅/❌ | [details] |
| A06 — Vulnerable Components | ✅/❌ | [details] |
| A07 — Auth Failures | ✅/❌ | [details] |
| A08 — Integrity Failures | ✅/❌ | [details] |
| A09 — Logging Failures | ✅/❌ | [details] |
| A10 — SSRF | ✅/❌ | [details] |

## Zero-Trust Compliance

| Principle | Status | Findings |
|---|---|---|
| Never trust, always verify | ✅/❌ | [details] |
| Least-privilege access | ✅/❌ | [details] |
| Assume breach | ✅/❌ | [details] |
| Explicit verification | ✅/❌ | [details] |
| Micro-segmentation | ✅/❌ | [details] |

## STRIDE Threat Model

| Threat | Status | Findings |
|---|---|---|
| Spoofing | ✅/❌ | [details] |
| Tampering | ✅/❌ | [details] |
| Repudiation | ✅/❌ | [details] |
| Information Disclosure | ✅/❌ | [details] |
| Denial of Service | ✅/❌ | [details] |
| Elevation of Privilege | ✅/❌ | [details] |

## Attack Chain Analysis

### Chain 1: [name]
- **Feasibility**: [Low/Medium/High]
- **Impact**: [Low/Medium/High/Critical]
- **Steps**: [trace]
- **Mitigation**: [fix]

## Agent Reports

### Weaver — Web App Security
[Full report from web-app-security-expert agent]

### Gateway — API Security
[Full report from api-security-expert agent]

### Bastion — Security Architecture
[Full report from security-architect agent]

### Nimbus — Cloud Security
[Full report from cloud-security-specialist agent]

## Remediation Priority

1. **Immediate (before commit)**: [list critical + high]
2. **Before release**: [list medium]
3. **Backlog**: [list low]
4. **Monitor**: [list informational]

## Sign-off

- [ ] All critical vulnerabilities resolved
- [ ] All high vulnerabilities resolved or risk-accepted
- [ ] OWASP Top 10 compliance verified
- [ ] Zero-trust principles verified
- [ ] STRIDE threat model reviewed
- [ ] Attack chains traced and mitigated
- [ ] Audit report presented in chat session
```

---

### Phase 6: Remediation & Verification

#### Step 1: Fix Critical & High Vulnerabilities

For each critical/high finding:
1. Implement the remediation specified in the report
2. Re-run the specific agent that found the issue to verify the fix
3. Update the audit report with resolution status

#### Step 2: Regression Security Check

```bash
# Re-run the security-specific scans only — lint/tsc are health-check.py's job
bun audit

# Re-run only tests related to the changed files — never the full suite here
bunx vitest related [changed-files]
```

#### Step 3: Present Audit Report

The audit report is presented directly in the chat session. No file creation is needed.

---

## Quality Gates

### Must Pass (Blocking — Cannot Commit Without These)

- [ ] No critical vulnerabilities found
- [ ] No high vulnerabilities found
- [ ] No hardcoded secrets, API keys, or tokens
- [ ] No SQL injection vectors (all queries parameterised)
- [ ] No XSS vectors (no `v-html`, no unsanitised user input in templates)
- [ ] No broken access control (all endpoints authenticated and authorised)
- [ ] No auth bypass paths
- [ ] Dependency audit clean (no known CVEs)

### Should Pass (Warning — Should Fix Before Release)

- [ ] All OWASP Top 10 categories verified
- [ ] Zero-trust principles verified
- [ ] STRIDE threat model completed
- [ ] No medium vulnerabilities
- [ ] Security headers configured
- [ ] Rate limiting present on all endpoints
- [ ] Error responses don't leak internal state
- [ ] Attack chains traced and documented

### Recommended (Non-blocking)

- [ ] Low vulnerabilities documented
- [ ] Informational findings noted
- [ ] Audit report presented in chat session
- [ ] Remediation plan created for backlog items

---

## Agent Deployment Guide

### How to Deploy Agents

Each agent is invoked via its BMAD skill. The workflow orchestrator should:

1. **Prepare the audit brief** (from Phase 1, Step 3)
2. **Invoke each agent skill** with the audit brief and changed file paths
3. **Collect agent reports** and synthesise into the final audit report
4. **Cross-reference findings** between agents for attack chain analysis

### Agent Invocation Examples

```
# Deploy Weaver for OWASP Top 10 audit
Skill: bmad-cybersec-agent-web-app-security-expert
Context: "Audit these uncommitted changes for OWASP Top 10 compliance: [file list]"

# Deploy Gateway for API security audit
Skill: bmad-cybersec-agent-api-security-expert
Context: "Audit these server-side changes for API security: [file list]"

# Deploy Bastion for zero-trust and architecture audit
Skill: bmad-cybersec-agent-security-architect
Context: "Audit these changes for zero-trust compliance and defence-in-depth: [file list]"

# Deploy Nimbus for cloud/deploy security
Skill: bmad-cybersec-agent-cloud-security-specialist
Context: "Audit deployment and configuration changes for cloud security: [file list]"
```

### Conditional Agent Deployment

| Condition | Agent | Skill |
|---|---|---|
| Changes touch AI/LLM features | Oracle | `bmad-cybersec-agent-llm-ai-security-expert` |
| Changes touch user data or auth | Sentinel | `bmad-cybersec-agent-compliance-guardian` |
| Changes touch mobile components | Phantom | `bmad-cybersec-agent-mobile-security-expert` |
| Changes touch blockchain/Web3 | Ledger | `bmad-cybersec-agent-blockchain-security-expert` |
| Changes touch infrastructure/CI | — | `bmad-cybersec-workflow-infrastructure-security-testing` |

---

## Quick Reference Commands

```bash
# Full audit pipeline
git diff HEAD --name-only                    # 1. Identify changes
bun audit                                     # 2. Dependency check
git diff HEAD | grep -iE "secret|token|key"  # 3. Secret scan
bunx eslint --ext .ts,.vue [files]           # 4. Lint security rules
bunx tsc --noEmit --strict                    # 5. Type safety
bunx vitest run                               # 6. Regression tests

# Report is presented in chat — no file creation needed
```

## Resources

### BMAD Cybersec Agents

| Agent | Skill | Domain |
|---|---|---|
| Weaver | `bmad-cybersec-agent-web-app-security-expert` | OWASP Top 10, web app security |
| Gateway | `bmad-cybersec-agent-api-security-expert` | API security, OAuth, REST/GraphQL |
| Bastion | `bmad-cybersec-agent-security-architect` | Zero-trust, defence-in-depth, threat modelling |
| Nimbus | `bmad-cybersec-agent-cloud-security-specialist` | Cloud security, IAM, infrastructure |
| Oracle | `bmad-cybersec-agent-llm-ai-security-expert` | AI/ML security, prompt injection |
| Sentinel | `bmad-cybersec-agent-compliance-guardian` | GDPR, compliance, audit trails |
| Spectre | `bmad-cybersec-agent-penetration-tester` | Offensive security, pentesting |
| Shield | `bmad-cybersec-agent-blue-team-lead` | Defensive security, detection |
| Cipher | `bmad-cybersec-agent-threat-analyst` | Threat intelligence, MITRE ATT&CK |
| Ghost | `bmad-cybersec-agent-social-engineer` | Social engineering, phishing |
| Watchman | `bmad-cybersec-agent-soc-analyst` | SOC operations, alert triage |
| Trace | `bmad-cybersec-agent-forensic-investigator` | Digital forensics, evidence |
| Phoenix | `bmad-cybersec-agent-incident-commander` | Incident response, crisis management |

### Security Frameworks Referenced

- **OWASP Top 10 (2021)** — Web application security risks
- **Zero-Trust Architecture (NIST SP 800-207)** — Never trust, always verify
- **STRIDE Threat Model** — Spoofing, Tampering, Repudiation, Info Disclosure, DoS, EoP
- **MITRE ATT&CK** — Adversary tactics and techniques
- **CIS Controls v8** — Critical security controls
- **NIST Cybersecurity Framework** — Identify, Protect, Detect, Respond, Recover
