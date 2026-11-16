# Capability: extract — dissect shipped work into its knowledge chain

A shipped story is evidence of knowledge the org needed. Don't extract what
was *produced* — dissect what a person would need to *know* to produce it
themselves.

## Input

`{key}` → the story's card + devlog + diff/spec — whatever the pipeline
produced. Establish first **what was actually delivered**: a UI change, an
API route, a schema migration, a config knob. The deliverable anchors the
dissection.

## The dissection

For the delivered output, ask: *a person with working computer literacy —
they can use a browser and files but know no IT — what would they have to
learn to build this themselves, confidently?*

Walk backwards from the deliverable to the floor:

```
UI story → component rendering → Vue → JavaScript → TypeScript (project uses it)
         → HTML/CSS → how the web works          ← the floor, stop here
         → hydration flicker → SSR → DOM lifecycle → JS event loop
```

- **Chains go down to the floor, no further.** "How the web works" and
  HTML/CSS/JS entry points are the deepest nodes. Computer-usage basics
  (what a file is, how to browse) are assumed — don't extract those.
- **Every node in the chain is a concept** — the direct "this story used X"
  nodes AND the prerequisite rungs beneath them. A UI story's extraction may
  hold 15–30 concepts the first time; that is the honest size of the gap
  between zero and shipped. Later stories mostly re-use existing nodes.
- **Level is the learner-facing band** — where on the fundamentals →
  intermediate → advanced spectrum this concept must be taught for someone
  to *produce* (not merely recognize) the work.

## Write

`learning/knowledge/{key}.yaml` (under `{orchestration_dir}` — ops evidence,
not public curriculum):

```yaml
source_story: S12
delivered: ReviewCard hydration-flicker fix + responsive layout rework
concepts:
  - id: ssr-hydration             # kebab-case, canonical across stories
    name: SSR hydration & mismatch
    kind: concept                 # concept | api | pattern | domain | toolchain | process
    level: advanced               # fundamentals | intermediate | advanced
    track: frontend-engineering   # suggested academy placement
    course: nuxt
    requires: [ssr-rendering, dom-lifecycle, js-event-loop]
    evidence: flicker came from server/client markup divergence in ReviewCard.vue
  - id: ssr-rendering
    name: server-side rendering
    kind: concept
    level: intermediate
    track: frontend-engineering
    course: nuxt
    requires: [http-request-lifecycle]
    # chain node — no evidence needed, the story assumed it
  - id: css-flexbox
    name: flexbox layout
    kind: concept
    level: fundamentals
    track: frontend-engineering
    course: css
    requires: [css-box-model, html-elements]
    evidence: layout rework used v-row/v-col which resolve to flex
```

## Judgment

- **Extract knowledge, not work-products.** "We edited ReviewCard.vue" is a
  deliverable; "hydration requires identical server/client markup" is
  knowledge. Extract the second kind.
- **Concept ids are canonical** — reuse an existing id from
  `learning/knowledge/*.yaml` if it fits; a new id per story fragments the
  graph. Check neighboring extractions before minting.
- **`requires` is the graph** — prerequisite ids share the concept namespace.
  A chain node absent from the catalog is as much a gap as the top node; the
  gap-check walks both.
- **Track/course are suggestions** — propose where the academy would teach
  it; gap-check confirms or corrects placement against the catalog's actual
  structure.
- **Thin is fine** — a story that exercised nothing new yields a small
  `concepts:` list (or empty); don't manufacture curriculum to look
  productive. But never truncate a real chain because it got long.

## Output

`{key, delivered, concepts: [...]}` written to `learning/knowledge/{key}.yaml`.
