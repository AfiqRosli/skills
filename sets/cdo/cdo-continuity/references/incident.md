# Capability: incident — IR delegation

A genuine incident (breach-class, destructive action, systemic corruption) is the cybersec IR team's domain. This dept owns declaring and coordinating, not improvising response.

## Input

`{scope}` — what the incident covers: affected story keys, surfaces, or a free-text declaration (e.g. `13-08-x+08-02-x — unauthorized writes to prod schema`). The tighter the scope, the cleaner the freeze.

## Delegates (srm-synced BMAD-CYBERSEC)

| Need | Delegate |
|---|---|
| incident command/coordination | `bmad-bus-cybersec-team-incident-commander` |
| response playbook | `bmad-bus-cybersec-team-incident-response-playbook` |
| defensive ops | `bmad-bus-cybersec-team-blue-team-lead` |
| evidence-grade analysis | `bmad-bus-cybersec-team-forensic-investigator` |

None installed → escalate straight to the Operator: a declared incident without IR capability is a human problem by definition.

## Duty

- **Declare precisely** — scope, blast radius, what's known vs assumed. An over-declared incident freezes the floor; an under-declared one costs more than the floor.
- **The org keeps a shadow** — journal the incident + response to `learning/cases/` via the forensic path; recovery lessons become doctrine.
- **LINE_STOP during an incident** — file `signals/line-stop-incident-*.md`; the batch floor holds while IR runs.

## Output

`{scope, delegates_invoked, line_stop_filed}` — or `{errors: ["no IR delegates installed"]}`.

