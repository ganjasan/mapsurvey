## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A landing SHALL hold an ordered list of blocks of the kinds `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents`, `map` and `results`, each with an optional title. Every write of a block SHALL pass `landings.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same landing, map colours `#rrggbb` only, base maps only keys the workspace resolves, results only for a publishable question of a survey of the same workspace with a visualisation from its type's list. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another landing SHALL be refused.

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
- **THEN** the blocks' order is 0..N in that order, and a list containing another landing's block id is refused with 400

## ADDED Requirements

### Requirement: A results block shows aggregated answers to one question
A results block SHALL name one question by code of a survey linked to the landing (linking it when needed) whose type the public results page can publish: a chart for choice, multichoice, rating, thumbs, number and range; a map for point, line, polygon and spray; a table for objects on the map. Text, date and other types SHALL be refused. Its payload SHALL come from `PublicResultsService` over the clean sessions of the canonical survey and its versions, masked with the survey's results-page K (3 without a page), with no map popups and no free text, and SHALL be cached for 60 seconds. The page SHALL draw it with the same renderer as `/r/<slug>/`, and SHALL load the chart and map libraries only when a results block needs them. A block whose question no longer exists SHALL not be drawn.

#### Scenario: Choice chart with masking
- **WHEN** a results block shows a choice question answered A by 5 clean sessions and B by 1, with K 3
- **THEN** the payload lists A with value 5 and B as "<3" with no value, and the page carries the renderer and Chart.js

#### Scenario: Text question refused
- **WHEN** a results block is saved for a text question
- **THEN** the save is refused with a field error

#### Scenario: Excluded sessions do not count
- **WHEN** one of the sessions is deleted and another marked not approved
- **THEN** neither contributes to the payload

#### Scenario: Deleted question
- **WHEN** the question of a results block is deleted from the survey
- **THEN** the public page omits the block and the builder marks it

### Requirement: The results renderer is shared with the public results page
The browser code that draws result payloads SHALL live in one static file, `js/public_results_render.js`, exposing `renderResultBlocks(blocks, basemaps)`; `/r/<slug>/` and landing pages SHALL both load it and SHALL NOT carry their own copy.

#### Scenario: Public results page uses the shared renderer
- **WHEN** `/r/<slug>/` renders
- **THEN** it loads `public_results_render.js` and calls `renderResultBlocks`
