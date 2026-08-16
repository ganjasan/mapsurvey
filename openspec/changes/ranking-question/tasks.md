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

## Review follow-ups (2026-08-15)

- [x] Empty state: a ranking with no items showed a drag hint over nothing. It now points at the
      Choices editor. Stars could be given a default (five steps); ranking items cannot be
      invented, so the fix is to say what is missing.
- [x] `ranking` had no canned Type Example payload, so hovering its card rendered an empty frame.
- [x] Type examples animate (rows lift in turn, stars fill in sequence). Scoped to the example
      frame via `example=1` → `.is-type-example`; the "Respondent sees" pane deliberately does
      not animate, since it shows the creator's own question while they type into it. Wrapped in
      `prefers-reduced-motion: no-preference`. A range animation was written and dropped — a
      native slider thumb cannot be moved from CSS, and a brightness pulse would have been
      movement without meaning.
- [x] The example frame sized to its content instead of a fixed 190px, which had been clipping
      Choices, Multiple Choices and Ranking. Two traps: measuring after `requestAnimationFrame`
      reads the *previous* example, and `body.scrollHeight` inside an iframe can never report
      less than the frame's own height — so the frame grew once and never shrank. Measures the
      content wrapper on load instead.
- [x] A multi-line `{# #}` comment leaked into the rendered page again. The repo's guard test
      caught it, but only at full-suite time, after it had already reached the user's screen —
      recorded as a working rule to run that one test straight after touching a template.

## AI generator (asked 2026-08-16)

- [x] The generation **schema** picked the type up for free: its enum derives from
      `INPUT_TYPE_CHOICES` via `serialization.VALID_INPUT_TYPES`.
- [x] The **prompt** did not — it names the types in prose and had never heard of `ranking`, so
      the model could emit it in principle and never would in practice. Added, with guidance on
      when a ranking is the right question (a trade-off between items) and when `rating` is.
- [x] The **validator** had a real hole: `CHOICE_REQUIRED_INPUT_TYPES` did not include `ranking`,
      whose choices *are* its items — a generated draft could therefore contain a ranking with
      nothing to rank, which no respondent can answer. Fixed.
- [x] Guard added: a test asserts the prompt names every type the schema permits, because a
      derived enum and hand-written prose drift silently. (Same failure shape as the subtext
      table test earlier today.)
- Not changed: the generator never sets `display_style`, so generated ratings inherit the survey
  default rather than asking for stars. Deliberate simplification, noted rather than fixed.
