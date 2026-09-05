# object-answers Specification

## Purpose
TBD - created by archiving change overlay-features. Update Purpose after archive.
## Requirements
### Requirement: An answer may reference a layer object
`Answer` SHALL carry a nullable `layer_object` reference. Answers to sub-questions of a
`layer_objects` question SHALL set it and SHALL NOT set `parent_answer_id`. At most one
answer SHALL exist per (session, question, object), enforced by a partial unique constraint
on rows where `layer_object` is set. Deleting an object SHALL delete its answers.

#### Scenario: One row per object and sub-question
- **WHEN** a respondent rates object `m-034` twice in one session
- **THEN** one answer row exists for (session, rating sub-question, `m-034`) holding the latest value

#### Scenario: Legacy rows unaffected
- **WHEN** the constraint is added to a database with existing answers
- **THEN** the migration succeeds because existing rows have no `layer_object`

### Requirement: Posting, purging and visibility
The section POST SHALL accept object answers as `obj__<key>__<code>` fields, ignore keys
not in the bound layer, and discard object answers whose `layer_objects` question is hidden
by a visibility rule. Restoring a session SHALL re-populate the popup forms and the
answered state from stored object answers.

#### Scenario: Unknown key ignored
- **WHEN** a POST carries `obj__zzz__q1` for a key not in the layer
- **THEN** no answer is stored and the request otherwise succeeds

#### Scenario: Hidden block discards
- **WHEN** the `layer_objects` question is hidden by a rule for this session and the POST still carries object fields
- **THEN** those fields are discarded and no rows are written

#### Scenario: Session restore
- **WHEN** a respondent returns to the section after answering about two objects
- **THEN** both objects show as answered and their popups show the stored values

### Requirement: Object answers export keyed by object
The response ZIP SHALL contain, per `layer_objects` question, `objects_<code>.csv` with one
row per (session, object) and one column per sub-question, and per bound layer a
`layers/<name>.results.geojson` whose features carry per-object aggregates: `answers`
(distinct sessions), and per sub-question `mean` and `count` for rating, `up`/`down` for
thumbs, per-choice counts for choice, `count` for text. Free-text values SHALL appear only
in the CSV, never in the GeoJSON.

#### Scenario: CSV shape
- **WHEN** 31 sessions answered about `m-034` on a question with rating, thumbs and text sub-questions
- **THEN** `objects_<code>.csv` has 31 rows for `m-034` with columns `session_id, object_key, object_title, <rating>, <thumbs>, <text>`

#### Scenario: Results GeoJSON aggregates
- **WHEN** the same layer is exported
- **THEN** the `m-034` feature carries `answers = 31`, the rating `mean` and `count`, and thumbs `up`/`down`, and no text value

### Requirement: Responses tab shows per-object aggregates
The Responses map SHALL badge each object of a bound layer with its answer count and
headline aggregate, and selecting an object SHALL filter the table to that object's rows
through the existing selection mechanism.

#### Scenario: Badge and selection
- **WHEN** the creator clicks object `m-034` on the Responses map
- **THEN** the badge reads "31 · 4.2★ · 👍 24/7" and the table shows the 31 matching rows

### Requirement: Public results respect k-anonymity per object
A public-results block of type `object_ratings` SHALL show per-object aggregates using the
page's k threshold: objects with fewer than k answers are masked; free-text answers are
never rendered.

#### Scenario: Masked object
- **WHEN** `k = 3` and object `m-051` has 2 answers
- **THEN** the block shows `m-051` as masked and shows aggregates for objects with ≥ 3

