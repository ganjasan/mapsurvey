## Context

`_export_survey_data` (`survey/views.py:1053`) builds the respondent-data ZIP: one GeoJSON layer per
geo question, plus one CSV for everything else. Both branches translate an `Answer` row into a cell
value, and both do it with the same hand-written `elif` chain over `input_type`, duplicated:

| | GeoJSON sub-question loop (`:1099-1123`) | CSV loop (`:1166-1188`) |
|---|---|---|
| `text`, `text_line` | `answer.text` | `answer.text` |
| `number`, `range` | `numeric`, else `selected_choices[0]`, else `""` | identical |
| `choice`, `rating` | first choice name | identical |
| `multichoice` | choice names joined by `"; "` | identical |
| anything else | *falls through, no assignment* | `else: continue` |

The two chains are byte-for-byte equivalent except in how they end, and that ending is where both
bugs live. The GeoJSON branch compounds it by initialising the accumulator once before the loop
(`:1098`) rather than per iteration, so a fall-through does not merely produce nothing — it
produces the previous sub-question's value.

The fall-through is reached more often than it looks. Sub-answers are written only for keys present
in the submitted feature's `properties` (`views.py:841`), so a sub-question the respondent left
blank has **no `Answer` row at all**; `subAnswers()` then yields an empty list for it, no branch
assigns, and the stale value is written out under that sub-question's name. A `datetime`, `image`
or `html` sub-question falls through the same way regardless of whether it was answered.

Constraints worth stating: the export view is unauthenticated for public surveys and must not raise
on unexpected data — denying someone their data is a worse failure than an imperfect cell. The
output is consumed by QGIS and Excel, so column presence and stability matter as much as values.
There is no migration surface here; this is a read path only.

## Goals / Non-Goals

**Goals:**

- A sub-question's exported property depends only on that sub-question's own answer.
- `datetime` answers reach the CSV.
- An input type that no branch handles cannot silently disappear from the download.
- Value-level test coverage: assert which value lands in which column and property, including the
  partially-filled sub-question case that produced the bug.
- Confirm or refute that the accumulator fix also resolves backlog #23 (number sub-question exports
  blank), rather than assuming it.

**Non-Goals:**

- The CASCADE deletion of answers when a question is removed (backlog #98). Different code path,
  different decision, tracked separately.
- The asymmetry where the sub-answer *save* path branches on `sub_question.choices` rather than
  `input_type` (`views.py:845-856`), which means a `choice` sub-question with no choices defined
  silently stores nothing. Real, but a write-path bug; fixing it here would mix a data-collection
  change into a data-export change.
- Adding media, ranking or scale types to the export (backlog #102) — the allowlist introduced here
  is what makes adding them safe later.
- Shapefile / GeoPackage output (backlog #8).

## Decisions

### D1 — Extract one shared cell formatter instead of fixing each chain in place

Replace both duplicated chains with a single helper, `_answer_cell(question, answers)`, returning
the formatted value for one question from that question's answer rows. Both call sites use it.

*Why over the minimal fix:* moving `result = ""` inside the loop is two characters and repairs the
symptom, but leaves two copies of the same chain that already drifted apart once — the drift *is*
the bug. With one formatter there is no accumulator to leak across iterations, because each call
returns its own value; the bug becomes structurally unavailable rather than merely absent.

*Cost:* a larger diff than the symptom fix, touching the CSV path which nobody reported as broken.
Mitigated by the fact that the chains are provably equivalent today (table above), so the CSV
branch's observable behaviour is unchanged except for the two intended fixes. The tests added under
D5 pin the existing CSV behaviour before the refactor lands.

### D2 — Classify input types explicitly; no bare `else`

The helper dispatches on three named sets rather than falling off the end of a chain:

- **value types** — `text`, `text_line`, `number`, `range`, `choice`, `rating`, `multichoice`,
  `datetime`: formatted as today, with `datetime` added.
- **geometry types** — `point`, `line`, `polygon`: not CSV cells; they are the GeoJSON layers
  themselves. The helper reports "not applicable" and the CSV caller omits the column, preserving
  current behaviour.
- **display-only types** — `image`, `html`: presentational, carry no respondent input. Omitted for
  the same reason, but for a different reason, and the code should say which.

Anything not in any set — i.e. a type added to `INPUT_TYPE_CHOICES` later — logs a warning naming
the type and exports an empty cell under the question's name.

*Why empty-and-warn over raising:* an exception here fails the whole download for every respondent
because one question has an unrecognised type. *Why over silently skipping:* silent skipping is
precisely what hid the `datetime` defect; a column of blanks is visible to the creator and the
warning is visible to us.

### D3 — Serialise `datetime` as ISO 8601, from `answer.text`

`datetime` answers are stored by the save path alongside text (`views.py:702`), so the value in
`answer.text` is whatever the `datetime-local` input posted. Normalise to ISO 8601 on export rather
than passing the raw string through, so the column is machine-readable and stable regardless of
what a future widget change posts. Values that fail to parse pass through unchanged rather than
being dropped — a raw string the creator can interpret beats a blank.

*Alternative rejected:* locale-formatted output for Excel friendliness. Excel's interpretation
depends on the reader's locale, which makes the file non-portable; ISO 8601 is unambiguous and
QGIS-safe.

### D4 — Stop rebinding `answer` inside the sub-question loop

The current code assigns the sub-answer to `answer` (`:1103`, `:1107`, `:1116`), shadowing the geo
answer being exported, which is why `properties["session"]` at `:1125` reads from a sub-answer row.
It happens to be the same session today. D1 removes the rebinding as a side effect since the
formatter owns its own locals; this is called out so the reviewer knows it was deliberate and the
session properties are asserted in tests.

### D5 — Pin behaviour with value-level tests, characterisation first

Existing export tests assert row counts and metadata columns only, never that an answer value
reached the correct column. Order the work so the tests come first:

1. Characterisation tests for current *correct* behaviour across every value type, CSV and GeoJSON,
   written against the unrefactored code and passing before any change.
2. Failing tests for the three defects: partially-filled sub-questions, a `datetime` question, and
   a number sub-question mirroring backlog #23's setup.
3. The refactor, turning (2) green while (1) stays green.

The #23 test is the arbiter of whether that backlog item closes here: if it passes after the fix,
#23 was the same bug; if it still fails, #23 is separate and stays open with a sharper reproduction
than it has now.

## Risks / Trade-offs

**Re-exporting a survey now returns different attribute values than the file the customer already
downloaded** → This is the fix working, but a creator who has published analysis from the old export
will find the numbers moved and no explanation. Anyone with an affected export in hand (Manuel
Frost, bisq) should be told directly rather than discovering it. Not a deploy blocker; it is a
communication task attached to the release.

**The refactor touches the CSV path, which nobody reported as broken** → Characterisation tests
(D5.1) land and pass before the refactor, so any behaviour change shows up as a red test rather
than in a customer's spreadsheet.

**A warning for an unhandled type is only useful if anyone reads it** → Root logger is at WARNING in
production and reaches Render logs (added with the web-concurrency work), so this surfaces. It is
still weaker than a test; the allowlist in D2 is the real guard, since adding a type to
`INPUT_TYPE_CHOICES` without classifying it is a visible omission in review.

**`datetime` normalisation could mangle values stored by an older widget** → Parse failures pass the
raw string through unchanged, so the worst case is the current behaviour plus a column that did not
exist before.

## Migration Plan

No schema change, no migration, no data backfill. The change is a read path; deploying it changes
what subsequent downloads contain and nothing already stored.

Rollback is a revert — previously downloaded files are unaffected either way, and no state depends
on which version produced them.

## Open Questions

- Should affected creators be notified that a re-export will yield corrected values, and does that
  go out with the release or with the reply already owed to Manuel Frost? Product call, not a
  technical one.
- Does #23's reporter (bisq) have a survey still in the database to verify the fix against real
  rows, or is the mirrored test setup the only available evidence?
