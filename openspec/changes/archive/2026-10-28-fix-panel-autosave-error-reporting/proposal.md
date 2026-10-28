## Why

PostHog Replay Vision scored a session **4.0 / 10 frustration** on 2026-09-21: a persistent
*"Not saved — retry"* in **Survey settings** that several clicks never resolved. The creator is
James Neimeister (Resilient Cities Network, user 413) — the same lead who reported
backlog #179 with "I think this is a very early stage product".

`editor_survey_settings_panel` answers an invalid autosave POST with
`JsonResponse({'ok': False, 'errors': form.errors}, status=400)` (`editor_views.py:625`). The
panel's inline autosave rejects on `!r.ok` and catches with
`.catch(function(){ setStatus('error'); })` — `form.errors` is parsed by nobody. The creator
gets a red line naming no field, every further edit repeats it, and retrying re-posts the same
invalid data, so the state is permanent until they guess which field (a too-long name, a
malformed `redirect_url`, a bad accent colour) the form is rejecting. The status element is
also not clickable here, so "retry" names an action the widget does not offer.

**The error the creator actually saw came from a module that had no business on that page.**
`editor_autosave.js` exists for question EDIT forms; it claims `form[data-autosave]` — and the
editor PANELS carry that attribute too, for their own autosaver. So every change in Survey
settings also fired a question autosave, which POSTed to `form.getAttribute('hx-post')` — `null`
on a panel form — producing `fetch("null")` → 404, and then wrote
*"Not saved — tap to retry"* into the first `.autosave-indicator` in the form. On the settings
panel that element is the MAP's indicator (`#survey-map-status`), which is why the message
appeared under the auto-center switch the creator had just touched, why it said "tap to retry"
rather than the panel's own "retry", and why nothing ever cleared it: it fired again on the
next keystroke. Confirmed in a browser against this branch's dev server before the fix —
`fetch("null") → 404` on every settings change. It is live on production now.

Two further defects sit under it.

First, the reason a real validation failure was permanent too. `redirect_url` is
`CharField(max_length=250, default="#")` with no `blank=True`, so the ModelForm makes it
**required** — while `"#"` is exactly how the model spells "no redirect" (`views.py:1324`
sends the respondent to the thanks page when it sees it). A creator who clears that box
because they want no redirect gets `{"redirect_url": ["This field is required."]}` back on
**every** autosave of the whole panel, whatever field they actually touched. That is why
flipping the auto-center switch appeared to fail, and why no number of retries helped: the
only escape was guessing to type `#` back in.

Second, the same fifteen lines are pasted into three panels — Survey settings, Thanks page and Public
results — each with the same swallow. Fixing only the reported surface leaves the other two to
be rediscovered from a replay later, which is how backlog #180 reached a fourth template six
days after a fix covered three.

Two things the backlog card claims are already fixed on master and are NOT in this change:
PR #192 replaced the "Save map position" button with `MapPositionPicker`, so the auto-center
switch now saves through its own endpoint with its own indicator, and that indicator already
binds a retry click.

## What Changes

- `editor_autosave.js` attaches only to forms that carry `hx-post` — the question forms it was
  written for. A panel form is no longer claimed by it, so the stray 404 and the error it wrote
  into someone else's indicator are gone.
- New `survey/assets/js/panel_autosave.js`: one debounced autosaver for editor panels.
  - A 400 carrying `errors` is a **validation** failure: the status names the first failing
    field by its visible label and its message, the field is marked `is-invalid`, and no retry
    is offered — retrying cannot help until the value changes.
  - Any other failure is a **transport** failure: the status says so and the indicator becomes
    a retry control, as `editor_autosave.js` already does for question forms.
  - A successful save clears every mark and message it set.
- Survey settings, Thanks page and Public results drop their inline copies and call it. Their
  existing behaviour is preserved through options: `beforeSave` (thanks-page Quill sync),
  `exclude` (the Public results slug field, the reference-layer controls), and `onSaved`
  (preview reloads, `sectionSaved`).
- `redirect_url` becomes optional in `SurveyHeaderForm`, and an empty value is normalised to
  the `"#"` sentinel the model already defaults to and the respondent views already read. No
  migration: the model keeps its default, only the form stops demanding the field.
- The auto-center switch is excluded from the settings form's autosave. It carries no `name`
  and saves through `MapPositionPicker`; today flipping it also fires a settings POST it is not
  part of, so a validation error lands under the switch the creator just touched and reads as
  "the geolocation setting failed".
- Tests: a 400 with errors names the field and offers no retry; a network failure offers one; a
  later success clears the mark; the three panels reference the shared module and hold no
  `setStatus('error')` of their own; the switch is not bound to the settings autosave; an empty
  Redirect URL saves and stores `"#"`; the endpoint still answers 400 with a per-field `errors`
  map, which is the contract the client now reads.

## Capabilities

### New Capabilities
- `survey-editor`: "Editor panel autosave error reporting" — what an autosaving panel tells the
  creator when a save fails, and when a retry is offered.

### Modified Capabilities
- none. "Survey settings editing" and "Survey default map position picker" keep their contracts.

## Impact

`survey/assets/js/panel_autosave.js` (new), `survey/assets/js/editor_autosave.js`,
`survey/editor_forms.py`,
`survey/templates/editor/partials/survey_settings_panel.html`,
`survey/templates/editor/partials/thanks_panel.html`, `survey/templates/editor/public_results.html`,
`survey/templates/editor/editor_base.html` (script tag + the `is-invalid` style), `survey/tests.py`.
No migration, no model change, no endpoint change — the 400 contract the views already emit is
what the client starts reading. Static assets: `collectstatic` (see `feedback_static_files`).
