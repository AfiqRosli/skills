# Capability: intake-shape — raw ask → specced docs item

Raw asks arrive thin ("document the auth flow", "write a runbook for deploys"). Shaping decides what produce would otherwise have to guess.

## Shape

Append to `backlogs/docs.md`:

```
- [ ] DOC{n} — {title} | type: {kind} | target: {section/path} | source: {story-key}? | size: lite|full | deps: {keys}
```

- **type** — `guide` (how-to, durable), `api` (endpoints/schemas), `runbook` (ops procedures), `reference` (lookup material), `tutorial` (learning path). Pick by what the reader does with it, not the topic.
- **target** — where it lands under the profile's `docs_root` (e.g. `engineering/api/`, `operations/runbooks/`). Consult `docs-profile.yaml`: a path inside an `auto_zone` means no nav edit will be needed; say so — it changes produce's work.
- **source** — the story this documents, when fed from shipped work.
- **size** — `lite` = one page; `full` = a section (multi-page or an index + children).
- **deps** — item keys that must be `done` before this produces; produce enforces it (unresolved dep → the item stops, not guesses). Only list real ordering constraints.

Fed items arrive with just `source:` + `type: guide` — when one comes back for shaping, fill `target`/`size`/`deps` rather than rewriting the line.

## Standards

- Shaping is cheap; a skipped dimension becomes produce's guess. If target section genuinely can't be determined, say `target: ?` and flag it — alignment will surface it.
- Doc-worthiness of fed items is *alignment's* call — shape captures intent, not verdicts.

## Output

`{key, item_line}` — the appended backlog line.
