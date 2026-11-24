## Why

The study area (change `map-layers-study-area`, #779/#780) is one per survey but is set only from a
section's Map card, so it reads as a section setting; and a survey cannot have different areas on
different map sections — a city-wide first section and a one-street corridor in the second, or a
"where do you live" section where marks outside must be accepted. Owner decision 2026-11-24, issue #781.

## What Changes

- The survey's study area is set in **Survey settings → Respondent map**, next to the default
  position: Set / Edit / Remove, fog, answers outside (the message stays in the study area editor).
- A map section's **Map card** chooses one of three: **Survey's area** (default, read-only summary),
  **Own area** (the same study area editor, outline and rules stored for the section), **No area**
  (no fog, nothing refused on this section).
- A section override is stored by section reference (`<code>` / `<code>#<n>`) on the canonical
  survey, like layer placements: drafts, versions and restores read it, nothing copies it.
  Switching away from "Own area" keeps the drawn outline so switching back restores it.
- The respondent map, the browser and server refusal, the Live preview and the printed form use the
  section's **effective** area; the respondent map swaps the outline/fog when the next section's
  area differs. Responses and Reports keep the survey's outline. The Wizard still sets the survey's area.
- The own area's refusal message is creator text in the Translations tab
  (`section:<ref>:study_area_message`).
- ZIP export/import (`section_study_areas`), survey copies, REST v1 and MCP
  (`get_section_study_area`, `set_section_study_area`; `get_study_area` lists section choices).
- Help page "Set the study area" updated.
- Map place search looks for places first (owner, 2026-11-24): "Санкт-Петербург" returned five
  venues and no city, so the Wizard proposed a courthouse as the study area. Places only in the first
  request; points of interest (Mapbox, all types) and OpenStreetMap — districts first — only when no
  place answers.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `survey-study-area`: a map section uses the survey's area, its own, or none; effective area on
  respondent map, refusal and preview; own message translatable; section choice through every surface.
- `survey-editor`: study area controls move to Survey settings → Respondent map; the Map card offers the three choices.
- `survey-serialization`: section study areas ride the archive and survey copies.
- `printable-form`: a printed map is framed on (and draws) its section's effective area.
- `map-place-search`: places are looked up first; points of interest and OpenStreetMap areas only when no place answers.

## Impact

- Model: new `SectionStudyArea` (migration), service `survey/services/study_area.py` grows the
  section functions (still the one writer); `study_area_guard`, `views.study_area_meta`,
  `study_area_views` (`section` parameter), respondent `study_area.js`, `study_area_editor.js`.
- Templates: `_map_card.html`, `survey_settings_panel.html`, `study_area.html`,
  `survey_section_partial.html`, `base_survey_template.html`, `_translation_link.html`.
- `translation_table.py`, `translation_gaps.py`, `serialization.py`, `cloning.py`,
  `print/static_map.py`, `print/pdf.py`, `api/v1/map.py`, `mcp/tools/map.py`; regenerated
  `reference/api.md` and `reference/mcp-tools.md`; help page; `.claude/architecture/map-layers.md`.
- Ordering: archive after `map-layers-study-area` (its deltas create `survey-study-area`).
