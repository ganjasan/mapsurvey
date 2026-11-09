## ADDED Requirements

### Requirement: Accessibility checks in the builder
The builder SHALL flag, without blocking publishing: an image block or the cover with a picture and no description; a small heading block that comes before any large or medium heading or any block heading on the page; a link in a text block or a button whose text is only a vague phrase ("here", "click here", "more", "read more", "this link", "link", "this"). Each flag SHALL appear under its block on the canvas and as an icon on its outline row, and the Publish popover SHALL list the count with links to the flagged blocks. Viewers SHALL NOT see the flags. The public page SHALL carry a "Skip to content" link to `<main id="main">` and a visible focus outline on links, buttons and form fields.

#### Scenario: Picture without a description
- **WHEN** an image block has a picture and an empty description
- **THEN** the canvas shows the accessibility note under it and the popover counts one thing to check

#### Scenario: Subheading first
- **WHEN** the first heading on the page is a small heading block
- **THEN** it is flagged; a small heading after a medium one is not

#### Scenario: Vague link text
- **WHEN** a text block contains `<a href="…">here</a>`
- **THEN** it is flagged; a link that names its target is not

#### Scenario: Skip link
- **WHEN** a published site is opened
- **THEN** the page starts with a "Skip to content" link to `#main`
