## MODIFIED Requirements

### Requirement: ContentReview record

The system SHALL provide a `ContentReview` model anchored to EXACTLY ONE subject: the canonical `SurveyHeader` (`survey`) or a `Landing` (`landing`), enforced by a database check constraint, with: `status` in (`pending`, `reported`, `cleared`, `confirmed`), `source` in (`screen`, `report`), `trigger` (`publish`, `draft_publish`, `live_edit`, or empty for reports), integer `score`, JSON `signals`, `fingerprint` (SHA-256 of the normalised screened text), `report_count`, `created_at`, `decided_at`, `decided_by` (user FK, SET_NULL), `note`. `(survey, status)` SHALL be indexed. At most one row per subject SHALL be in `pending` or `reported` at a time. The owner notification and the staff review page SHALL name the subject's kind, name, public URL and editor URL; confirming phishing on a landing review SHALL deactivate the landing's creator, close the surveys they created and unpublish the landings they created.

#### Scenario: Pending review is unique per survey

- **WHEN** a hold is requested for a survey that already has a `pending` review
- **THEN** the existing row SHALL be updated and no new row created

#### Scenario: Review is anchored to the canonical survey

- **WHEN** screening runs after a draft publish
- **THEN** the review's `survey` SHALL be the canonical survey, never the draft copy or an archived version

#### Scenario: A review names one subject

- **WHEN** a review row is saved with both `survey` and `landing` set, or with neither
- **THEN** the database SHALL refuse it

#### Scenario: Confirming a landing review

- **WHEN** staff confirm phishing on a pending landing review
- **THEN** the landing's creator is deactivated, every survey they created is closed and every landing they created is unpublished
