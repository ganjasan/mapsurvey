## MODIFIED Requirements

### Requirement: The badge appears on every respondent-facing surface
The "Made with Mapsurvey" badge SHALL render on the survey page, the thanks page and the public
results page `/r/<slug>/` for every survey, linking to the registration page with
`utm_source=viral_loop` and a `utm_medium` naming the surface (`survey`, `thanks`, `results`),
**unless** `unbranded` is in force for the survey's organisation (`covers("unbranded")`: the plan
includes it, or a live Pro trial includes it, spent or not) **and** the survey's `show_branding` is
false. The editor's thanks-page preview SHALL apply the same rule so the creator sees what
respondents see.

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

#### Scenario: Trial switch-off spent
- **WHEN** a survey was switched to `show_branding=false` under a live trial and that used the trial's only switch-off
- **THEN** the badge stays hidden while the trial is live

#### Scenario: Trial expires
- **WHEN** the trial's `expires_at` passes
- **THEN** the badge renders again on the next request, without any data change

### Requirement: The branding switch is editable only with the entitlement
The survey settings control for `show_branding` SHALL be enabled for surveys of organisations for
which `may("unbranded")` is true, and on any survey whose badge is already off (so it can be turned
back on); otherwise it SHALL be shown disabled with an "Upgrade to Pro" hint that links to the Pro
trial block of Plan & billing, and a submitted switch-off SHALL be ignored. When the organisation's
plan lacks `unbranded` and a save turns the switch from on to off, the settings service SHALL
consume one `unbranded` allowance; if none is left the value SHALL NOT be stored and the form SHALL
show an error on `show_branding` saying the trial for this is used up. Switching the badge back on
SHALL consume nothing and refund nothing.

#### Scenario: Free creator submits show_branding=false
- **WHEN** a creator in a Free organisation without a trial submits the survey settings form with `show_branding` unchecked
- **THEN** the stored value is unchanged and the badge keeps rendering

#### Scenario: Pro creator switches it off
- **WHEN** a creator in a Pro organisation unchecks `show_branding`
- **THEN** the value is stored as false and no allowance changes

#### Scenario: Trial creator switches it off
- **WHEN** a creator in a Free organisation whose trial has 1 `unbranded` left unchecks `show_branding`
- **THEN** the value is stored as false and the allowance reads 0 left

#### Scenario: Trial creator tries a second survey
- **WHEN** the same creator opens another survey's settings
- **THEN** the switch is disabled and an unchecked submission keeps the badge

#### Scenario: Turning the badge back on
- **WHEN** the creator opens the first survey's settings after the switch-off was spent
- **THEN** the switch is enabled, checking it stores the badge, and nothing is refunded
