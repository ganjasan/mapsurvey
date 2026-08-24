# Design: mapless-sections

## Context

The respondent page is a single persistent document: `base_survey_template.html` renders
`#map` (full-viewport Leaflet) plus `#info_page > #section-panel`, and section navigation
HTMX-swaps only the panel's innerHTML (`survey_section_partial.html` posts with
`hx-target="#section-panel"`). The map instance survives navigation by design
(persistent-map-htmx-navigation). The panel is a fixed ~420px sidebar. Section templates
are also reused by the editor's preview endpoints, so respondent-side changes propagate to
preview for free.

Constraint: merge reaches prod in minutes; the default must reproduce today's rendering
exactly, with `form` strictly opt-in per section.

## Goals / Non-Goals

**Goals**
- Per-section `layout` = `map` | `form`; `form` renders a centered full-width form, map hidden.
- Mode switches cleanly in BOTH directions across HTMX navigation without recreating the map.
- Geo questions and `form` layout are mutually exclusive, enforced in the editor and server-side.
- "Start" label on a head `form` section's submit.
- Serialization round-trip.

**Non-Goals**
- No per-question layout control; the section is the unit.
- No survey-level welcome model (`welcome_html`) — a `form` head section IS the welcome
  page; if a structured welcome is ever wanted it builds on this.
- No removal of the map from the DOM on form sections (the persistent map stays alive,
  only hidden) and no map bootstrap skipping even for all-form surveys — optimization later.
- No changes to analytics/export semantics: a form section's answers are ordinary answers.

## Decisions

1. **Mode is a body class driven by the swapped-in partial.** The section partial gains
   `data-layout="{{ section.layout }}"` on its root data element (the same element that
   already carries per-section `use_geolocation`). The existing `htmx:afterSwap` init hook
   reads it and toggles `survey-form-layout` on `<body>`. CSS does the rest:
   `body.survey-form-layout #info_page` becomes a static centered column
   (`position:static; width:100%; max-width:760px; margin:0 auto`), `#map` and map-coupled
   chrome (`#drawbar`, `#crosshair-overlay`, basemap switcher, `#showButton`) get
   `display:none`. Rationale: no template forking, no map teardown, works identically on
   first load and on every subsequent swap, and the back-navigation path restores map mode
   by simply not having the class.
2. **`layout` is a model field, not JSON settings.** `SurveySection.layout`
   CharField(max_length=8, choices, default='map'). It is queried in gating logic and
   serialization; burying it in a settings blob buys nothing. Additive migration with a
   default — safe under the no-staging deploy.
3. **Gating is symmetric and server-side.** (a) Question create/save into a `form` section
   rejects `GEO_TYPES` with a 400; the type picker hides the geo group client-side using
   the section's layout (the modal JS already scopes fields by type — same mechanism, new
   input). (b) Section save to `layout='form'` is rejected with a message while the
   section has geo questions; the creator deletes/moves them first. No silent conversion.
4. **Start label is computed where Next is.** The partial already branches Next/Finish; a
   head section with `layout='form'` and a next section labels the submit "Start". Not a
   creator setting — one less knob, and the label is right in the only case it applies.
5. **Map-position fields stay but are hidden for form sections** in the section editor
   panel (client-side toggle). The stored position is harmless and preserved if the
   creator switches back to `map`.

## Risks / Trade-offs

- **Chrome inventory drift**: anything absolutely-positioned over the map added later
  (new buttons) must join the hide list. Mitigation: hide via one CSS rule keyed on the
  body class listing selectors together, with a comment pointing here.
- **Geolocation on form sections**: `locateUser()` on a hidden map is wasted but harmless;
  skip when the body class is set to avoid the permission prompt on a welcome page — a
  consent-before-consent smell.
- **First paint flash**: on a direct load of a form section the map initializes beneath
  before CSS applies. The body class must be set server-side on `<body>` at render time
  (template conditional on the current section), not only by the afterSwap hook.
- **Editor preview** reuses these templates; preview panes are narrower than a real page —
  verify the centered column degrades to container width.

## Migration Plan

One additive migration (`layout` with default `map`); zero behavior change for existing
rows. After deploy, flip the Olney demo's `intro` section (and optionally a new closing
section) to `form` via the editor as the live validation. Rollback = revert deploy; the
column is ignored by old code.

## Open Questions

- Should an all-form survey skip loading Leaflet entirely? Deferred (Non-Goal) — measure
  first; it matters for the "survey tool with maps" positioning but not for Olney.
