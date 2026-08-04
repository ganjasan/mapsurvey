## 1. Characterisation tests (must pass before any production code changes)

- [x] 1.1 Add an export test case with a survey covering every value-bearing type — `text`,
      `text_line`, `number`, `range`, `choice`, `rating`, `multichoice` — one answered session, and
      assert the exact CSV cell for each. This pins today's correct behaviour before the refactor.
- [x] 1.2 Add the GeoJSON counterpart: a geo question whose sub-questions cover the same types, all
      answered, asserting each property value. Pins the sub-question path.
- [x] 1.3 Assert that geometry questions produce a `.geojson` entry and no CSV column, and that an
      `html` question produces neither.
- [x] 1.4 Run the suite and confirm 1.1–1.3 pass against unmodified code. If any fails, stop — the
      chain is not equivalent to what the design assumes, and the design needs revising first.

  Done in `ExportValueCorrectnessTest` (`survey/tests.py`), 6 tests, all green against unmodified
  code — the two chains behave as the design's equivalence table claims, so the refactor may
  proceed. Recorded while writing them: `numeric` is a `FloatField`, so integers reach the CSV as
  `"7.0"`, not `"7"`. Any later change to that formatting is a visible behaviour change and now has
  a test holding it.

## 2. Failing tests for the three defects

- [ ] 2.1 Test: geo answer with a first sub-question answered and a second with no `Answer` row →
      second property is empty. Expected to fail with the neighbour's value.
- [ ] 2.2 Test: three consecutive sub-questions with no `Answer` rows → all empty. Expected to fail.
- [ ] 2.3 Test: `datetime` question answered → CSV has a column with the ISO 8601 value. Expected to
      fail with the column absent.
- [ ] 2.4 Test mirroring backlog #23: a `number` sub-question of a geo question, answered, exported.
      Record whether it passes or fails on unmodified code — this decides whether #23 closes here.
- [ ] 2.5 Test: two sessions each with a geo answer → each feature's `session_id`,
      `validation_status` and `language` match its own session.

## 3. Shared cell formatter

- [ ] 3.1 Add `_answer_cell(question, answers)` to `survey/views.py` returning the formatted value
      for one question from its own answer rows, plus a sentinel distinguishing "no column for this
      question" from "empty value".
- [ ] 3.2 Classify types into the three named sets from design D2 — value, geometry, display-only —
      as module-level constants, so an unclassified type is a visible omission in review.
- [ ] 3.3 Handle `datetime`: parse `answer.text`, emit ISO 8601, pass the raw string through
      unchanged on parse failure.
- [ ] 3.4 Log a warning naming the type for anything unclassified, and return an empty value rather
      than raising or skipping.

## 4. Replace both call sites

- [ ] 4.1 Rewrite the GeoJSON sub-question loop to call the formatter per sub-question. The
      accumulator disappears; confirm no variable survives across iterations.
- [ ] 4.2 Rewrite the CSV loop to call the formatter, honouring the no-column sentinel so geometry
      and display-only questions stay out of the CSV.
- [ ] 4.3 Remove the rebinding of `answer` inside the sub-question loop (design D4) and confirm
      `properties["session"]`, `session_id`, `language` and `validation_status` read from the geo
      answer's session.
- [ ] 4.4 Confirm the duplicated `elif` chains are gone — one formatter, two call sites.

## 5. Verify

- [ ] 5.1 Run the full survey suite: `./run_tests.sh survey`. Tests from §1 still green, tests from
      §2 now green, no existing export test modified to make it pass.
- [ ] 5.2 Record the outcome of 2.4: if green after the fix, close backlog #23 as the same root
      cause; if still failing, leave #23 open and attach the reproduction as a note.
- [ ] 5.3 Export a survey with sub-questions by hand and open the GeoJSON in QGIS — the attribute
      table is what the customer actually reads, and no unit test checks that it loads.

## 6. Close the loop

- [ ] 6.1 Update backlog items 96 and 97 to point at this change; update #23 per 5.2.
- [ ] 6.2 Correct the wording in backlog 96, 97 and 23 that says `download_data` has no test
      coverage — it has count-level and metadata-level tests; the gap was value-level. The claim is
      wrong as written and will mislead whoever reads it next.
- [ ] 6.3 Note in the change that affected creators (Manuel Frost, bisq) hold exports whose
      attribute values a re-export will change, and that this needs saying to them — decision and
      wording belong to the reply already owed, not to this change.
