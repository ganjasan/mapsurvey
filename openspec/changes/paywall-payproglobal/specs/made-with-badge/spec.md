## MODIFIED Requirements

### Requirement: The badge appears on every respondent-facing surface
The "Made with Mapsurvey" badge SHALL render on the survey page, the thanks page and the public
results page `/r/<slug>/` for every survey, linking to the registration page with
`utm_source=viral_loop` and a `utm_medium` naming the surface (`survey`, `thanks`, `results`),
**unless** the survey's organisation holds the `unbranded` entitlement **and** the survey's
`show_branding` is false. The editor's thanks-page preview SHALL apply the same rule so the
creator sees what respondents see.

#### Scenario: Public results page carries the badge
- **WHEN** a visitor opens a public results page of a Free organisation's survey
- **THEN** the badge is present with `utm_source=viral_loop&utm_medium=results`

#### Scenario: Surfaces are distinguishable
- **WHEN** a visitor arrives at registration from the badge
- **THEN** `utm_medium` identifies which surface they came from

#### Scenario: Pro organisation turns branding off
- **WHEN** the survey's organisation is Pro and `show_branding` is false
- **THEN** none of the three surfaces nor the editor preview renders the badge

#### Scenario: Pro organisation keeps branding on
- **WHEN** the survey's organisation is Pro and `show_branding` is true
- **THEN** the badge renders as for a Free organisation

#### Scenario: Entitlement lapses
- **WHEN** a Pro organisation's subscription lapses and `show_branding` is still false
- **THEN** the badge renders again on the next request, without any data change

## ADDED Requirements

### Requirement: The branding switch is editable only with the entitlement
The survey settings control for `show_branding` SHALL be enabled only for surveys of
organisations with the `unbranded` entitlement; for others it SHALL be shown disabled with an
"Upgrade to Pro" hint and submitted values SHALL be ignored.

#### Scenario: Free creator submits show_branding=false
- **WHEN** a creator in a Free organisation submits the survey settings form with `show_branding` unchecked
- **THEN** the stored value is unchanged and the badge keeps rendering

#### Scenario: Pro creator switches it off
- **WHEN** a creator in a Pro organisation unchecks `show_branding`
- **THEN** the value is stored as false
