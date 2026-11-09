## ADDED Requirements

### Requirement: A draft can be shared for review
The Publish popover of an unpublished site SHALL offer a review link `/p/<slug>/?review=<token>`, signed with the site's review salt and valid 14 days, that opens the draft read-only for anyone without an account. The page SHALL carry a "Shared for review" banner, `noindex`, `Cache-Control: private, no-store` and `Referrer-Policy: no-referrer`; event registration SHALL be replaced by a note and the report link hidden. **New link** SHALL rotate the salt so every earlier link stops working; only owners, admins and editors MAY rotate it. A site held for a safety review SHALL NOT open through a review link.

#### Scenario: Client opens the draft
- **WHEN** someone without an account opens an unpublished site with a valid review token
- **THEN** the draft renders with the review banner, no registration form and `noindex`

#### Scenario: Without or with a bad token
- **WHEN** the same draft is opened without a token, with a tampered one, or after 15 days
- **THEN** the answer is the unavailable 404

#### Scenario: New link revokes the old one
- **WHEN** an editor presses New link
- **THEN** the old token gives 404 and the new one opens the draft

#### Scenario: Held site stays closed
- **WHEN** a site held for a safety review is opened with a valid review token
- **THEN** the answer is the unavailable 404
