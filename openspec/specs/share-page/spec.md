# share-page Specification

## Purpose
TBD - created by archiving change publish-prompt-on-share-draft. Update Purpose after archive.
## Requirements
### Requirement: Share page gates public links behind publish state
The Share page SHALL reveal copyable public share artifacts (the direct survey link, its
QR code, and the tracking-link form and list) only when the survey is publicly reachable,
i.e. `status == 'published'`. For any other status the Share page SHALL instead show a
status banner explaining that the public link returns a 404 until the survey is published
and that only the creator can open it (via Preview).

#### Scenario: Draft survey hides links and shows a banner
- **WHEN** an owner opens Share for a survey with `status == 'draft'`
- **THEN** the survey link, QR, and tracking-link form are not rendered
- **AND** a banner explains the public link 404s until the survey is published

#### Scenario: Testing survey hides public links
- **WHEN** an owner opens Share for a survey with `status == 'testing'`
- **THEN** the copyable public link section is not rendered
- **AND** the banner states the public link is not live yet

#### Scenario: Published survey shows the full Share page
- **WHEN** an owner opens Share for a survey with `status == 'published'`
- **THEN** the survey link, QR, and tracking sections render
- **AND** no publish banner is shown

### Requirement: Inline Publish from the Share page for owners
The Share page SHALL offer an inline Publish control to owners when the survey is not
publicly reachable and the transition to published is allowed. The control MUST publish
the survey through the existing lifecycle transition endpoint and then reload the page so
the shareable links appear. Non-owner editors MUST NOT see the control; they SHALL instead
see a hint to ask the survey owner to publish.

#### Scenario: Owner publishes inline
- **WHEN** an owner clicks Publish on the Share page of a draft survey
- **THEN** the survey transitions to `published`
- **AND** the Share page reloads and reveals the shareable links

#### Scenario: Non-owner editor sees no Publish control
- **WHEN** a user with the `editor` (non-owner) role opens Share for a draft survey
- **THEN** the inline Publish control is not shown
- **AND** the banner tells them to ask the survey owner to publish

### Requirement: The Share page offers a printable form in every status
The Share page SHALL carry a **Print a paper form** section, after the sharing sections (below
the tracking links on a published survey, below the publish banner otherwise), for every survey
status — it is not a public share artifact and is not gated behind publish state. It SHALL
offer the survey's languages (a select only when there is more than one), the paper size (A4
default; US Letter preselected when the creator's interface locale is `en-US` or `en-CA`), a
"Download PDF" control, and a hint that a draft prints with a watermark. A survey in `draft`
SHALL show the section beside the publish banner.

#### Scenario: Draft survey still offers the form
- **WHEN** an owner opens Share for a survey with `status == 'draft'`
- **THEN** the publish banner is shown and the Print section is rendered

#### Scenario: Language select only when needed
- **WHEN** an editor opens Share for a one-language survey
- **THEN** the Print section has no language select and the download link carries that language

#### Scenario: Letter for a US creator
- **WHEN** an editor whose interface locale is `en-US` opens Share
- **THEN** US Letter is the preselected paper size

