## ADDED Requirements

### Requirement: Three plan cards from one partial
The site SHALL describe its plans with ONE template, `partials/_plan_cards.html`, rendering three
cards in this order: **Free**, **Pro** and **Done for you**. It SHALL be the only template in
`survey/templates` and `billing/templates` that states the Pro price. The Pro card's capability
bullets SHALL be the labels of the Pro features in `billing/features.py`.

#### Scenario: Cards and figures
- **WHEN** the partial is rendered
- **THEN** the Free card SHALL show `$0`
- **AND** the Pro card SHALL show `$49` a month and `$490` a year, per workspace
- **AND** the Done-for-you card SHALL show no figure and say it is quoted after a call

#### Scenario: Pro bullets follow the registry
- **WHEN** a feature is added to `billing/features.py` for the Pro plan
- **THEN** its label SHALL appear on the Pro card without editing the partial's bullet list

#### Scenario: The figure lives in one template
- **WHEN** the templates are read from disk
- **THEN** `$49` SHALL appear in `partials/_plan_cards.html` and in no other template under
  `survey/templates` or `billing/templates`

#### Scenario: Monthly or yearly
- **WHEN** the visitor switches the period from monthly to yearly
- **THEN** the Pro card SHALL show the yearly figure instead of the monthly one, without JavaScript

#### Scenario: Done for you leads to a call
- **WHEN** the Done-for-you card is rendered
- **THEN** its button SHALL link to `/demo/` with `src=pricing` on public pages and `src=billing`
  on Plan & billing
- **AND** it SHALL link to `/services/`

#### Scenario: Readable on a phone
- **WHEN** the viewport is 360px wide
- **THEN** the cards SHALL stack in one column without horizontal scrolling

### Requirement: Public pricing page
The site SHALL serve `/pricing/` (URL name `pricing`) to everyone, built on `base_landing.html`,
listed in `sitemap.xml`, with the plan cards, a payment FAQ and links to `/pro/` and `/services/`.

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor opens `/pricing/`
- **THEN** the response SHALL be 200 with the three cards
- **AND** the Free and Pro buttons SHALL lead to registration

#### Scenario: Signed-in owner or admin
- **WHEN** a signed-in owner or admin of the active organisation opens `/pricing/`
- **THEN** the Pro button SHALL link to that organisation's Plan & billing page

#### Scenario: Payment questions answered
- **WHEN** `/pricing/` is rendered
- **THEN** it SHALL say that PayPro Global is the merchant of record, that the yearly plan can be
  paid by invoice or purchase order, and that cancelling keeps every survey and response

#### Scenario: In the sitemap
- **WHEN** `sitemap.xml` is requested
- **THEN** it SHALL list `/pricing/`

### Requirement: Pricing in the marketing nav
The navbar of `base_landing.html` SHALL carry a **Pricing** item linking `/pricing/` and SHALL
NOT carry a **Pro** item.

#### Scenario: Nav item
- **WHEN** any page built on `base_landing.html` is rendered
- **THEN** the navbar SHALL link "Pricing" to `/pricing/`
- **AND** the navbar SHALL NOT link to `/pro/`

### Requirement: Plan cards on Plan & billing
The Plan & billing page SHALL render the plan cards with the organisation's current plan marked.
On Free (or a lapsed Pro) with products configured, the owner SHALL see one **Upgrade to Pro**
button posting the period selected on the card and a **Get a quote** button for the yearly plan;
other members SHALL see that only the owner can upgrade. The "Prices" link SHALL lead to
`/pricing/`. The current-plan state, the manage block and the cancellation note are unchanged.

#### Scenario: Free organisation, owner
- **WHEN** the owner of a Free organisation opens Plan & billing
- **THEN** the Free card SHALL be marked as the current plan
- **AND** the Pro card SHALL show its price and an **Upgrade to Pro** button posting `period` to
  `org_checkout`, plus **Get a quote** posting `period=yearly` and `quote=1`

#### Scenario: Yearly selected
- **WHEN** the owner selects yearly on the Pro card and presses **Upgrade to Pro**
- **THEN** the checkout SHALL start for the yearly product

#### Scenario: Pro organisation
- **WHEN** a Pro organisation's owner opens Plan & billing
- **THEN** the Pro card SHALL be marked as the current plan and SHALL carry no upgrade button

#### Scenario: Admin who is not the owner
- **WHEN** an admin of a Free organisation opens Plan & billing
- **THEN** the Pro card SHALL say that only the organisation owner can upgrade and carry no
  checkout form
