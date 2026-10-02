# abuse-review Specification

## Purpose
TBD - created by archiving change phishing-content-review. Update Purpose after archive.
## Requirements
### Requirement: ContentReview record

The system SHALL provide a `ContentReview` model anchored to the canonical `SurveyHeader` with: `status` in (`pending`, `reported`, `cleared`, `confirmed`), `source` in (`screen`, `report`), `trigger` (`publish`, `draft_publish`, `live_edit`, or empty for reports), integer `score`, JSON `signals`, `fingerprint` (SHA-256 of the normalised screened text), `report_count`, `created_at`, `decided_at`, `decided_by` (user FK, SET_NULL), `note`. `(survey, status)` SHALL be indexed. At most one row per survey SHALL be in `pending` or `reported` at a time.

#### Scenario: Pending review is unique per survey

- **WHEN** a hold is requested for a survey that already has a `pending` review
- **THEN** the existing row SHALL be updated and no new row created

#### Scenario: Review is anchored to the canonical survey

- **WHEN** screening runs after a draft publish
- **THEN** the review's `survey` SHALL be the canonical survey, never the draft copy or an archived version

### Requirement: A held survey is unavailable to respondents and flagged to its creator

While a survey has a `pending` review, respondent access SHALL render the same "isn't available" page an unknown survey UUID gets (HTTP 404, `noindex`, no reason given) instead of the survey, for every entry point governed by `check_survey_access`. Owners and editors SHALL still bypass access control as today. The editor survey page SHALL show the creator a banner stating that the survey is under review, usually completed within a day, and that respondents will see it once review completes; the banner SHALL list no signals or reasons.

#### Scenario: Respondent hits a held survey

- **WHEN** an anonymous visitor opens the entry URL or any section URL of a published survey with a `pending` review
- **THEN** the response SHALL be the unavailable page with status 404, indistinguishable from an unknown survey
- **AND** no `SurveySession` SHALL be created

#### Scenario: Creator still reaches their own survey

- **WHEN** the survey owner opens the respondent URL of their held survey
- **THEN** the survey SHALL render as usual (owner bypass)

#### Scenario: Creator sees the review banner without reasons

- **WHEN** the owner opens the editor page of a survey with a `pending` review
- **THEN** a banner SHALL say the survey is under review and respondents cannot see it yet
- **AND** the banner SHALL contain none of the triggered signals, scores or keywords

#### Scenario: A reported survey keeps serving

- **WHEN** a survey has a `reported` review and no `pending` review
- **THEN** respondents SHALL see the survey as usual

### Requirement: Owner notification email

On every new `pending` or `reported` review the system SHALL send one email to `ABUSE_REVIEW_EMAIL` (env, default `CONTACT_EMAIL`) through `send_templated_mail`, enqueued as a Celery task; if enqueueing raises, the mail SHALL be sent synchronously instead. The message SHALL contain the survey name and link, score and triggered signals with text excerpts (or the report reason), the creator's username, email domain, registration time, number of surveys and sessions, prior reviews for the account, and a review link; the plain-text part SHALL place the review link within its first lines.

#### Scenario: Notice is sent on hold

- **WHEN** a `pending` review is created
- **THEN** exactly one email SHALL be sent to `ABUSE_REVIEW_EMAIL` with subject containing the survey name and the score
- **AND** the body SHALL contain the review link and the triggered signals

#### Scenario: Broker failure falls back to synchronous send

- **WHEN** enqueueing the notification task raises
- **THEN** the notice SHALL still be sent in the request
- **AND** the review row SHALL remain `pending`

#### Scenario: Notice never goes to the creator

- **WHEN** a review is created for a survey
- **THEN** no email about the review SHALL be sent to the survey's creator

### Requirement: Staff review page with Release and Confirm phishing

The system SHALL serve `/editor/abuse-review/<token>/` where `token` is a salted `signing.dumps` of the review id valid for 14 days. GET SHALL require an authenticated staff user (404 otherwise, 404 on bad or expired token) and SHALL render the evidence read-only. Decisions SHALL be accepted only as CSRF-protected POSTs to the same URL with `action=release` or `action=confirm`. A review already decided SHALL render its decision and accept no action.

#### Scenario: Link in mail is safe to prefetch

- **WHEN** an unauthenticated client or a non-staff user requests the review URL with GET
- **THEN** the response SHALL be 404 and nothing SHALL change

#### Scenario: Release restores the survey

- **WHEN** a staff user POSTs `action=release` on a `pending` review
- **THEN** the review SHALL become `cleared` with `decided_by` and `decided_at` set
- **AND** respondents SHALL see the survey on the next request
- **AND** an `AbuseEvent` with `defense='content_screen'` and `detail` starting with `release survey=<id>` SHALL be written

#### Scenario: Confirm phishing deactivates the account and closes its surveys

- **WHEN** a staff user POSTs `action=confirm` on a review
- **THEN** the creator's `is_active` SHALL be False
- **AND** every survey created by that user in status `draft`, `testing` or `published` SHALL become `closed`, with an audit row per survey
- **AND** every login session of that user SHALL be deleted
- **AND** the review SHALL become `confirmed`
- **AND** an `AbuseEvent` with `detail` starting with `confirm survey=<id> user=<id>` SHALL be written

#### Scenario: Expired token

- **WHEN** a staff user opens a review link older than 14 days
- **THEN** the response SHALL be 404
- **AND** the review SHALL remain reachable from the admin

#### Scenario: Decided review is read-only

- **WHEN** a staff user POSTs any action on a `cleared` or `confirmed` review
- **THEN** nothing SHALL change and the page SHALL show the existing decision

### Requirement: Reviews are listed in the Django admin

`ContentReview` and `AbuseEvent` SHALL be registered in the admin; `ContentReview` SHALL list status, survey, score, source, created and decided timestamps, SHALL filter by status, and SHALL link to the staff review page.

#### Scenario: Pending reviews are findable without the email

- **WHEN** a staff user opens the `ContentReview` admin list filtered by `pending`
- **THEN** every held survey SHALL appear with a link to its review page

