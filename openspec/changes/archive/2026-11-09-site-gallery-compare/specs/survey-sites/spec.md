## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A site SHALL hold an ordered list of blocks of the kinds `heading`, `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents`, `map`, `results`, `event`, `contacts`, `gallery` and `compare`, each with an optional title. Every write of a block SHALL pass `sites.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same site, map colours `#rrggbb` only, base maps only keys the workspace resolves, results only for a publishable question of a survey of the same workspace with a visualisation from its type's list, events only with a valid date, times, IANA time zone and a seat limit of 1–10000 or none, heading sizes only `l`, `m` or `s` (default `m`), contacts at most six people with well-formed e-mails, gallery columns only 2, 3 or 4. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another site SHALL be refused.

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

### Requirement: Gallery and before/after blocks
A **Gallery** block SHALL hold 1–12 pictures, each verified by its bytes as a JPEG, PNG, WebP or GIF, added, captioned and removed in the block on the canvas, shown in 2–4 columns (two on a phone) and opened large on a tap; a picture's caption SHALL be its text alternative, and a picture without one SHALL be flagged by the accessibility checks. A **Before and after** block SHALL hold two verified pictures in two slots, each dropped or replaced in its half of the block, with an optional label per slot, and SHALL be drawn only when both are present, as the "after" picture over the "before" one revealed by a slider (both pictures one under the other without script). Both SHALL offer Full width and SHALL be translatable (captions, labels).

#### Scenario: Gallery
- **WHEN** two pictures are added to a gallery, one captioned "Board 1", the columns set to 2, and the site published
- **THEN** the page shows a two-column grid with `alt="Board 1"` and loads the lightbox script, and the uncaptioned picture is flagged

#### Scenario: Not a picture
- **WHEN** an HTML file is sent as a gallery picture
- **THEN** it is refused and nothing is stored

#### Scenario: Before and after
- **WHEN** only the before picture is present, then the after one is added, then the before one replaced
- **THEN** the block is drawn only once both are there, and each slot holds exactly one picture
