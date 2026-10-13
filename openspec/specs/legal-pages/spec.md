# legal-pages Specification

## Purpose
TBD - created by archiving change dpga-readiness. Update Purpose after archive.
## Requirements
### Requirement: Public Terms of use page

The system SHALL serve a public page at `/terms/` (URL name `terms_page`), built on `base_landing.html`, reachable without login, indexable, and listed in `sitemap.xml`. The page SHALL show a "Last updated" date that changes only when its text changes, and SHALL contain sections with these anchor ids: `terms`, `acceptable-use`, `prohibited`, `moderation`, `harassment`, `children`, `personal-data`, `contact`.

#### Scenario: Anonymous visitor opens the Terms

- **WHEN** an anonymous visitor requests `/terms/`
- **THEN** the response SHALL be HTTP 200
- **AND** the page SHALL contain elements with ids `acceptable-use`, `prohibited`, `moderation`, `harassment`, `children` and `personal-data`

#### Scenario: Terms is in the sitemap

- **WHEN** `/sitemap.xml` is requested
- **THEN** it SHALL contain a `<loc>` ending in `/terms/`

### Requirement: Acceptable use & safety content

The `acceptable-use` part of the Terms SHALL state: (1) the prohibited content and uses — child sexual abuse material listed first, then phishing and fraud, illegal content, harassment and hate, exposure of private persons' data (doxxing), surveys impersonating a public authority or faking a public consultation, and spam or platform abuse; (2) how content is detected — screening at publication, holds, the "Report this survey" link usable without an account, private storage of respondent uploads; (3) moderation — release or take-down by a staff member, account suspension, reporting of child sexual abuse material to authorities, appeals; (4) response times — held surveys usually within one day, first assessment of reports within 2 business days, child sexual abuse material and imminent-harm reports the same day; (5) harassment protection — no respondent accounts or messaging, shared-map comments hidden by default, creator approval and hiding of marks and comments, members-only comment threads; (6) children — creator accounts for people aged 16 and over, creators responsible for consent when surveying children; (7) a personal-data summary linking to `/trust/`. The contact address SHALL be `konuchovartem@mapsurvey.org`. Every statement SHALL describe behaviour that exists in production when the page ships.

#### Scenario: CSAM is named and comes first

- **WHEN** the `prohibited` section is rendered
- **THEN** its first listed item SHALL name child sexual abuse material

#### Scenario: Response times are stated

- **WHEN** the `moderation` section is rendered
- **THEN** it SHALL state "2 business days" for a first assessment and same-day handling for child sexual abuse material

#### Scenario: Minimum age is stated

- **WHEN** the `children` section is rendered
- **THEN** it SHALL state that accounts are for people aged 16 and over

### Requirement: Privacy URL redirects to Trust

`/privacy/` SHALL respond with HTTP 301 to `/trust/`. It SHALL NOT be listed in `sitemap.xml`.

#### Scenario: Privacy redirect

- **WHEN** a visitor requests `/privacy/`
- **THEN** the response SHALL be a 301 whose `Location` is `/trust/`

### Requirement: Trust page names the owner

`/trust/` SHALL contain an "Ownership" block stating that Mapsurvey — the source code and the hosted service — is owned and operated by Artem Koniukhov, a sole proprietor in the Kyrgyz Republic, who holds the copyright in the code published under AGPLv3, and that surveys and responses belong to the creator who collected them. The "Who is behind Mapsurvey" block SHALL use the name Artem Koniukhov. The page SHALL link to `/terms/`.

#### Scenario: Ownership block present

- **WHEN** `/trust/` is rendered
- **THEN** it SHALL contain an element with id `ownership` and the text "Artem Koniukhov"
- **AND** it SHALL NOT contain the text "Artem Konuchov"
- **AND** it SHALL contain a link to `/terms/`

