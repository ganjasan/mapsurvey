## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A site SHALL hold an ordered list of blocks of the kinds `heading`, `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents`, `map`, `results` and `event`, each with an optional title. Every write of a block SHALL pass `sites.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same site, map colours `#rrggbb` only, base maps only keys the workspace resolves, results only for a publishable question of a survey of the same workspace with a visualisation from its type's list, events only with a valid date, times, IANA time zone and a seat limit of 1–10000 or none, heading sizes only `l`, `m` or `s` (default `m`). Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another site SHALL be refused.

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

### Requirement: Headings of a chosen size, in or out of the menu
A **Heading** block SHALL be the block's title on its own, in a size chosen in Settings: large and medium render as `<h2>`, small as `<h3>`; an empty heading block SHALL stay off the public page. Every block's heading SHALL be optional (the empty slot on the canvas reads "Heading (optional)"), and SHALL be a link in the menu at the top only while its "Show the heading in the menu at the top" is ticked (`SiteBlock.in_menu`, ticked by default). A text block SHALL offer Heading and Subheading (`<h2>`, `<h3>`) and SHALL store a posted `<h1>` as `<h2>`: the site title is the page's only `<h1>`.

#### Scenario: Three sizes
- **WHEN** a site with a large, a medium and a small heading block is published
- **THEN** the page shows two `<h2>` and one `<h3>` in their size classes and exactly one `<h1>`

#### Scenario: Heading kept out of the menu
- **WHEN** a text block's "Show the heading in the menu at the top" is unticked
- **THEN** its heading still shows above the text and the menu leaves it out

#### Scenario: Text without a heading
- **WHEN** a text block is published with its heading left empty
- **THEN** no heading is drawn and the menu gains nothing

#### Scenario: No second h1
- **WHEN** a text block is saved with `<h1>Big</h1>`
- **THEN** the stored body is `<h2>Big</h2>`
