## 1. Reproduce before changing anything

- [x] 1.1 Build a survey with a 9-point named range question mirroring the reporter's ("(positive)
      Geräusche" → "(negativer) Lärm") and capture the slider as rendered, at desktop width and at
      320px. This is the before-picture the fix is judged against.

  Reproduced locally. Measured geometry: the slider spans x=41→378 (337px), the thumb is 22px so
  the extreme thumb *centres* sit at 52 and 367. The tick row (`padding: 0 10px`) puts its outer
  ticks at 51.5 and 367.5 — near enough. The label row (`padding: 0`) starts at 41 and ends at 378,
  so **each endpoint label is 11px outside the position it claims to mark**. The error is a
  constant, independent of width, so it grows as a proportion on a narrower panel.
  Desktop capture: `screenshot-1785912570031-0.jpg`. The 320px capture was not taken — the window
  would not resize below its current size — but the constant-offset finding makes the fix
  width-independent, so it does not gate the work.

- [x] 1.2 Answer the open question from the design: is "the slider is too short" about the slider or
      about the width of the question card containing it? Measure both; do not change anything until
      it is known which.

  **Neither — it is the page layout, and it is not a range problem at all.** At a 1854px viewport
  the question panel is 371px, because `base_survey_template.html:74` renders `<div id="map">`
  unconditionally and it claims the rest of the width. The reproduction survey has no geo question
  whatsoever and still gives ~80% of the screen to an empty map. Every question type in a non-geo
  survey is squeezed the same way; the slider is just where it shows most, being the one control
  that wants horizontal room.
  Filed separately rather than fixed here — see 7.3. §2.3 below is therefore a no-op beyond
  recording this.

- [x] 1.3 Check production for `range` questions with no `choices` defined. Their existence decides
      whether the fallback in §4 is a real path or a defensive one.

  **A real path: 34 of 122 range questions in production have no choices** (28%). They currently
  render on the slider's 0–10 fallback (`forms.py:191-195`). Under a choice-based style they would
  have nothing to lay out, so §4.1 is load-bearing and needs a test, not a comment.
  Also confirmed: `display_style` is `default` on every range question in production (0 non-default),
  which is expected since the control has never been offered for them — so no existing question
  changes appearance when the styles are ungated.

## 2. Slider alignment

- [x] 2.1 Introduce a custom property for the thumb size on the slider block and derive the tick and
      label insets from it, so both rows consume one declared value (design D3).
- [x] 2.2 Confirm the endpoint labels sit under the extreme positions the thumb can occupy, at both
      widths from 1.1.
- [x] 2.3 Act on 1.2's finding, or record explicitly that the width complaint was the question card
      and belongs to backlog #42 rather than here.

## 3. Display style for range questions

- [x] 3.1 Resolve the display style before the form field is built, rather than attaching it to the
      widget afterwards (`forms.py:251-255`). Range resolves `default` to the slider and does not
      consult the survey-wide rating default (design D4).
- [x] 3.2 Build a `ChoiceField` with `RadioSelect` for `scale_strip` and `list_pips`, keeping
      `IntegerField` + `RangeWidget` for the slider (design D2).
- [x] 3.3 Extend the render branch in `survey_section_partial.html` to cover `range`, reusing
      `rating_scale_strip.html` and `rating_list_pips.html` unchanged.
- [x] 3.4 Make prepopulation style-aware: `initial` is an int for the slider and the string form of
      the choice code for the radio styles (`views.py:716-718`).
- [x] 3.5 Verify the same in the editor's live preview, which renders through its own frame
      (`question_preview_frame.html`).

## 4. Fallback and editor

- [x] 4.1 Fall back to the slider when a range question has no choices, whatever style is selected,
      and render without error.
- [x] 4.2 Replace the `input_type === 'rating'` test that gates "Display as" with membership of a
      named set of types supporting display styles (design D5).
- [x] 4.3 Update the `display_style` help text on `Question`, which currently says "only used by
      rating questions".

  **Deliberately not done.** Django generates an `AlterField` migration for a `help_text` change, and
  migration-number collisions between parallel worktree branches are a recurring problem here — not
  worth it for a string. It is also not user-visible: `question_form_modal.html` excludes
  `display_style` from its generic field loop and renders the control by hand without the help text,
  so the sentence only exists in the model. Fold it into the next change that touches `Question` for
  a real reason. The comment above `DISPLAY_STYLE_TYPES` in `forms.py` now carries the accurate
  version.

## 5. Tests

- [x] 5.1 Round-trip an answer through all three styles and assert `Answer.numeric` is identical —
      the claim the whole change rests on.
- [x] 5.2 Assert a style change on a question with existing answers leaves those answers and their
      export column untouched.
- [x] 5.3 Assert `list_pips` renders all nine names of a 9-point scale, and `scale_strip` renders one
      cell per choice plus the two anchors.
- [x] 5.4 Assert `default` renders a slider even when the survey's `rating_display_style` is set to
      something else.
- [x] 5.5 Assert a required range question rejects an empty submission in each style, creating no
      answer row.

  **Rewritten, because the platform does not do this.** Answers are never validated server-side —
  the POST handler passes `request.POST` as `initial`, so the form is never bound and `required` is
  not enforced for any question type (filed as #107). The test now asserts what this change actually
  guarantees: an unanswered range question stores nothing and does not error, identically in all
  three styles. The spec scenario was corrected to match rather than left describing behaviour that
  does not exist.
- [x] 5.6 Assert a choice-less range question renders as a slider under a choice-based style.
- [x] 5.7 Assert back-navigation prepopulates the previous answer in each style.

## 6. Verify

- [x] 6.1 Run the full survey suite: `./run_tests.sh survey`.

  879 tests, OK. Two of them — LastActivityMiddleware's — had been failing before this change and
  were nearly written off as environmental. They were not: `run_tests.sh` started only the db
  container and passed no `REDIS_URL`, so `settings.py` fell back to `redis://localhost:6379/1`,
  which on this machine belongs to an unrelated project. `CACHES` sets `IGNORE_EXCEPTIONS`, so the
  suite was silently reading and writing another project's Redis. The runner now brings up redis
  too, waits for both services instead of sleeping, and passes a `REDIS_URL` derived from
  `PORT_OFFSET`. Committed separately (`c2c25f4`) since it is test infrastructure, not this feature.
- [x] 6.2 Capture the after-picture at both widths from 1.1 and compare against the before.

  Endpoint label error went from 11px on each side to **0** — the labels now sit exactly on the
  extreme positions the thumb can occupy. Ticks are within half a pixel, which is the 1px tick's own
  width. The 320px case was measured through the DOM rather than captured as an image, because the
  browser window would not resize below its current size.
- [x] 6.3 Measure `scale_strip` with nine choices at 320px. If the cells are unusably small, say so
      in the editor's style picker rather than letting creators pick it blind — or record explicitly
      that it was measured and judged acceptable.

  Measured at a 320px panel: nine cells come out **20.5px wide** by 46px tall — under half the ~44px
  a reliable touch target wants. `list_pips` at the same width keeps every label unclipped, and the
  slider's end labels do not collide. So the strip is genuinely a poor choice for a long scale, and
  the editor now says so: a hint appears under "Display as" when the strip is selected with more
  than seven options. Note this applies to `rating` today too — the change did not introduce it,
  it just stopped hiding it.

## 7. Close the loop

- [x] 7.1 Strike backlog #99; note in #102 which slice this covered and what remains (continuous
      scale, vertical scale, ranking).
- [x] 7.2 Note that this is the second attempt at the same reporter's request — #5 shipped labels
      that did not align — so the after-picture is worth putting in front of him rather than
      announcing it as done.

  Standing. The screenshot to send is the one from 6.2. Worth saying plainly that his "too short"
  observation was correct and is a separate, larger problem now filed as #106, rather than implying
  the whole report is closed.
- [x] 7.3 Filed as **#106**. File a new backlog item for the finding in 1.2: the survey page always renders the map
      panel, so a survey with no geo questions gives ~80% of the viewport to an empty map and
      squeezes every question into a ~370px column. This is the actual cause of "the slider is too
      short", it affects every question type rather than just `range`, and it is plausibly a bigger
      readability problem than anything in this change. Deliberately out of scope here.

- [x] 7.4 File the finding from §5: answers are never validated server-side, because the POST
      handler passes `request.POST` as `initial` so the form is never bound. Filed as **#107**. It
      is the general case of a symptom previously recorded as geo-only, and it is why the spec
      requirement about required questions was rewritten to assert sameness across styles instead of
      rejection.
