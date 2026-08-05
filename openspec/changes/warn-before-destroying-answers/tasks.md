## 1. Counting helper

- [ ] 1.1 Add a helper returning the number of answers beneath a question — its own plus its
      sub-questions' — and one for a section covering all its questions and their sub-questions
      (design D2).
- [ ] 1.2 Unit-test the traversal directly, before any view uses it: question alone, question with
      sub-questions, section spanning both, and the zero cases.

## 2. Server-side guard

- [ ] 2.1 `editor_question_delete`: when answers exist and the request carries no acknowledgement,
      return 409 with the count and delete nothing.
- [ ] 2.2 `editor_section_delete`: the same, counting across the whole section. Take care that the
      neighbour re-linking that runs before the delete does not happen on the refused path — the
      current code re-links first and deletes after.
- [ ] 2.3 Proceed normally when the acknowledgement is present, and when there are no answers to
      lose.
- [ ] 2.4 Include in the response whether the versioning explanation applies — true only when the
      survey has never been published (design D3). Compute it server-side; the template should not
      re-derive it.

## 3. Editor confirmation

- [ ] 3.1 Replace the static `hx-confirm` on the question delete button with a handler that posts,
      and on 409 opens a dialog stating the count and, when applicable, what versioning does.
- [ ] 3.2 The same for the section delete control.
- [ ] 3.3 Confirming re-posts with the acknowledgement; cancelling does nothing.
- [ ] 3.4 Keep the single-click path for objects with no answers — no dialog where there is nothing
      to lose (design D4).
- [ ] 3.5 Word the versioning sentence so it states what versioning does rather than advising the
      author to publish. Publishing a half-built survey to protect two test answers is worse than
      losing them.

## 4. Tests

- [ ] 4.1 Delete without acknowledgement on a question with answers → 409, count correct, question
      and answers still present.
- [ ] 4.2 Delete with acknowledgement → question and its answers gone.
- [ ] 4.3 Question with no answers deletes without a 409.
- [ ] 4.4 Count includes sub-question answers.
- [ ] 4.5 Section count spans questions and sub-questions.
- [ ] 4.6 Refused section delete leaves the section and its neighbour links untouched — this is the
      regression 2.2 is written to avoid.
- [ ] 4.7 The versioning flag is set for a never-published survey and unset for a draft copy of a
      published one.
- [ ] 4.8 The read-only lock still wins: a published survey returns 403 rather than 409, and no
      acknowledgement can override it.

## 5. Verify

- [ ] 5.1 Run the full survey suite.
- [ ] 5.2 Exercise both dialogs by hand in the editor — the count is only trustworthy if it is right
      on a real survey, and the section case is the one that can silently undercount.

## 6. Close the loop

- [ ] 6.1 Strike backlog #98 and correct its description: it says editing a survey destroys the
      answers already given, which overstates the case by omitting that versioning protects
      published surveys. The accurate statement is that surveys which have never been published are
      unprotected — 50 in `draft` holding 842 answers and 12 in `testing` holding 1471, measured
      2026-08-05.
- [ ] 6.2 Record the open question from the design as a backlog item if it is not taken up here:
      changing a question's `input_type` or removing referenced choice codes invalidates stored
      answers on the unpublished path with no warning, while `check_draft_compatibility` already
      detects exactly that for the published one.
