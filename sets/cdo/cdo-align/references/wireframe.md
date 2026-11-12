# Wireframe Standard — Design Intent, Not Commentary

A wireframe on an alignment card is a **decision artifact**: the Operator confirms the design off it, and a confirmed card's URL satisfies the pipeline's wireframe gate — dev builds against it without re-asking. A wire that doesn't match the real page can do neither job. The bar: hold it next to the live surface and the delta is legible.

## Build it grounded

1. **Read the real surface first.** Open the page/component/layout the item touches (the same files the grounding read already identified) and reproduce its *current* region structure in wire objects — nav, hero, sections in real order, real headings/labels where they carry meaning. The wire is a diff surface, not a blank canvas.
2. **Mark the delta.** Design intent = what changes and where. `name` every object after the real component or region it maps to (`HeroSub`, `PainPoints.stats`), `annotation` carries the change note, `groupId` (or a `proposed` layer) separates existing structure from new work. The wire should say *"USP line lands in hero-sub slot, under H1, above the CTA pair"* — not *"a text element exists somewhere"*.
3. **Type the components.** Use the component types that map to what gets built — `button`, `card`, `tabs`, `stepper`, `alert`, `breadcrumb` — not bare boxes. Dev maps wire objects → Vue components; typed objects are intent, sketched rectangles are commentary.
4. **Copy-true when copy is the change.** For copy/messaging items the wire shows the actual proposed text in place — the Operator reads the words in situ, not a placeholder.

## Fidelity scales with the item

- **Lite / single-slot items** — a cropped region is enough: the affected section + immediate neighbors, delta marked. No full-page reconstruction.
- **Full / layout-altering items** — the whole affected surface at region fidelity, so ordering, prominence, and crowding are reviewable.
- **Multi-state flows** (modals, steppers, error states) — one wire per state, or `groupId`-separated states in one wire.

## Mechanic notes

- `wiretext:create_wireframe` takes `objects` (positioned boxes/typed components), `name`, `annotation`, `groupId`, `layerId` fields — the schema's layout rules (nesting offsets, label parity, z-order) live in the tool description; follow them or the render corrupts.
- The returned URL is editable — the Operator can adjust slots in the editor; the confirmed URL lands on the card and flows to dispatch untouched.
- MCP absent or erroring → `unavailable — wiretext MCP absent` on the card and file anyway; an optional artifact never blocks.
