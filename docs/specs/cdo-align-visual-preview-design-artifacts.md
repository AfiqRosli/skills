# Spec — cdo-align Visual Preview: Designed Artifacts

**Status:** implemented 2026-11-16 · **Scope:** `cdo-align` Visual Preview capability · **Date:** 2026-11-16

## 1. Intent

Upgrade the alignment card's Visual Preview from "a wiretext wireframe URL" into a pair of design artifacts that let the Operator confirm the *to-be* design, not just its structure:

1. **Wiretext framing as close to intended design as possible, without meta commentary** — the frame is the design argument; annotation states placement and intent, never rationale.
2. **The to-be is actually designed** — proposed work is drawn as it will exist, grounded in the surface it lands on, not sketched as commentary beside a current-state replica.
3. **Browser-window-tab framing** — every wire's outer container is a `browser` component whose chrome reads as the real window (route in the URL bar, surface name implied by content). A change spanning multiple surfaces/surfaces-states shows them as multiple browser frames in one wire so the holistic connection is visible in a single artifact.
4. **Holistic with the current implemented design** — additions and modifications must be legible *where they integrate*: the wire reproduces the touched surface's real structure and the delta sits inside it.
5. **Static HTML/CSS design mock** — a renderable visual-fidelity artifact derived from the wireframe, built on the project's real design language, for further visualization beyond the wiretext editor.

## 2. Current state

- `references/wireframe.md` — the standard: reproduce the touched surface's *current* region structure in wire objects, mark the delta via `name`/`annotation`/`groupId`, use typed components, scale fidelity to `lite|full` sizing, one wire per state for flows.
- `assets/alignment-card-template.md` — Visual Preview section carries one line: `Wireframe: {url | n/a | unavailable}`.
- `scripts/file-cards.py` — accepts optional `wireframe` field, recovers a `wiretext.app` URL from the card body, validates it.
- Downstream consumers:
  - `cdo-code-e2e` pipeline step 2 — a *confirmed* card's `card.wireframe` URL satisfies the wireframe gate (reused, not regenerated, not re-asked).
  - `cdo-review` `confirm-edited` — offers keep / regenerate / strip when scope edits invalidate the wire.
  - `cdo-orchestrator` secretariat — cards carrying a wireframe URL are excluded from self-approve (a human saw this).

## 3. Gap analysis

| Intent | Today | Gap |
|---|---|---|
| To-be designed, not annotated current-state | Wire reproduces *current* layout and marks delta | Proposed objects are marks, not a designed end-state at real placement fidelity |
| Browser-tab outer container | No framing convention — raw object grid | `browser` component unused as the universal outer container |
| Multi-surface holistic view | "One wire per state" only | No convention for several surfaces/routes in one artifact |
| Holistic w/ implemented design | "Read the real surface" at wire-object fidelity | No token/component-level grounding (colors, type scale, real component names beyond region labels) |
| Static HTML/CSS mock | Does not exist | New artifact class entirely |
| No meta commentary | Partial — `annotation` carries "the change note" | No budget rule; annotations can drift into rationale |

## 4. Design decisions

### 4.1 Wire structure — browser-tab framing

- **Every wire's outermost objects are `browser` components.** URL bar carries the route (`/pricing`, `/dashboard/billing`); the frame title/first heading names the surface. One surface → one browser frame. The canvas may hold several.
- **Multi-surface changes** → multiple `browser` frames in a *single wire*, ordered along the user flow, joined by `connector`s where the transition matters. This is the "holistic connection" the Operator reviews in one URL. If a wire hits practical canvas limits, fall back to region-cropped browser frames (still one wire) — never split into separate wires that lose the connection.
- **Incumbent vs proposed separation is structural, not prose:**
  - `layerId` (or `groupId`) separates `current` from `proposed` objects.
  - Proposed objects get `annotation` = placement/intent only (`"USP line — hero-sub slot, under H1"`, `"NEW: trial banner, dismissible"`, `"MODIFIED: CTA pair order"`).
  - Surviving unchanged structure is drawn (the Operator must hold the delta against the real page) but carries no annotation — group/layer membership does the work.
  - **Annotation budget:** annotations name *what and where*; rationale lives in Marshal's Read. A wire that needs a paragraph of annotation is under-designed — fix the wire, not the note.

### 4.2 To-be fidelity

- The wire depicts the **designed end-state**: proposed elements occupy their real slots at real relative prominence. "Mark the delta" becomes "draw the delta in place" — an arrow to empty space is commentary; a button in the hero-sub slot is design.
- Fidelity tiers (extends today's sizing rule):
  - **lite** — cropped region(s) inside browser chrome: the affected section + immediate neighbors, to-be drawn.
  - **full** — whole affected surface(s) at region fidelity, ordering and crowding reviewable.
  - **multi-state flows** — one browser frame per state (modal open, stepper step, error), grouped or connected; states are separate frames, not overlays.
- Typed components stay mandatory (`button`, `card`, `tabs`, `stepper`, `alert`…) — dev maps wire objects → real components.

### 4.3 Static HTML/CSS design mock

A second artifact per UI-touching card: one self-contained HTML file that renders the to-be surface at visual fidelity.

- **Grounding order for the mock's design language:**
  1. The project's real design tokens / global CSS / component library (the same files the grounding read identified — custom properties, font stacks, spacing scale, real component class names or Vue/React component names carried as comments).
  2. The framework's own conventions (Vue SFC / React / plain HTML per repo).
  3. A neutral, clearly-marked placeholder styling *only* when no design system is identifiable — the mock header comment must say `placeholder styling — no design tokens found`.
- **Scope of fidelity:** layout, hierarchy, typography, color, spacing, and the *depicted* micro-interactions (`:hover` lift, `:active` press scale ~0.97, focus rings) via pure CSS. No JS framework, no build step, must open from `file://`. Inline `<style>` in one file; no external assets (placeholder content allowed for imagery, marked).
- **Interaction details follow the emil-design-eng rubric** where they carry intent: press feedback on actionable elements, easing/duration values noted in CSS comments when they encode a decision (e.g. `/* 160ms ease-out — press feedback */`). Not every detail needs depicting — frequency decides (keyboard-repeated actions get none).
- **Anti-slop floor (from taste-skill, borrowed as sensibility not machinery):** equal content edges, one visual system, no generic-gradient hero, no decoration that isn't in the incumbent language. The mock must be holdable next to the live surface and read as *the same product*.
- **Relationship to the wire:** the wire is the structural contract (what/where); the mock is the visual contract (how it looks/feels). Both derive from the same grounded read — a mock that contradicts the wire is a defect, not a second opinion.

### 4.4 Card contract changes

- Visual Preview section gains a second line: `Mock: {relative/path/to/mock.html | n/a — no UI surface | unavailable — mock not produced}`.
- `file-cards.py` accepts an optional `mock` field: validates the referenced file exists (relative to the card/drafts dir), copies or references it into `alignment/drafts/assets/{key}/mock.html` (decision below), and the card body embeds the path. A missing/unwritable mock degrades to `unavailable` on the card — never blocks filing, same posture as the wireframe.
- **The wireframe URL remains the pipeline gate artifact.** The mock is Operator-facing review evidence; `cdo-code-e2e` step 2, `cdo-review` confirm-edited handling, and secretariat self-approve exclusion are unchanged in this spec (see §6 for the confirm-edited follow-up).

### 4.5 Aptitude sourcing (why these three skills informed this)

- **`pbakaus-impeccable`** → the grounding method: read incumbent visual truth (real surface files *and* design tokens/DESIGN.md when present) before designing; refinement preserves identity — the to-be extends the incumbent world, never replaces it.
- **`emilkowalski-emil-design-eng`** → the interaction/polish rubric for depicted micro-details (press states, easing, duration ceilings, origin-aware motion) — applied selectively, not as a checklist dump.
- **`leonxlnx-taste-skill`** → only its verification discipline and anti-slop sensibility; its page-level rules (section-per-screen, dealt palettes) are explicitly *not* imported — they govern marketing sites, not product-UI deltas.

## 5. File-by-file changes

| File | Change |
|---|---|
| `references/wireframe.md` | Expand into the full wire standard: browser-tab framing, current/proposed layers, multi-surface single-wire convention, annotation budget, to-be fidelity tiers. Keep it the single routing point for wire construction. |
| `references/design-mock.md` *(new)* | Mock construction standard: grounding order, fidelity scope, placeholder-marking rule, file contract (`file://`-openable, inline CSS, no external assets). |
| `assets/alignment-card-template.md` | Visual Preview section: add `Mock:` line + comment block; document both `n/a`/`unavailable` fallbacks. |
| `SKILL.md` | "Visual preview" bullet → produce both artifacts; filing payload gains `mock`; report line mentions mocks produced/skipped. |
| `scripts/file-cards.py` | Accept/validate `mock` field; stage mock file into drafts assets dir; embed path in card body; tolerate absence. |
| `scripts/tests/` | Cases: mock present/missing/invalid path; card body round-trip. |

## 6. Decisions taken at implementation

1. **Mock storage path** — `alignment/drafts/assets/{key}/mock.html` (chosen; enables future multi-file assets under the same `{key}/` dir).
2. **Archival behavior** — implemented for superseded drafts: `file-cards.py` moves `assets/{key}/` to `superseded/{key}.{stamp}.assets/` alongside the draft snapshot. Archived-to-date cards (`cdo-review` move) still orphan their mock — flagged follow-up.
3. **`confirm-edited` mock drift** — implemented: `cdo-review` SKILL.md's confirm-edited offer now covers the mock alongside the wire URL, and `apply-decisions.py` moves `assets/{key}/` with the card through archive (dated dir), defer (`parked/assets/{key}/`), resurface (back to `drafts/`), and unpark/resurface-superseded (`superseded/{key}.{stamp}.assets/`). `resolve-item.py` surfaces `card.mock`/`mock_status` for downstream consumers, and the pipeline's Dev Notes embed it when confirmed.
4. **Wiretext canvas limits** — unverified max object count/size for a full-surface multi-frame wire. Implementation should empirically check on the first `full` multi-surface card; fallback is region-cropped frames per §4.1.
5. **Mock for `lite` items** — every UI-touching card (chosen): a lite item's mock is small by definition and the Operator's confirm is cheaper with it.

## 7. Validation

- Implement, then run `cdo-align` on one real UI-touching backlog item end-to-end: wire with browser frames + mock produced, card filed, Operator review simulated.
- Success signal: the confirmed card's wire + mock let `cdo-code-e2e` step 2 reuse the wireframe URL *and* the dev needs no design re-ask; Operator edits on confirm drop vs. wire-only cards.
- Regression: non-UI cards unchanged (`n/a` on both lines); wiretext-absent runs file `unavailable` and still pass `file-cards.py` validation.
