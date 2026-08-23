# Design — Geo Multi-Feature UX

Interactive mockup (browser-tested): `geo-multi-feature-ux.mockup.html` in this folder.

## Context

Respondent geo flow today (`base_survey_template.html`):

- Delegated click handlers on `.drawpoint` / `.drawline` / `.drawpolygon` set `currentQ`
  and enable a Leaflet draw handler (points go through the crosshair overlay instead).
- `draw:created` binds the sub-question popup and opens it; the popup's `layer-apply`
  handler serializes the form into `feature.properties`, closes the popup and sets
  `currentQ = null` — **this is where the flow dies** and where the respondent (and the
  creator watching Preview) concludes the question takes one feature.
- All features live in one `editableLayers` FeatureGroup; each carries
  `feature.properties.question_id`. Serialization to the pipe-joined `geo-inp` value
  happens at `htmx:configRequest`.
- `restoreGeoAnswers()` re-creates layers on back-navigation with the same wiring.

Editor already persists per-type `vs_*` inputs into `Question.validation_settings` (JSONB)
in `editor_question_edit`; the section POST in `views.py` saves geo answers with no
validation at all (`required` is client-only).

## Goals / Non-Goals

**Goals**: make multiplicity visible per question (counter, list, progress); keep the
draw cycle alive after each feature; give creators min/max feature limits without a
migration; keep a `max=1` question looking like today.

**Non-Goals**: clone detector / merge tool in the editor; AI validator rule; reworking the
popup or crosshair flows; server-side form-error rendering for the section POST; changes to
export or public results.

## Decisions

1. **All counts derive from `editableLayers`** — no parallel JS state. One function
   `refreshGeoQuestionUI()` walks the layers, groups by `properties.question_id`, and
   updates every geo block (chip, title, progress, list, disabled state). Called after
   `draw:created`, popup apply, delete, `restoreGeoAnswers`, and in `initSection`.
   Rationale: the layer group is already the single source of truth for serialization;
   a second counter would drift.

2. **No auto re-arm — completing a feature returns to the panel.** (Revised after a live
   walkthrough: the first build re-armed drawing after each popup save, and with several
   geo questions in one section the respondent lost track of which question they were
   answering.) After popup apply — and after `draw:created` for questions without
   sub-questions — the panel comes back and the respondent explicitly picks the next
   question. The just-completed question stays one click away from its next feature.

3. **Button state lives in `refreshGeoQuestionUI()`**, driven by
   `data-min-features` / `data-max-features` attributes rendered on the button.
   The question **title is never replaced** — it is the only thing distinguishing several
   geo questions in one section. Multi-feature state is conveyed by the counter chip and
   the subtitle line ("＋ Add another — up to N more" / "Maximum reached…"); the subtitle
   element renders even when the creator wrote no subtext so the invitation has a place.
   The original subtitle is kept in a `data-` attribute so the swap is reversible. A
   question with `max_features == 1` skips the chip/progress/list — visually identical to
   today after its single feature is placed. At max the button disables.

4. **No per-feature list in the panel.** (Revised after review: an early build listed each
   feature as an "Answer N · attrs" row; the rows duplicated the map pins and the chip
   while carrying no information of their own, and degenerated to pure noise on questions
   without sub-questions.) Editing and deleting placed features stays where it always was —
   the feature's popup on the map. The progress indicator moved **inside the button**
   (under the subtitle) so it is unambiguous which question it belongs to; at max the
   button disables, and the recovery path is deleting a feature via its map popup.

5. **Widget plumbing**: `_get_form_from_input_type` already receives the `question`;
   `LeafletDrawButtonField`/`Widget` gain `min_features`/`max_features` passed from
   `question.validation_settings` and rendered as `data-min-features`/`data-max-features`
   plus the chip/progress/list containers in `leaflet_draw_button.html`. Empty attrs when
   unset.

6. **min enforcement rides the existing required-validation block** in
   `htmx:configRequest`: it already counts geo answers per `geo-inp`; extend it to compare
   the feature count against `data-min-features` (forward navigation only, same `isBack`
   guard), reusing `is-required-invalid` highlighting and the `#required-summary` note.

7. **Server clamps, doesn't reject.** In the section POST geo branch, slice
   `geostr_list` to `max_features` when set. The POST path has no error rendering (even
   `required` is client-only there), so bounding stored data is the honest scope; a real
   error path is a separate change if ever needed.

8. **Editor UI mirrors the other `vs_*` fields**: two small number inputs shown for
   point/line/polygon types in `question_form_modal.html`, saved in `editor_question_edit`
   as ints with `max >= min >= 0`, `max >= 1`; blank removes the key. Invalid range is a
   form error (`QuestionForm.clean` or view-level check consistent with current style).

9. *(Dropped.)* The stray-click guard existed for the auto re-arm; with decision 2 revised
   to "no auto re-arm" there is no drawing mode active when the popup's save click lands.

## Risks / Trade-offs

- **One extra click per feature vs the auto re-arm variant.** Deliberate: the walkthrough
  showed orientation loss beats the saved click. The click lands on a button whose chip
  and subtitle now advertise "add another", which is the affordance creators were missing.
- **Choice-label lookup for row summaries** parses widget HTML; if fragile, fall back to
  raw values — the row still works, only less pretty.
- **`refreshGeoQuestionUI` runs on every mutation**; sections have tens of features at
  most, so a full rebuild is fine.

## Migration

None. No schema change; absent `validation_settings` keys reproduce current behaviour.
Existing multi-clone surveys keep working unchanged (each clone simply gains its own
counter — which reads oddly but is not a regression, and nudges creators to merge).
