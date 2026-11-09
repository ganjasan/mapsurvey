## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A site SHALL hold an ordered list of blocks of the kinds `heading`, `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents`, `map`, `results`, `event` and `contacts`, each with an optional title. Every write of a block SHALL pass `sites.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same site, map colours `#rrggbb` only, base maps only keys the workspace resolves, results only for a publishable question of a survey of the same workspace with a visualisation from its type's list, events only with a valid date, times, IANA time zone and a seat limit of 1–10000 or none, heading sizes only `l`, `m` or `s` (default `m`), contacts at most six people with well-formed e-mails. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another site SHALL be refused.

#### Scenario: Rich text is sanitised
- **WHEN** a text block is saved with `<p>Hello</p><script>alert(1)</script>`
- **THEN** the stored body is `<p>Hello</p>` without the script

#### Scenario: Unsafe button link refused
- **WHEN** a button block is saved with URL `javascript:alert(1)`
- **THEN** the save is refused with a field error naming the URL

#### Scenario: Video only from YouTube or Vimeo
- **WHEN** a video block is saved with `https://youtu.be/dQw4w9WgXcQ`
- **THEN** the stored embed is the YouTube player URL for that video, and a URL from another host is refused

#### Scenario: Reorder
- **WHEN** the builder posts the block ids in a new order
- **THEN** the blocks' order is 0..N in that order, and a list containing another site's block id is refused with 400

## ADDED Requirements

### Requirement: Contacts block
A **Contacts** block SHALL list up to six people — name, role, e-mail, phone — edited as rows in the block on the canvas, with an address and opening hours in its Settings. The public page SHALL draw each person with a name as a card whose e-mail is a `mailto:` link and whose phone is a `tel:` link; a row without a name SHALL be kept and not drawn. A malformed e-mail SHALL be refused with a field error; the block SHALL be drawn once it has a named person or an address.

#### Scenario: Team on the page
- **WHEN** a contacts block with "Ana Ruiz, Project lead, ana@city.example, +1 410 555 0100" is published
- **THEN** the page shows her card with `mailto:ana@city.example` and `tel:+14105550100`

#### Scenario: Bad e-mail refused
- **WHEN** a person's e-mail is saved as `ana@`
- **THEN** the save is refused with an error naming the address

#### Scenario: Row being typed
- **WHEN** the builder autosaves a row with a phone and no name
- **THEN** it is kept and the public page does not draw it
