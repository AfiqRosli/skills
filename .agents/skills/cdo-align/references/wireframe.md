# Wireframe Standard — Design Intent, Not Commentary

A wireframe on an alignment card is a **decision artifact**: the Operator confirms the design off it, and a confirmed card's URL satisfies the pipeline's wireframe gate — dev builds against it without re-asking. The bar: hold it next to the live surface and the delta is legible.

## Frame convention — environment chrome

- **The wire's outermost frame matches the environment the surface is experienced in.** Browser-experienced surfaces → `browser` components, URL bar carrying the route (`/pricing`, `/dashboard/billing`), first heading inside names the surface. Phone-experienced surfaces → a portrait frame drawn at roughly 9:19 from `box`/`text` — status-bar row up top, host-app chrome when the surface lives inside one (chat → message list + compose row); wiretext has no `phone` component, so the bezel is drawn. Aspect ratio is the environment signal — landscape reads desktop, tall reads phone. A wire without environment chrome is a sketch, not a framed design.
- **One surface → one frame.** **Multi-surface change → multiple frames in a single wire**, ordered along the user flow, joined by `connector`s where the transition matters. The holistic connection is the point — never split surfaces into separate wires that lose it. If a wire approaches canvas limits, crop to region-fidelity frames (still one wire); splitting wires is the last resort.
- **Multi-state flows** (modals, steppers, error states) → one frame per state, `groupId`-separated or connector-linked. States are frames, not overlays on one frame.

## Build it grounded — the to-be, drawn in place

1. **Read the real surface first.** Open the page/component/layout the item touches *and* its design tokens — global CSS custom properties, font stacks, spacing scale, the component library's real names (the same files the grounding read identified). Reproduce the surface's current region structure in wire objects — nav, hero, sections in real order, real headings/labels where they carry meaning. For the mock this token read is load-bearing; for the wire it keeps names and proportions honest.
2. **Separate incumbent from proposed structurally.** `layerId` (or `groupId`) splits `current` from `proposed` objects. Proposed work is **drawn in its real slot at real relative prominence** — a button in the hero-sub slot is design; an arrow to empty space is commentary. Surviving unchanged structure is drawn (the Operator holds the delta against the live page) but carries no annotation — membership does the work.

The drawing itself carries three concurrent obligations:

- **Annotate what and where, never why.** `name` every object after the real component or region it maps to (`HeroSub`, `PainPoints.stats`); `annotation` carries placement/intent only — `"USP line — hero-sub slot, under H1"`, `"NEW: trial banner, dismissible"`, `"MODIFIED: CTA pair order"`. The budget: one annotation per proposed object, ≤ ~15 words. Rationale lives in Marshal's Read — a wire that needs a paragraph of annotation is under-designed; fix the wire, not the note.
- **Type the components.** Use the component types that map to what gets built — `button`, `card`, `tabs`, `stepper`, `alert`, `breadcrumb` — not bare boxes. Dev maps wire objects → real components; typed objects are intent, sketched rectangles are commentary.
- **Copy-true when copy is the change.** For copy/messaging items the wire shows the actual proposed text in place — the Operator reads the words in situ, not a placeholder.

## Fidelity scales with the item

- **Lite / single-slot items** — one framed crop: the affected section + immediate neighbors, to-be drawn, delta legible. No full-page reconstruction.
- **Full / layout-altering items** — every affected surface at region fidelity inside its environment frame, so ordering, prominence, and crowding are reviewable — including the cross-surface connections when the change spans them.
- **Backend-affecting items** — the wire frames the *consumer surface's* to-be state: the component rendering the new field, the pending/empty/error state the new lifecycle implies, the affordance a permission change toggles. The backend machinery itself is never wired — System Context carries that. Same `n/a` bar as the mock: claim it only when no surface reflects the change.
- **Multi-state flows** — one frame per state as above.

## Mechanic notes

- `wiretext:create_wireframe` takes `objects` (positioned boxes/typed components), `name`, `annotation`, `groupId`, `layerId`, `url` fields — the schema's layout rules (nesting offsets, label parity, z-order) live in the tool description; follow them or the render corrupts.
- **Typed components use the `component` discriminator**: every UI object is `{"type": "component", "componentType": "browser" | "button" | "card" | ...}` — writing `type: "browser"` directly fails validation (`No matching discriminator`). The browser frame's URL bar is driven by `label` (put the route there); `name` and `annotation` carry surface naming and delta intent.
- The returned URL is editable — the Operator can adjust slots in the editor; the confirmed URL lands on the card and flows to dispatch untouched.
- MCP absent or erroring → `unavailable — wiretext MCP absent` on the card and file anyway; an optional artifact never blocks. The static mock is produced independently — a missing wiretext does not excuse a missing mock on a UI-affecting card.
