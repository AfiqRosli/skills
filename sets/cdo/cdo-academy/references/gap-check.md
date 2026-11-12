# Capability: gap-check — knowledge chains vs the curriculum map

What the org's shipped work required vs what the academy actually teaches.
This is a judgment pass, not an id diff — coverage means *taught*, not
*mentioned*.

## Input

The knowledge entries to check — default: all of
`learning/knowledge/*.yaml`; a caller may scope to specific keys.

## The coverage pass

1. **Load the map** — `docs/academy/catalog.yaml`
   (`tracks → courses → modules`, each module with a level and the stories
   that motivated it). Read course `index.md` / module files where the
   catalog alone can't settle whether a concept is genuinely covered.

2. **Walk every concept and its `requires` chain** — for each concept in the
   extractions, ask: does a module exist whose content would let a learner
   *produce* this, at the level the work demanded?

   - **Covered** — a module teaches this concept at ≥ the needed level.
     Match on the module's `concepts` list first (a module can declare which
     concept ids it covers even when its module-id differs), then on
     module-id equality, then on honest content judgment — "Covered" means
     taught, not mentioned. A `fundamentals` need covered by an `advanced`
     module counts; the reverse does not.
   - **Placement check** — the extraction suggests `track`/`course`; the
     catalog is authoritative. Re-file the concept where the curriculum
     actually wants it rather than minting a duplicate course.
   - **Transitive holes** — a `requires` id that no module covers is a gap
     even when the top concept is covered. Prerequisite rungs are the
     curriculum's foundation; missing ones make every dependent module lie.
   - **Adjacent-but-different** — "CSS transitions" existing doesn't cover
     "CSS grid". Err toward filing the gap; the alignment review can reject
     a false positive cheaply — an unfiled hole stays invisible.

3. **File confirmed gaps** — one backlog item per missing module, via the
   deterministic recorder:

   ```bash
   uv run ./scripts/catalog.py --orchestration-dir "{orch}" file-gap \
     --concept-id {id} --title "{name}" --kind {kind} \
     --track {track} --course {course} --level {level} --sources {keys}
   ```

   The script allocates `C{n}` keys, dedupes on `concept-id`, and writes the
   canonical line format. Already-filed concepts report `already-filed` —
   a result, not a failure.

   Always read knowledge files with explicit UTF-8 — a platform-default
   decode (cp1252) mangles typographic characters into the backlog and the
   corruption looks plausible until rendered.

4. **Summarize** — covered vs filed vs already-known, so the caller sees
   the org's teaching surface grow.

Gaps land in the normal pipeline — alignment drafts on them like any backlog
item; the Operator sees "we needed to know X and can't teach it yet" on the
standard review surface.

## Output

`{checked: n, covered: [ids], gaps_filed: [{key, concept-id}], already_known: [ids]}`
— JSON for `-H`.
