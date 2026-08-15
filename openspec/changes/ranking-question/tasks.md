# Tasks — ranking question

## 1. Type

- [x] 1.1 `INPUT_TYPE_CHOICES` gains `ranking`; picker metadata (group, icon, hint) so the parity
      test passes and the type is findable.
- [x] 1.2 Choices editor and validation-field toggles treat `ranking` like the other
      choice-carrying types in the question dialog.

## 2. Widget

- [x] 2.1 `RankingField` / `RankingWidget` + `templates/ranking.html`: one row per item, each
      carrying a hidden input with its code under the question's field name.
- [x] 2.2 `assets/js/components/ranking.js`: pointer drag and keyboard move (Space/Enter to pick
      up, arrows to move), rank numbers repainted after every change.
- [x] 2.3 CSS; include the script in the survey template; collectstatic.

## 3. Server

- [x] 3.1 Save path: a `ranking` branch that stores `selected_choices` in submitted order only
      when the submission is a permutation of the question's item codes.
- [x] 3.2 Prepopulation: restore the stored order when the respondent navigates back; unanswered
      questions keep the creator's item order.
- [x] 3.3 Export: `ranking` in `EXPORT_VALUE_TYPES`; `_answer_cell` returns a mapping of
      item → rank; CSV builder merges mappings as columns.

## 4. Tests

- [x] 4.1 A submitted order round-trips: stored in order, prepopulated in order.
- [x] 4.2 Permutation enforcement: duplicate rank, missing item, unknown code and extra item each
      store nothing.
- [x] 4.3 Export produces one column per item with the rank as the value.
- [x] 4.4 Analytics does not break on the new type (falls back to the answer count).
- [x] 4.5 Live preview renders a ranking draft.
- [x] 4.6 `./run_tests.sh survey` green.

## 5. Records

- [x] 5.1 Spec; backlog #102 ranking slice closed; follow-ups filed (analytics view, top-N).
- [x] 5.2 Commit, push, PR.

## Found while building

- `ranking` was added to `CARD_INPUT_TYPES` but not to `SUBTEXT_IN_TEMPLATE_TYPES`, so the new
  type silently dropped its subtext — the exact bug `subtext-rendering` had just fixed for nine
  other types. Worse, that change's table test did **not** catch it: the table was a hardcoded
  dict, so a type missing from it was simply never checked. The test now asserts its own keys
  equal `INPUT_TYPE_CHOICES`, which is what "a type added later fails this test" was supposed to
  mean.
- `QuestionPreviewLiveTest.test_unknown_input_type_is_rejected` used `ranking` as its example of a
  type the model does not have. It does now — the example was changed, and a test failing because
  the thing it called impossible got built is the good kind.
- The widget script is loaded from `<head>`, so `document.body` does not exist when it runs;
  the htmx re-init listener sits on `document` instead.
