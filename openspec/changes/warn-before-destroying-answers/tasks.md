## 1. Counting helper

- [x] 1.1 Add a helper returning the number of answers beneath a question — its own plus its
      sub-questions' — and one for a section covering all its questions and their sub-questions
      (design D2).
- [x] 1.2 Unit-test the traversal directly, before any view uses it: question alone, question with
      sub-questions, section spanning both, and the zero cases.

## 2. Server-side guard

- [x] 2.1 `editor_question_delete`: when answers exist and the request carries no acknowledgement,
      return 409 with the count and delete nothing.
- [x] 2.2 `editor_section_delete`: the same, counting across the whole section. Take care that the
      neighbour re-linking that runs before the delete does not happen on the refused path — the
      current code re-links first and deletes after.
- [x] 2.3 Proceed normally when the acknowledgement is present, and when there are no answers to
      lose.
- [x] 2.4 Include in the response whether the versioning explanation applies — true only when the
      survey has never been published (design D3). Compute it server-side; the template should not
      re-derive it.

## 3. Editor confirmation

- [x] 3.1 Replace the static `hx-confirm` on the question delete button with a handler that posts,
      and on 409 opens a dialog stating the count and, when applicable, what versioning does.

  Done differently from the task, and better: `hx-confirm` was left alone. The editor already routes
  every `hx-confirm` through `Dialog.confirm` (`editor_dialog.js`), a shared Bootstrap modal, so the
  409 handler calls the same `Dialog.confirm` rather than the bespoke modal this first shipped with.
  I built that bespoke modal before checking whether the editor already had one — it did, and the
  first version put a second modal system alongside it. Verified in the browser that only one modal
  is ever open at a time.
- [x] 3.2 The same for the section delete control.
- [x] 3.3 Confirming re-posts with the acknowledgement; cancelling does nothing.
- [x] 3.4 Keep the single-click path for objects with no answers — no dialog where there is nothing
      to lose (design D4).
- [x] 3.5 Word the versioning sentence so it states what versioning does rather than advising the
      author to publish. Publishing a half-built survey to protect two test answers is worse than
      losing them.

## 4. Tests

- [x] 4.1 Delete without acknowledgement on a question with answers → 409, count correct, question
      and answers still present.
- [x] 4.2 Delete with acknowledgement → question and its answers gone.
- [x] 4.3 Question with no answers deletes without a 409.
- [x] 4.4 Count includes sub-question answers.
- [x] 4.5 Section count spans questions and sub-questions.
- [x] 4.6 Refused section delete leaves the section and its neighbour links untouched — this is the
      regression 2.2 is written to avoid.
- [x] 4.7 The versioning flag is set for a never-published survey and unset for a draft copy of a
      published one.
- [x] 4.8 The read-only lock still wins: a published survey returns 403 rather than 409, and no
      acknowledgement can override it.

## 5. Verify

- [x] 5.1 Run the full survey suite.
- [x] 5.2 Exercise both dialogs by hand in the editor — the count is only trustworthy if it is right
      on a real survey, and the section case is the one that can silently undercount.

  Done on a seeded survey. A geo question whose own answers are zero but whose sub-question holds 3
  reported 3, showed the versioning explanation, and on confirmation took the sub-question with it.
  A question with no answers deleted after the ordinary confirmation with no second prompt. Verified
  against the database rather than the DOM — the first DOM assertions raced the HTMX swap and read
  as failures when the rows were already gone.

## 6. Close the loop

- [x] 6.1 Strike backlog #98 and record the measured exposure on it.

  The task as written said #98's description overstated the case. Re-reading the item, that was
  wrong — it already states that published surveys are protected by versioning and draft/testing are
  not. The overstatement was in how I had summarised it, not in the file. Struck, and the measured
  numbers plus the fix are recorded on it.
- [x] 6.2 Filed as **#108**. Record the open question from the design as a backlog item:
      changing a question's `input_type` or removing referenced choice codes invalidates stored
      answers on the unpublished path with no warning, while `check_draft_compatibility` already
      detects exactly that for the published one.
