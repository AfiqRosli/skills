# Design Mock Standard — Visual-Fidelity HTML Artifact

Every **UI-affecting** card carries a **design mock**: one self-contained HTML file rendering the to-be surface at visual fidelity, derived from the same grounded read as the wire. That includes backend items — a "purely backend" change almost always implies a UI state update somewhere: the new API field a component renders, the async job's pending/progress state, the status value that becomes a badge, the permission gate that hides an affordance, the error path that becomes a notice. For those items the mock depicts the **consumer surface's new state**, never the backend internals. `n/a — no UI surface` applies only when no surface reflects the change (internal jobs, plumbing, silent migrations) — and the drafter justifies it in Flags, not by default. The wire is the structural contract (what/where); the mock is the visual contract (how it looks/feels). A mock that contradicts the wire is a defect, not a second opinion.

## Grounding order — the incumbent design language wins

Build the mock's styling from real sources, in this order:

1. **Project design tokens** — global CSS custom properties, font stacks, spacing/radius scales, the component library's real class or component names (carry them as HTML comments). The mock must read as *the same product* when held next to the live surface.
2. **Framework conventions** — Vue SFC / React / plain HTML per the repo's stack; mock markup mirrors how the real component will be structured.
3. **Neutral placeholder styling** — only when no design system is identifiable. The file's header comment must then say `placeholder styling — no design tokens found`, and the card's Flags should carry `ungrounded:design-tokens`.

Anti-slop floor: equal content edges, one visual system, no generic-gradient hero, no decoration absent from the incumbent language. The bar is a professional product surface, not a template — and never page-level marketing-site rules; this is product UI, not a landing page.

## Environment frame — render where the surface lives

The mock's outer frame is the **dominant environment the surface is actually experienced in**, decided by the grounded read (which device, which host app) — not by what's easiest to draw. Aspect ratio is the frame's loudest signal — the silhouette answers "does this work *there*?" before the details do.

- **Browser-experienced surfaces** (app routes, dashboards, admin screens) → a true **16:9 browser viewport**: URL bar carrying the real route, tab bar, window chrome.
- **Phone-experienced surfaces** (mobile flows, link/share destinations) → a **9:19 portrait phone frame**: rounded bezel, notch, status bar. When the surface is experienced *inside a host app*, the host's chrome renders too — a link pasted into a chat gets the chat header, the message stream around the card, and the compose bar, because that chrome is the real surrounding the user sees.
- **Cross-device surfaces** → the dominant environment wins; render a second labeled frame only when the change behaves materially differently per environment.

An env-mismatched frame silently approves designs that fail in the real context — a phone surface mocked on a wide canvas passes review and ships broken.

## Fidelity scope

- **Layout, hierarchy, typography, color, spacing** — the full visual argument.
- **Depicted micro-interactions via pure CSS** — `:hover` lift, `:active` press (`scale(0.97)`), focus rings. No JS framework, no build step; the file must open from `file://`.
- **Interaction details are depicted selectively** — depict one when it carries intent (press feedback on actionable elements, an easing/duration that encodes a decision — note the value in a CSS comment, e.g. `/* 160ms ease-out — press feedback */`). Frequency decides: keyboard-repeated actions get no depicted motion. Keep durations under ~300ms and animate transform/opacity only.
- **Imagery** — placeholder blocks marked `<!-- image: {what goes here} -->`; never stock filler presented as final.

## File contract

- One `.html` file, inline `<style>`, no external assets or CDN links.
- Header comment: `{key} — {title}`, the surface/route it depicts, the environment frame chosen (`browser:{route}` | `phone:{host-app|bare}`), and the grounding source (`tokens: {file}` or the placeholder notice).
- Multi-surface changes → either tabbed sections in one file, or a directory of one file per surface (passed as the dir path in `mock`); order follows the user flow — the wire's frame order when a wire exists.
- Multi-state flows → states as separate labeled sections or files matching the wire's frames.

## Card contract

The drafter passes the produced file (or directory) as `mock` in the filing JSON — `file-cards.py` stages it into `alignment/drafts/assets/{key}/` and sets the card's Mock line deterministically (`mock.html` for a file, `mock/` for a directory). Relative `mock` paths resolve against the cards-JSON file's directory. `n/a — no UI surface` for non-UI items; `unavailable — {reason}` only when production genuinely failed (say why in Flags). **Before filing, confirm the mock renders as intended** — the filer verifies structure, existence, and external refs; whether it *looks right* is yours. The mock never substitutes for the wireframe URL — the pipeline's wireframe gate is unchanged.
