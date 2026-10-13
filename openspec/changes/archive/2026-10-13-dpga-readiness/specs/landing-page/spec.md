## MODIFIED Requirements

### Requirement: Footer
The landing page SHALL display a footer with contact info, navigation links, legal links, and a copyright line naming the owner.

#### Scenario: Footer content
- **WHEN** a page built on `base_landing.html` is rendered and `BOOK_A_CALL_URL` is set
- **THEN** the footer "Connect" column SHALL offer a "Book a call" link to `BOOK_A_CALL_URL`, alongside email, Telegram and GitHub
- **AND** the footer SHALL NOT link to Discord
- **AND** the footer SHALL NOT display any login or registration links
- **AND** the footer "Legal" column SHALL link "Terms of use" to `/terms/` and "Privacy & Trust" to `/trust/`
- **AND** the copyright line SHALL read "© 2021–<current year> Artem Koniukhov" (the existing AGPLv3 licence line stays next to it)
