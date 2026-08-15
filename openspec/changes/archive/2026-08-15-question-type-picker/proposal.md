# Question type picker rework

## Why

The New/Edit Question dialog presents `INPUT_TYPE_CHOICES` as one flat thirteen-entry dropdown in
a `modal-lg` dialog. Three separate reports now trace back to it:

- **2026-08-09** (backlog #112): the list mixes display blocks (`image`, `html`) that collect
  nothing with real questions and geo questions, in drifted order, with no grouping.
- **2026-08-09** (backlog #111): Color, Icon class and Image are offered on every type and do
  nothing on most — Image being the damaging one, since an upload against a text question is
  accepted, stored, and never rendered, with no signal to the author.
- **2026-08-14** (Jannis Hamp, jhmp): a user emailed asking for a "ranking" question type when
  one `rating` question per item already covers his case — he could not tell from a flat list of
  names. The picker is now costing us feature requests for capabilities we already have.

A name in a dropdown does not tell a creator what the respondent will see. A picture does. The
editor already proves this server-side: the edit dialog renders a real preview iframe
(`editor_question_preview`), but only for questions that are already saved, and it only refreshes
on Apply — the one moment a creator most needs the preview is while choosing a type for a new
question, and that is exactly when it is absent.

## What Changes

- The question modal grows to a wide two-pane layout: form on the left, a persistent
  **"Respondent sees" preview pane** on the right (hidden on narrow viewports).
- The input type dropdown is replaced by a **grouped card grid** — Questions / Map questions /
  Display blocks — one card per type with an icon and a one-line hint. The native `<select>` stays
  in the form, hidden, as the submitted control; cards only set its value. Sub-question type
  restrictions continue to come from the form field's choices.
- Hovering a card shows a **canned example** of that type under the preview pane — rendered
  through the same server-side machinery, so the example is the real widget, not an imitation —
  and the choice is made by picture rather than by name.
- The preview pane renders the question **as currently configured, before it is saved**: a new
  endpoint accepts the modal's unsaved values (type, text, choices, display style, colour, icon)
  and returns the real respondent-side render built by `SurveySectionAnswerForm` — the same code
  path respondents hit, not a lookalike. Works for both new and existing questions; edits are
  reflected live, debounced, without Apply.
- **Irrelevant fields are hidden per type** (#111): Color and Icon class appear only for geo
  types, Image only for the `image` type, Required disappears for display blocks. Hiding is
  presentation-only — stored values are not cleared.
- The `html` type is **displayed as "Formatted Text"** with a paragraph icon; creators do not
  know what "HTML" means. The stored `input_type` value stays `html` — display-layer rename only,
  no migration.

Direction, grouping, sizes, live-preview behaviour and the rename were all validated on an
interactive mockup ([question-type-picker.mockup.html](question-type-picker.mockup.html)) and
chosen explicitly: card grid, 1100px, hover examples, hidden irrelevant fields, live
configured-state preview.

Not in scope: a real ranking input type (backlog #102 keeps it), any change to
`INPUT_TYPE_CHOICES` values or the save path, the Django admin's question form.

## Capabilities

### New Capabilities

- `question-type-picker`: how the question editor presents the set of input types to a creator —
  grouping, naming, iconography, per-type hints and examples, which settings fields are offered
  for which type, and the live respondent-side preview of the question being configured.

### Modified Capabilities

None. Respondent-side rendering, storage and export are untouched.

## Impact

- `survey/question_types.py` — new: picker metadata (groups, icons, hints, display labels), the
  single source the template renders from; parity-tested against `INPUT_TYPE_CHOICES`.
- `survey/forms.py` — `_get_form_from_input_type` becomes a classmethod; small factory building a
  one-field form for a possibly-unsaved question (shared by the existing preview and the new one).
- `survey/editor_views.py` — new `editor_question_preview_live` endpoint (POST, permission-gated
  like the existing preview); `editor_question_preview` refactored onto the shared factory.
- `survey/urls.py` — one route.
- `survey/templates/editor/partials/question_form_modal.html` — layout, card grid, flyout,
  extended visibility toggles, live-preview wiring.
- `survey/templates/editor/survey_detail.html` — modal dialog width.
- `survey/assets/css/editor.css` (or main.css) — picker/flyout/pane styles; collectstatic.
- `survey/tests.py` — parity test, preview endpoint tests.
- No migration. Backlog #111 and #112 closed; #103's hint surface improves as a side effect.
