# Proposal: mapless-sections

## Why

Every section renders as a narrow panel beside a map, even when no question in it touches
the map. Real surveys are mixed — demographics, consent, instructions, feedback sit around
the mapping core — and today those parts waste the screen, invite pointless map
interaction, and force fakery: the Olney demo's welcome had to be built as a Formatted
Text block pretending to be a question, with a useless map beside it (backlog #144/#145,
epic field-data-collection FD-15/FD-16).

## What Changes

- A section gets a `layout` setting: `map` (today's behavior, default) or `form` — a
  classic full-width web form, Google Forms style.
- The respondent page switches mode per section as HTMX swaps the panel: on a `form`
  section the panel becomes the page body (centered column), the map is hidden; navigating
  to a `map` section restores the split view. The map instance is never destroyed — the
  persistent-map behavior stays.
- Geo question types are blocked in `form` sections (picker hides them; server refuses),
  and a section holding geo questions refuses to switch to `form`.
- The welcome-page case falls out: a `form` head section with a Formatted Text block is a
  welcome page. Its forward button is named by the creator: each section gets an optional
  translated button label (empty = Next/Finish) — decided over an inferred "Start"
  heuristic after review.
- Survey theming (backlog #146, pulled in mid-change): one accent color per survey in
  `style_settings`, applied to respondent buttons, dropdown highlight and the form-page
  tint; validated as `#RRGGBB` at save, import and render.
- `layout` and the button label round-trip through export/import; absent keys = defaults.

## Capabilities

### New Capabilities

- `section-form-layout`: how a `form`-layout section renders and behaves for respondents
  (full-width form, hidden map, mode switching across HTMX navigation, creator-named
  forward button), and the constraint that geo questions and form layout exclude each
  other.
- `survey-theming`: the per-survey accent color — where the creator sets it, where it
  applies, and the triple validation that keeps a stored value from becoming CSS
  injection.

### Modified Capabilities

- `survey-editor`: section settings expose the layout choice; question type picker and
  question save respect the section's layout; layout switch is refused while geo questions
  exist.
- `survey-serialization`: sections serialize the `layout` key; import defaults it to `map`.

## Impact

- `survey/models.py` — `SurveySection.layout` CharField + migration (additive, default `map`).
- `survey/templates/base_survey_template.html`, `partials/survey_section_partial.html`,
  `survey/assets/css/main.css` — layout mode class, full-width form styles, Start label.
- `survey/editor_forms.py` / `editor_views.py` / section + question editor partials —
  layout field, geo-type gating both directions.
- `survey/serialization.py` — section `layout` export/import.
- `survey/tests.py` — respondent rendering both modes, gating, round-trip; template guard
  after each template edit.
