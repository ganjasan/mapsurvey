## MODIFIED Requirements

### Requirement: The hero renders on the dashboard only, and suppresses the small card everywhere
The dashboard `/editor/` SHALL render a pending hero above the survey list: the plate (`art`
or `image`), the eyebrow, the title, the body, the chips, one primary call-to-action linking
to `link` with `link_query`, the "How it works" link when `help` resolves to a help page, the
`note` when `note_if` holds, a × and "Don't show these". While a hero is pending the system
SHALL render no small card on any page, and SHALL render the hero on no page but the
dashboard. The hero SHALL NOT render on respondent surfaces, for anonymous users, or when
`changelog_cards` is off.

On a viewport narrower than 768 px the hero SHALL render collapsed to one row — the "New"
badge, the title, a chevron and the × — and SHALL show the rest of the card only after the
creator taps that row; a second tap collapses it again. The collapsed state SHALL NOT be
remembered between page loads and SHALL NOT move the watermark. The first expand on a page
SHALL capture `changelog_card_expanded` with `entry_id` and `tier: 'hero'`. On 768 px and wider
the row SHALL NOT be shown and the full card SHALL render as before.

#### Scenario: Dashboard shows the hero
- **WHEN** a creator with a pending hero opens `/editor/`
- **THEN** the response contains the hero with its title, the CTA linking to the resolved
  `link` plus `link_query`, and no small-card markup

#### Scenario: Editor page shows nothing while the hero is pending
- **WHEN** the same creator opens a survey editor page
- **THEN** the response contains neither the hero nor the small card

#### Scenario: Free workspace sees the note
- **WHEN** the hero declares `note_if: free_plan` and the active workspace is on Free
- **THEN** the hero shows the `note` line; on a Pro workspace it does not

#### Scenario: Phone shows one row
- **WHEN** a creator with a pending hero opens `/editor/` on a 390 px wide screen
- **THEN** the hero is one row with the badge, the title and the ×, and the first survey card
  is visible on the first screen

#### Scenario: Tapping the row expands the card
- **WHEN** the creator taps the collapsed row
- **THEN** the body, the call to action and "Don't show these" appear, the row's
  `aria-expanded` is `true`, and the watermark is unchanged

#### Scenario: The disclosure is in the markup
- **WHEN** the dashboard renders a pending hero
- **THEN** the response contains a toggle button with `aria-expanded="false"` whose
  `aria-controls` names the element holding the body and the actions
