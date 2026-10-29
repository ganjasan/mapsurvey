# share-page — delta for printable-form

## ADDED Requirements

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
