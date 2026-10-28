## Why

Every map section renders one way: a fixed 420 px text panel on the left, the map on the rest; the only alternative is the centred `form` card. A creator cannot put a picture where the map is, cannot move the text to the right and cannot widen the panel — so a welcome screen like Senf's ("photo on the left, text and a Start button on the right", Carroll Creek case study) is out of reach, and so is a wide reading column next to a map. Senf is the closest direct rival and this is where its surveys visibly look better (issue #473).

Rather than restyling surveys for everyone, give the creator three independent per-section controls whose defaults reproduce today's rendering exactly.

## What Changes

- **Stage** — what fills the part of the screen the panel does not: `SurveySection.layout` grows a third value, `image`, beside `map` and `form`. An `image` section shows a picture (`SurveySection.stage_image`, falling back to the survey's `cover_image`) where a map section shows the map; like `form`, it has no map and cannot hold geo questions.
- **Panel side** — new `SurveySection.panel_side`: `left` (default, today) or `right`. The map chrome that today makes room for the panel on the left (Leaflet controls, the hide/show-panel buttons) moves with it.
- **Panel width** — new `SurveySection.panel_width`: `default` (420 px, today), `third` or `half` of the viewport. Presets only, no free numbers.
- **Mobile**: below 768 px the panel is already a full-width overlay over the map, so side and width have no effect there; an `image` section renders the picture as a band above the text, the text scrolling beneath it. The Preview pane of the editor shows the same.
- The three values are display settings: a SAFE edit on a live survey (no "Unpublished changes"), carried by the draft copy, duplicate/paste, the ZIP backup (with the image file), the REST API and the MCP `create_section`/`update_section` tools.
- The section modal gets a "Layout" block: stage, side, width, picture upload, shown only where they apply (side/width for `map` and `image`, the picture for `image`).

Out of scope, later steps of the same direction: a partner-logos row on the welcome page, a muted basemap, image choices (`image_grid`), theme presets, a custom domain.

## Capabilities

### New Capabilities

(none — the three controls extend the existing section-layout capability)

### Modified Capabilities

- `section-form-layout`: the layout requirement becomes three independent per-section controls (stage `map | form | image`, panel side, panel width); the `image` stage inherits the `form` rules (no map, no map chrome, no geolocation prompt, no geo questions); a mobile requirement fixes what side/width/image mean below 768 px; the serialization and editor requirements cover the new fields and the image file.

## Impact

- `survey/models.py` (+ migration `0106`): `layout` choices, `panel_side`, `panel_width`, `stage_image`; the geo-exclusion set `form` → `{form, image}` lives in ONE constant used by `SurveySectionForm.clean_layout`, `QuestionForm` and the type picker.
- Respondent page: `base_survey_template.html` (body classes from the section, the stage image element beside `#map`, the HTMX layout-switch step), `partials/survey_section_partial.html` (data attributes), `assets/css/main.css` (mirrored panel/chrome rules under `body.panel-right`, a `--panel-w` variable for the width presets, the image stage, the mobile block).
- Editor: `editor_forms.SurveySectionForm` (+ files), `section_detail_form.html` (multipart form, Layout block, show/hide JS, map-position button), `editor_views.editor_section_detail` → `services.sections.update(..., files)`.
- Copies: `cloning.copy_section` copies the image file like `Question.image`; `plain_field_values` carries the three plain fields unchanged (`DraftCopyKeepsFieldsTest`, `DuplicateSurveyKeepsFieldsTest`).
- ZIP: `serialization.serialize_sections` / section import (+ `images/sections/<code>_<name>` beside `images/structure/`).
- API / MCP: `api/v1/schemas.py` (`SectionIn`, `SectionOut`), `forms_bridge.SECTION_FIELDS`, `api/v1/out.py`, `mcp/tools/sections.py` descriptions; regenerated `help/.../reference/api.md` and `reference/mcp-tools.md`.
- Help centre page for sections/layout, a "What's new" entry, creator strings in every offered catalog.
- Tests: `survey/tests/test_section_form_layout.py`, `api/tests`, `mcp/tests`.
