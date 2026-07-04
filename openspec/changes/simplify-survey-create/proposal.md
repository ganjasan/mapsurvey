# Simplify the Create New Survey page

## Why

The create page currently dumps the entire `SurveyHeaderForm` on the user —
redirect URL, available languages, visibility, thanks HTML (a JSON blob!),
cover image, basemap checkboxes — plus the map picker. At creation time none
of these decisions can be made meaningfully (the survey has no content yet),
and every one of them is already editable later in the Build space's
"Survey settings" panel. The page reads as a pile of unrelated fields with no
sequence of actions ("нет последовательности действий и понимания что это и
зачем" — user feedback, 2026-07-04).

## What Changes

- The Create New Survey form asks only two things, in product order:
  **what is it called** (name) and **where is your survey area** (map picker
  with creator auto-geolocation + the auto-center-on-respondent toggle).
- Everything else — redirect URL, languages, visibility, thanks page, cover
  image, basemaps — is dropped from the form and inherits model defaults
  (`redirect_url="#"`, `visibility=private`, `basemaps=streets/satellite/topo`,
  empty `thanks_html`/`available_languages`, no cover).
- A hint under the actions points to where those options live:
  "Languages, thanks page, and other options — in Survey settings."
- The page adopts the shared `.pr-card`/`.pr-field`/`.pr-help`/`.pr-switch`
  vocabulary (same look as the Survey settings panel it defers to).
- Server-side: a minimal `SurveyCreateForm` (name only) replaces
  `SurveyHeaderForm` in `editor_survey_create`; the settings panel keeps the
  full form. No model or migration changes.

## Impact

- Affected specs: `survey-editor`
- Affected code: `survey/editor_forms.py` (new `SurveyCreateForm`),
  `survey/editor_views.py` (`editor_survey_create`),
  `survey/templates/editor/survey_create.html`
- No data changes; existing surveys and the settings panel are untouched.
