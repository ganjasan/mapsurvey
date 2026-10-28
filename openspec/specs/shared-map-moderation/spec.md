# shared-map-moderation Specification

## Purpose
TBD - created by archiving change respondent-shared-map. Update Purpose after archive.
## Requirements
### Requirement: Objects have a moderation status
`LayerObject.status` SHALL be one of `visible`, `pending`, `hidden` (default `visible`).
A newly materialised object SHALL be `pending` when its layer has `approve_first`, else
`visible`. Turning `approve_first` on SHALL NOT change existing objects. Only `visible`
objects SHALL be served to respondents; all statuses SHALL remain in the creator's
Responses map, aggregates and export.

#### Scenario: Approve-first layer
- **WHEN** `approve_first` is on and a respondent submits a mark
- **THEN** the object is created `pending`, absent from other respondents' maps, present in Responses → Shared map under "Pending"

#### Scenario: Default layer
- **WHEN** `approve_first` is off and a respondent submits a mark
- **THEN** the object is `visible` immediately

### Requirement: Comments can be hidden one by one
`Answer` SHALL carry `hidden` (default false). A hidden text sub-answer SHALL be excluded
from the object card's comments and from `comment_count`, and SHALL remain in Responses and
export.

#### Scenario: Hide a comment
- **WHEN** the creator hides one of three comments on a mark
- **THEN** respondents see two comments and `comment_count=2`; the export still lists three

### Requirement: Responses tab has a Shared map block
For each question bound to a `question` layer the Responses tab SHALL show a *Shared map*
block in that question's per-object results: the per-object table with a Status column, filter chips All / Pending / Hidden with counts, actions
Approve (pending → visible), Hide (any → hidden), Show (hidden → visible), and a row
expander listing the mark's comments each with Hide / Show. Actions SHALL apply without a
page reload and SHALL touch the layer so respondents' next load reflects them. The block
SHALL warn when `approve_first` is on, pending marks exist and the bound question has
`min_objects > 0`. The block SHALL be read-only for collaborators without edit rights and
absent under the kill switch.

#### Scenario: Approve from the block
- **WHEN** the creator clicks Approve on a pending mark
- **THEN** its status becomes `visible`, the Pending count drops by one, and a respondent loading the section afterwards receives the mark

#### Scenario: Hide a mark
- **WHEN** the creator clicks Hide on a visible mark that has 4 reactions
- **THEN** the mark and its reactions stay in the table and export, and the mark is absent from respondents' layer collections

#### Scenario: Minimum cannot be met
- **WHEN** `approve_first` is on, 3 marks are pending, none visible, and the bound question has `min_objects=1`
- **THEN** the block shows a warning that respondents cannot currently meet the minimum

