# Design — question type picker rework

## Context

The question modal is a Django `QuestionForm` (ModelForm) rendered field-by-field in
`question_form_modal.html`, submitted over HTMX. `input_type` is a plain `<select>`; a handful of
inline scripts (`toggleChoicesEditor`, `toggleValidationFields`, `toggleDisplayStyleFields`)
already show/hide sections keyed on its value. Edit mode has a real preview iframe fed by
`editor_question_preview`, which builds the section's `SurveySectionAnswerForm` and deletes every
field but one — real render, but only for saved state.

The mockup validated with the user fixed the direction: grouped card grid, 1100px modal, hover
examples, hidden irrelevant fields, and a persistent pane rendering the question as configured.

## Goals / Non-Goals

**Goals**: the picker communicates what each type is by grouping, icon, hint and example; the
preview shows the *configured* question live for new and edited questions; irrelevant fields
disappear; `html` reads "Formatted Text".

**Non-goals**: new input types (ranking stays in #102); touching `INPUT_TYPE_CHOICES` values,
storage, export, respondent rendering, or the admin.

## Decisions

### D1 — Picker metadata lives in Python, one structure, parity-tested

`survey/question_types.py` defines the groups and per-type metadata (icon, hint, display-label
override). The template renders cards from it; the flyout and the hidden-select options come from
the same place. A test asserts its keys equal `INPUT_TYPE_CHOICES` keys, so the next type added to
the model without picker metadata fails loudly instead of silently missing from the dialog.
Rationale: the mockup carried this data in JS; in production JS it would drift from the model.

### D2 — Cards drive the existing hidden `<select>`; the form contract is untouched

The native `select[name=input_type]` remains in the DOM (visually hidden), still owned by
`QuestionForm`. Cards are rendered only for values present in the field's choices — which is how
sub-question restrictions (`SUBQUESTION_DISALLOWED_INPUT_TYPES`) keep working for free — and a
click sets the select's value and dispatches `change`, so every existing toggle listener fires
unmodified. The save path sees exactly the POST it saw before.

### D3 — Live preview is a real server render of unsaved state, not a JS lookalike

New endpoint `editor_question_preview_live` (POST, `survey_permission_required('viewer')`,
same-origin frame headers): takes the modal's current values (`input_type`, `name`,
`choices_json`, `display_style`, `color`, `icon_class`), builds an **unsaved** `Question` bound to
the section, and renders the existing `question_preview_frame.html` through the same
`SurveySectionAnswerForm` machinery respondents hit. The client debounces form changes (~400ms),
fetches, and writes the HTML into the pane's iframe via `srcdoc`.

- Shared factory: `_get_form_from_input_type` has an unused `self` — it becomes a classmethod,
  and a `single_question_form(question, language)` classmethod builds a one-field form.
  `editor_question_preview` is refactored onto it (behaviour unchanged); the live endpoint is then
  ~20 lines.
- The unsaved `Question` is never saved; `choices_json` is parsed defensively (invalid JSON →
  no choices, the form's existing no-choices fallbacks apply).
- Rejected alternative: client-side approximation (as in the mockup). It would be a second,
  drifting implementation of every widget; the server render is the truth and already exists.
- Rejected alternative: extending the GET endpoint with override params. The value set (choices
  JSON, translated names) is POST-shaped, and a draft of a *new* question has no `question_id` for
  the existing URL.
- Image uploads are not previewed (the file lives client-side only); the pane shows the stored
  image for saved questions and a placeholder otherwise.

### D4 — Hover examples are real renders of canned payloads

Hovering a card shows a "Type example" box in the preview column, directly under the "Respondent
sees" pane (two review follow-ups: a floating flyout beside the modal read as detached from the
dialog, and hand-written HTML snippets did not look like the product's actual widgets — the range
slider gave it away). Each type has a small canned payload (generic fruit-survey question +
choices) that is POSTed to the same live-preview endpoint the pane uses and rendered into an
iframe, cached per type per modal open. Two deliberate exceptions stay illustrations: `image`
(without an uploaded file there is nothing real to render) and the three geo types — their real
widget is only the draw button, the map lives beside it in the survey, so a mini-map showing the
drawn point/line/area is what actually communicates the interaction (review follow-up: the
real-render geo example read as an empty button). The examples deliberately show a *generic*
question, distinct from the configured one in the pane — the two answer different questions
("what is this type?" vs "what will mine look like?").

### D5 — Modal layout

`#questionModal .modal-dialog` gets a `question-modal-xl` class (max-width 1100px). The modal body
becomes two columns: form (flexible) and preview pane (~340px, sticky). Below Bootstrap's `lg`
breakpoint the pane is hidden — the 500px experience degrades to today's, minus the flat list.
The edit-mode iframe moves into the pane and is superseded by the live render after first change.

### D6 — Field visibility extends the existing toggles; hiding never clears data

One new `toggleTypeScopedFields` keyed on the same select: Color + Icon class visible for
`point`/`line`/`polygon`; Image visible for `image`; Required hidden for `image`/`html`. CSS-hidden
inputs still submit, so stored values pass through unchanged — a text question that once got an
accidental image keeps it in the DB (deciding what to do with those is #111's separate note, out
of scope). Hidden `required` checkboxes are the one exception (unchecked semantics), which is
correct: display blocks cannot meaningfully be required.

### D7 — "Formatted Text" is a display-layer rename

`display_label` in the metadata; the stored value, export column behaviour and admin remain
`html`. No migration, nothing to backfill.

## Risks / Trade-offs

- **Preview latency / request volume**: one debounced POST per edit burst, per open modal, gated
  to authenticated editors — negligible next to the analytics endpoints. Mitigation: 400ms
  debounce, in-flight request superseded by the next.
- **Geo widgets in the pane**: `question_preview_frame.html` already renders draw buttons inert
  (`pointer-events:none`); same for the live render, no map is initialised.
- **`modal-lg` → 1100px** changes a familiar dialog's size; the mockup review explicitly chose
  this, and the sm fallback keeps small screens working.
- **Two sources of "what does this type support"** (metadata hints vs toggle functions) — both
  live in the same template/module pair and the spec pins them; folding toggles into the metadata
  would be a larger refactor than #111 warrants.

## Migration Plan

Pure frontend + one additive endpoint; deploys with no data steps. Revert = revert the commit.

## Open Questions

- None blocking. Follow-up candidate (not this change): fold `subtext` and translations into the
  live preview payload so the pane reflects them too.
