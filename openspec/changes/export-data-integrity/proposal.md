## Why

The respondent-data download produces wrong values, and does so silently. In the GeoJSON branch of
`_export_survey_data` the `result` accumulator is initialised once before the loop over
sub-questions instead of once per sub-question (`survey/views.py:1098`), so a sub-question with no
answer — or with an input type the chain does not handle — is exported carrying the value of
whichever sub-question was processed before it. The file is well-formed and the values are
plausible, so nobody downstream can tell which attributes are real. Sub-questions of a geo question
are the documented way to model attributes of a mapped object, which puts this on the main path for
the platform's core use case.

Two smaller defects sit in the same function: `datetime` answers are stored (the save path folds
them in with text, `views.py:702`) but dropped by the CSV chain's `else: continue`
(`views.py:1185`), and the same `else` will silently swallow any input type added later.

All three survived because the existing tests assert row counts and metadata columns
(`validation_status`, `session_id`) and never assert that an answer value reaches the correct
column, nor exercise sub-question properties at all. Fixing the three without closing that gap
leaves the next value-level regression just as invisible.

Now, because a customer has already hit the visible symptom and the correctness of exports is the
product's output of record — a survey platform whose download cannot be trusted has no deliverable.

## What Changes

- Scope the property accumulator to a single sub-question so a blank or unhandled sub-question
  exports as empty rather than inheriting its predecessor's value.
- Export `datetime` answers to CSV, reading `answer.text`, serialised as ISO 8601.
- Replace the silent `else: continue` for unhandled input types with an explicit, documented
  behaviour, so a type added later cannot vanish from the download without anyone noticing.
- Stop rebinding `answer` to a sub-answer inside the sub-question loop (`views.py:1103` and
  siblings). Currently benign, but it makes `properties["session"]` read from the wrong row and is
  a trap for the next edit.
- Add value-level test coverage for the download: which value lands in which column, and what a
  partially-filled set of sub-questions produces in the GeoJSON.

Not in scope: the CASCADE deletion of answers when a question is removed (backlog #98) and the
blank-number report (#23) as a separate investigation. #23 is expected to be resolved by the
accumulator fix — the reporter's number lived in a sub-question of a geo question — and the change
should confirm or refute that with a test rather than assume it.

**Output changes, not breaking API:** CSVs gain a column for every `datetime` question, which is
additive. GeoJSON property *values* change for partially-filled sub-questions — that is the fix,
but anyone who has already analysed a previous export will get different numbers from a re-export,
which needs saying out loud rather than shipping quietly.

## Capabilities

### New Capabilities
- `response-data-export`: the content of the respondent-data download (`/surveys/<slug>/download`) —
  which answers appear in the CSV and in the per-question GeoJSON layers, under which column or
  property name, and in what serialised form. Covers value correctness only; the version-filter UI
  around it is already specified by `version-export-ui`, and the CLI survey export by
  `survey-serialization`.

### Modified Capabilities

None. `version-export-ui` specifies the download dropdown and version filter, neither of which
changes here. `survey-serialization` specifies the `export_survey` management command, which is a
different code path.

## Impact

- `survey/views.py` — `_export_survey_data` (both the GeoJSON and the CSV branch); `download_data`
  unchanged.
- `survey/tests.py` — new value-level cases; existing export tests keep passing unmodified.
- No model change, no migration, no template change.
- Backlog items closed: 96, 97; 23 confirmed or refuted.
- Anyone re-exporting a survey with sub-questions will see corrected attribute values. Manuel Frost
  (Berlin Senate) and bisq both have affected exports in hand.
