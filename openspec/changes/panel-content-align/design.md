## Context

`section-layout-controls` (#473) put stage, panel side and panel width on the section and
renders them as body classes from `SurveySection.layout_classes()` (direct load) and
`initSection()` step 0 (HTMX swap), plus `--panel-w`; side and width rules live only inside
`@media (min-width: 769px)`. Inside `#info_page` (a flex column, `overflow-y: auto`) sit
`#section-panel` (the HTMX target) → `#section-data` (the section partial: `.header` with
`#title` and `#closeButton`, `.survey-progress`, `#content`, `#navig_buttons` with `mt-auto`)
and, after it, the footer partials. `#closeButton` is `position:absolute` against `#info_page`.

## Goals / Non-Goals

**Goals:** two opt-in settings — content width (`full | column`) and vertical alignment
(`top | middle`) — in any combination with each other and with #473's controls; defaults
render byte-identical bodies; desktop only; same travel paths as #473.

**Non-Goals:** a centred card over the whole screen (the earlier reading of #476); free
widths; text alignment (left/centre of the text itself); changes to `form` or phone layouts.

## Decisions

### D1. Two plain columns beside the #473 ones
`content_width = CharField(6, choices=(full, column), default='full')`,
`content_valign = CharField(6, choices=(top, middle), default='top')`. Two settings, not one
"centre" switch (owner's choice 2026-10-28): a column at the top is a valid look of its own.

### D2. Two more body classes from the same two writers
`layout_classes()` appends `content-column` / `content-middle` for non-`form` sections (unknown
values add nothing); `#section-data` carries `data-content-width` / `data-content-valign`;
`initSection()` toggles the two classes next to `panel-right` etc. One rule set, two writers,
as before.

### D3. CSS, desktop only, inside the existing min-width block
- Column: `body.content-column #section-data > .header, .survey-progress, #content,
  #navig_buttons { max-width: 640px; margin-left: auto; margin-right: auto; width: 100%; }`
  — box-level centring keeps the text left-aligned and leaves `#closeButton` (absolute against
  `#info_page`) in its corner. On the 420 px default panel the column is wider than the panel,
  so it is a no-op there.
- Middle: `body.content-middle #section-panel { flex: 1 0 auto; display: flex; flex-direction:
  column; }` and `body.content-middle #section-data { margin-top: auto; margin-bottom: auto; }`.
  Auto margins centre while there is free space and collapse to 0 when the content is taller,
  so overflow scrolls from the top inside `#info_page` instead of being clipped above the
  title (the failure of `justify-content: center`). `#navig_buttons`' `mt-auto` has no free
  space to eat inside a non-stretched `#section-data`, so the buttons follow the content.
  The footer follows `#section-panel`, i.e. sits at the panel's bottom.

### D4. Editor, travel, API
Same as #473: two `Select`s in the Layout block after `panel_width`, hidden with side/width for
`form` (`syncLayoutControls`), required=False + clean_* keep the stored value on a POST without
them; `plain_field_values` carries them (draft copy, duplicate); `serialize_sections` +
`_choice()` on import; `SectionIn` literals, `SectionOut`, `forms_bridge.SECTION_FIELDS`, MCP
descriptions, regenerated references. `structural_section_changes` ignores them → safe edit.

### D5. One changelog card per epic
No new `survey/changelog/` file: one sentence is added to `2026-10-28-section-layout.html`
(same id — creators who saw it are not shown it again; owner rule 2026-10-28).

## Risks / Trade-offs

- The image stage on desktop + `middle`: the panel is full height, nothing changes there but
  the content position — fine. A geo pop-up or crosshair does not live inside `#section-data`,
  so it is unaffected.
- `#section-panel` becoming a flex container under `content-middle` only: other sections keep
  today's box model, so no regression surface beyond the opt-in.

## Migration Plan

Migration `0107`: two columns with defaults; nothing to backfill; revert = drop them.
