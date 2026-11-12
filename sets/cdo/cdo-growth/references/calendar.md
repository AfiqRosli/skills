# Capability: calendar — the editorial view

`content/calendar.md` — one line per piece: date → key → title → status (drafted | published | queued).

- **Queued** items are produced + confirmed but not yet published (a lane decision, often waiting a ship date or an Operator pass)
- **Published** gets the date stamped; the ledger's findings carry the link/channel
- Keep it newest-first, one line per entry — the Operator's skim surface for "what's going out the door"

Publishing itself is a ship-decision — if the piece needs a deploy (docs site, blog), route through `cdo-platform ship`; marketing channels stay inbound per the dept's stance.

## Output

calendar.md state — `{queued: n, published: n, next: {key}}`.

