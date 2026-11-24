## Context

`map-layers-study-area` (#779/#780) shipped one `StudyArea` per canonical survey (OneToOne), one
writer `survey/services/study_area.py`, a full-page editor (`study_area_views.editor_study_area` +
`study_area_editor.js`), a gated outline endpoint, the respondent `study_area.js` (fog, open-on,
`admit`) initialised once per page from a shell `json_script`, the server guard
`study_area_guard.for_section`, print framing, Responses/Reports outlines, translation occurrence
`survey:study_area_message`, ZIP, copies, REST and MCP. The only entry point is the section's Map
card. Issue #781 (owner, 2026-11-24) moves the survey's area to Survey settings and lets a map
section choose the survey's area, its own, or none.

## Goals / Non-Goals

**Goals:** per-section choice with one effective-area resolver used by every respondent-side
surface (map, browser refusal, server refusal, preview, print); survey area editable from Survey
settings; parity in ZIP, copies, REST, MCP, translations.

**Non-Goals:** per-section outlines on Responses or Reports (they keep the survey's outline);
the Wizard setting section areas; re-checking stored answers; a section area for mapless sections.

## Decisions

**D1. A separate model `SectionStudyArea`, not a generalised `StudyArea`.** Fields: `survey` (FK to the
canonical survey), `section_ref`, `mode` (`survey` | `own` | `none`), nullable `geometry`, and the
same `source`, `place_name`, `osm_ref`, `fog`, `refuse_outside`, `message`, `refused_marks`,
`updated_at` as `StudyArea`. Unique `(survey, section_ref)`; the service writes the ref as
`section_ref(section)` and looks up by `section_refs.split` equality, so `<code>` and `<code>#0`
match like placements. *Alternative:* drop the OneToOne and add `section_ref` to `StudyArea`; it
would turn every `StudyArea.objects.filter(survey=…)` (Responses, Reports, ZIP, copies) into a
silent bug source. The separate model keeps `get(survey)` meaning exactly "the survey's area".

**D2. `mode='survey'` rows are kept.** Switching a section from Own to Survey's area or No area
keeps the drawn outline in the row, so switching back restores it; no row and a `survey` row both
mean the survey's area. Exports carry only `own` and `none` rows.

**D3. One resolver `effective(section)`** in the service returns `(kind, area)` where `kind` is
`survey` | `own` | `none` and `area` is the `StudyArea` or `SectionStudyArea` that applies (None for
`none` or when the survey has none). Both models answer the same duck-typed attributes
(`geometry`, `fog`, `refuse_outside`, `message`, `refused_marks`), so `Guard`, `message_for`,
`describe`, `draw_study_area` take either. Mapless sections resolve to none.

**D4. Respondent page: per-section metadata, swapped on navigation.** `views.study_area_meta(section)`
returns the effective meta (URL, fog, rule, message, bounds) and the section partial carries it as
`#section-data[data-study-area]` (template filter, so the respondent, operator-entry and preview
renders all get it without hand-built contexts). The shell `json_script` goes. `initSection()` calls
`StudyArea.show(map, meta)` on map sections; it redraws only when the outline URL changes, clears
on `none`, and the map re-opens on the area whenever the area changed (first load or swap), unless
the section's own start lies inside. The outline URL is the survey endpoint, with `?section=<id>`
for an own area; the endpoint checks the section belongs to the resolved survey.

**D5. Writes reuse the existing editor endpoints with an optional `section`.** `save`, `settings`,
`clear`, `from_layer` read `section` (an id of a section of `request.survey`); a new
`editor_study_area_section_mode` endpoint sets the Map card's choice. Choosing "Own area" with no
outline yet navigates to the editor `?section=<id>`, which starts from the survey's outline (unsaved)
when there is one; Save stores the section's own area with `mode='own'`. "Remove" on the section
editor returns the section to the survey's area.

**D6. Survey settings card** shows the survey area summary, Set/Edit (the editor), Remove
(`Dialog.confirm`), and the fog and refusal switches saving through `editor_study_area_settings`.
Controls carry no `name=` (the panel is one autosaving form, like the layers card). The Map card's
area row becomes three radios; the editor's "Back" returns to the section.

**D7. Translations.** An own area with refusal on lists occurrence `section:<ref>:study_area_message`,
entity kind `section_study_area`, written by `set_section_message_translation`; gaps list it as
"Study area message · <section title>".

**D8. REST/MCP.** `GET/PUT /surveys/{uuid}/sections/{section_id}/study-area` and MCP
`get_section_study_area` / `set_section_study_area` (`mode`, optional geometry and rules; `own`
without geometry keeps the stored outline, else 422). `get_study_area` adds `sections`: each map
section's id, ref, title and mode.

**D9. Print and counters.** `resolve_frame`/`draw_study_area` take the section's effective area; the
form hash includes each override's mode and `updated_at`. Refusals count on the area that refused.

## Risks / Trade-offs

- [Section codes change in a draft] → refs then name another section, exactly like placements; the
  same behaviour users already have for layers. Stale rows are ignored.
- [Respondent swaps between two areas fetch twice] → the outline is cached (`max-age=60`), small (≤2,000 vertices).
- [Archive ordering] → `survey-study-area` exists only in the unarchived parent change, so deltas here
  are ADDED-only; archive this change after `map-layers-study-area`.

## Migration Plan

One additive migration (new table). No data migration: no row means the survey's area, which is
today's behaviour. Rollback = revert; the table is unused by old code.
