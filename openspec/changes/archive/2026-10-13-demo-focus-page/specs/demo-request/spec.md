## MODIFIED Requirements

### Requirement: Two-step demo request page
The system SHALL serve a public page at `/demo/` that asks an anonymous or signed-in visitor for an email address only, and on submission SHALL store a `DemoRequest` and continue to a second step at `/demo/<key>/` that asks for name, organisation, what they plan to map and when. The second step SHALL be skippable. The page SHALL NOT require a consent checkbox, a CAPTCHA or picking a calendar slot. The page SHALL state that we reply once by email and keep no mailing list, and SHALL link the trust page. The page SHALL carry a `noindex` robots meta tag. Every state of the page SHALL be a focused page: no marketing navbar and no footer, only the Mapsurvey wordmark linking home, the form on one side and customer quotes on the other.

#### Scenario: Step one asks for an email only
- **WHEN** a visitor requests `/demo/`
- **THEN** the response is HTTP 200 with the heading "What's your work email?", a form whose only visible input is an email field, and a "Next" button

#### Scenario: Focused page without marketing chrome
- **WHEN** `/demo/`, a step-two URL or the done page is rendered
- **THEN** the response SHALL NOT contain the landing navbar or the landing footer
- **AND** it SHALL contain the Mapsurvey wordmark linking to `/`

#### Scenario: Submitting an email creates the lead and moves to step two
- **WHEN** a visitor POSTs a valid email to `/demo/`
- **THEN** one `DemoRequest` row is created with that email and the response redirects to `/demo/<key>/` for that row

#### Scenario: Step two completes the same row
- **WHEN** the visitor POSTs name, organisation, project and timeline to `/demo/<key>/`
- **THEN** the same row is updated, `details_at` is set, and the done state is shown

#### Scenario: Step two can be skipped
- **WHEN** the visitor follows "Skip for now" on step two
- **THEN** the done state is shown and the row keeps only the email

#### Scenario: A completed or expired key shows the done state
- **WHEN** `/demo/<key>/` is requested for a row whose `details_at` is set, or that is older than 7 days
- **THEN** the done state is shown and no further edits are accepted

#### Scenario: Unknown key
- **WHEN** `/demo/<key>/` is requested with a key that matches no row
- **THEN** the response is HTTP 404

#### Scenario: Signed-in creator sees their email pre-filled
- **WHEN** an authenticated user requests `/demo/`
- **THEN** the email field is pre-filled with their account email and the stored row references their user account

## ADDED Requirements

### Requirement: Customer quotes and logos on the demo page
The demo page SHALL show a carousel of real, attributed customer quotes, each taken verbatim from a published story, with the speaker's name, role, organisation, an avatar (an approved photo, otherwise their initials) and a link to that story. A quote whose story is not published SHALL NOT be shown, and the carousel SHALL be omitted when no quote qualifies. Without JavaScript the first quote SHALL be visible. Automatic rotation SHALL pause on hover and keyboard focus and SHALL NOT run when the visitor prefers reduced motion. The page SHALL show a strip of customer logos built from published stories that have a credit logo, each linking to its story, and SHALL omit the strip when no such story exists.

#### Scenario: Carousel of published quotes
- **WHEN** `/demo/` is rendered and the Pszów and Whitehouse stories are published
- **THEN** the carousel holds the quotes of Anna M. Pyziak (Towarzystwo Urbanistów Polskich), Julian Thomas and Cliff Schraibman (Whitehouse Community Council), each with initials and a story link
- **AND** only the first card is visible before any script runs

#### Scenario: Quote of an unpublished story
- **WHEN** a quoted story is not published
- **THEN** its quotes are not shown

#### Scenario: No qualifying quote
- **WHEN** none of the quoted stories is published
- **THEN** the carousel is not rendered

#### Scenario: Logo strip from published stories
- **WHEN** published stories with a credit logo exist
- **THEN** the page shows one logo per such story, with the credit as alt text, linking to the story
- **AND** unpublished stories and stories without a logo are not shown

#### Scenario: No logos, no strip
- **WHEN** no published story has a credit logo
- **THEN** the logo strip is not rendered
