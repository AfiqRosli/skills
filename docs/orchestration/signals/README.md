# Signals Inbox

Frontline agents and pipelines drop signal files here — one file per signal,
`.md` format. `cdo-watch --mode intake` folds them into `flow-ledger.yaml`'s
signal queue for Marshal's duty-officer triage, then deletes the file.

## Conventions

- **Filename:** `{kind}-{key-or-slug}.md` — e.g. `line-stop-s7.md`,
  `blocked-content-12.md`
- **First line** is the one-line summary shown in triage — make it count
- **`LINE_STOP`** (literal, uppercase) anywhere in the file = halt-class
  signal: something is looping or producing garbage; the pipeline that dropped
  it should already have stopped locally

## Who writes here

`cdo-code-e2e` sessions, `cdo-*` department pipelines, and anything else that hits
an autonomously-unresolvable condition mid-run. Don't drop signals for things
you can fix — the inbox is for "the machine needs a human or a Marshal."

Empty directory = quiet floor. That's the good state.
