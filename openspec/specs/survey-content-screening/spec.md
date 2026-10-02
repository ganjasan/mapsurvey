# survey-content-screening Specification

## Purpose
TBD - created by archiving change phishing-content-review. Update Purpose after archive.
## Requirements
### Requirement: Creator-authored survey text is scored for phishing signals when it goes live

The system SHALL compute a phishing score for a survey from its creator-authored text — survey name, section titles and subheadings, question names and subtexts (all translations), the thanks page in every language, and `redirect_url` — together with account facts (account age at the moment of publishing, email domain, total question count). Scoring SHALL be deterministic, SHALL run without network access, and SHALL weigh at least these signals: URL-shortener hosts, email click-tracker hosts, external links to hosts outside an allow-list that includes the site's own host and media host, impersonated brand terms, lure phrases, empty-paragraph padding, a survey with at most one question, an account younger than one hour (and, weaker, younger than one day), and a disposable email domain.

#### Scenario: The XFINITY lure scores above the hold threshold

- **WHEN** a survey published two minutes after registration from a disposable-mail domain has one section whose subheading names "XFINITY", says "You're almost set", carries a "CLICK HERE TO PROCEED" link to a URL-shortener host and is followed by 74 empty paragraphs, and the survey has one `text` question
- **THEN** the score SHALL be at or above `CONTENT_SCREENING_HOLD_THRESHOLD`
- **AND** the recorded signals SHALL name the shortener host, the brand term, the padding and the external link

#### Scenario: The redirect-only lure scores above the hold threshold

- **WHEN** a survey published two minutes after registration has a single question named "PDF Document" and a `redirect_url` on an email click-tracker host
- **THEN** the score SHALL be at or above `CONTENT_SCREENING_HOLD_THRESHOLD`
- **AND** the recorded signals SHALL include the tracker host from `redirect_url`

#### Scenario: Legitimate surveys from the 2026-10-02 scan stay below the threshold

- **WHEN** a survey links only to the site's own media host, or to Facebook, a project website or an image on a retailer's CDN, has several questions, and was published by an account minutes old
- **THEN** the score SHALL be below `CONTENT_SCREENING_HOLD_THRESHOLD`

#### Scenario: Account age and question count cannot hold a survey by themselves

- **WHEN** a survey with one question and no links or lure terms is published by an account registered one minute earlier from a normal email domain
- **THEN** the score SHALL be below `CONTENT_SCREENING_HOLD_THRESHOLD`

### Requirement: Screening runs at every moment survey text goes live

The system SHALL screen a survey when its status transitions to `published`, when a draft copy is published onto the canonical survey (screening the canonical survey), and when `redirect_url` or `thanks_html` is saved on a survey whose status is `published`. Drafts and `testing` surveys SHALL NOT be screened.

#### Scenario: Publish transition screens the survey

- **WHEN** the owner moves a survey from `draft` or `testing` to `published`
- **THEN** the survey SHALL be screened once after the status is saved
- **AND** the review row, if any, SHALL record the trigger `publish`

#### Scenario: Draft publish screens the canonical survey

- **WHEN** the owner publishes a draft copy of a published survey
- **THEN** the canonical survey SHALL be screened after the draft's content has been copied onto it
- **AND** the review row, if any, SHALL record the trigger `draft_publish`

#### Scenario: Changing the redirect on a live survey re-screens it

- **WHEN** `redirect_url` or `thanks_html` is saved through the survey settings or thanks panel on a survey with status `published`
- **THEN** the survey SHALL be screened again with the trigger `live_edit`

#### Scenario: Drafts and testing surveys are not screened

- **WHEN** a draft or `testing` survey's text is saved, or a survey transitions to `testing`
- **THEN** no screening SHALL run and no review row SHALL be created

### Requirement: Screening fails open

A failure inside screening — an exception in text collection, scoring, review creation or notification — SHALL be logged and SHALL NOT prevent the publish, draft publish or settings save from completing; the survey SHALL serve as if screening had not run.

#### Scenario: Scorer exception does not block publishing

- **WHEN** the scorer raises during a publish transition
- **THEN** the publish SHALL complete with the same response as without screening
- **AND** the exception SHALL be logged
- **AND** no review row SHALL exist for the survey

### Requirement: A survey at or above the hold threshold is held for review

When the score reaches `CONTENT_SCREENING_HOLD_THRESHOLD` (integer env setting, default 7), the system SHALL create one `ContentReview` with `status='pending'`, the score, the signals and a content fingerprint, write an `AbuseEvent` with `defense='content_screen'`, and notify the review address. When the score is below the threshold, nothing SHALL be recorded.

#### Scenario: Hold creates exactly one pending review

- **WHEN** a survey scores at or above the threshold on publish and has no open review
- **THEN** one `ContentReview` row with `status='pending'` SHALL be created for the canonical survey
- **AND** one `AbuseEvent` with `defense='content_screen'` and `detail` starting with `hold survey=<id>` SHALL be written
- **AND** the review notice SHALL be sent to the review address

#### Scenario: A second trigger while pending updates the existing review

- **WHEN** a survey that already has a `pending` review is screened again and still scores at or above the threshold
- **THEN** the existing row's score and signals SHALL be updated
- **AND** no second review row SHALL be created and no second notice SHALL be sent

#### Scenario: Released content is not held again

- **WHEN** a survey has a `cleared` review whose fingerprint equals the fingerprint of the current text
- **THEN** no new review SHALL be created regardless of the score

#### Scenario: Edited content after release is screened afresh

- **WHEN** a survey has a `cleared` review and its `redirect_url` is changed so the fingerprint differs
- **THEN** screening SHALL run and MAY create a new `pending` review

#### Scenario: Below threshold leaves no trace

- **WHEN** a survey scores below the threshold
- **THEN** no `ContentReview` row and no `AbuseEvent` SHALL be written

### Requirement: `CONTENT_SCREENING` kill switch

The system SHALL read `CONTENT_SCREENING` from the environment (default on). When off, screening SHALL return before collecting any text and SHALL create no review; existing `pending` reviews SHALL keep holding their surveys until decided.

#### Scenario: Switch off disables scoring

- **WHEN** `CONTENT_SCREENING` is off and a lure survey is published
- **THEN** no review SHALL be created and the survey SHALL serve to respondents

#### Scenario: Switch off does not release an existing hold

- **WHEN** `CONTENT_SCREENING` is off and a survey has a `pending` review
- **THEN** respondents SHALL still see the unavailable page until the owner decides

