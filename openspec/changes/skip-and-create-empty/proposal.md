# "Skip and Create Empty Survey" — the manual path stops asking for anything

## Why

`/editor/surveys/new/` reads as one form with two exits, and the manual exit is the one
that looks like the consolation prize. The button says "Create empty" — next to a filled
AI panel that says "Generate draft" — and it silently carries the map framing the creator
never asked to do: the picker syncs `map_lat/lng/zoom` from the map centre on every
`moveend`, so *something* is always posted, even by a creator who scrolled past the map.

Two consequences:

- The manual path is not actually a skip. A creator who wants "just give me an editor"
  still has a map picker between them and the editor, and the survey they get is framed on
  whatever the picker happened to be showing (Berlin, or wherever geolocation landed) —
  a position they never chose and now have to find in Survey settings to fix.
- The button is one click away from throwing away a brief the creator just typed. Nothing
  warns them. `create-empty-blocked-by-brief` fixed the opposite failure (the brief
  *blocking* the button); the button silently discarding the brief is the same seam from
  the other side.

## What Changes

- **The button is renamed to "Skip and Create Empty Survey".** It is a skip, and it should
  say so: skip the AI draft, skip the map framing, land in the editor. The label change
  applies only where there is something to skip — i.e. when the AI panel is rendered.
- **The skip action ignores the map picker entirely.** It posts `action=empty_skip`, and
  that branch applies neither `map_lat/lng/zoom` nor `default_basemap`; the survey is
  created with the model's default start position, zoom and base map, and the creator sets
  the map later in Survey settings. `action=empty` (the no-AI-panel button, legacy POSTs,
  and a POST with no action at all) keeps applying the map exactly as today — without the
  AI panel the picker is the only reason that page has a right-hand column.
- **A filled brief is confirmed before it is discarded.** If any of `goal`, `audience` or
  `map_target` holds non-whitespace text, clicking the skip button raises
  `Dialog.confirm` ("Create an empty survey? Your AI brief won't be used…"); cancelling
  leaves the page and the brief untouched, confirming submits. The use-case chip is *not*
  part of the test — it ships preselected (`initial='urban_planning'`), so treating it as
  "filled in" would prompt every creator who never touched the panel.

## Impact

- Affected specs: `survey-editor`
- Affected code: `survey/editor_views.py` (`editor_survey_create`),
  `survey/templates/editor/survey_create.html`, `survey/tests.py`
- No model change, no migration, no change to the generate path — `_start_survey_generation`
  still reads the map fields and still frames the AI draft on what the creator picked.
- The pre-existing `action=empty` contract is untouched, so every current test and any
  bookmarked/scripted POST keeps its behaviour.
