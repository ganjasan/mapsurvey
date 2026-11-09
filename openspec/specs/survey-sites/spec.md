# survey-sites Specification

## Purpose
Sites (epic #348): a workspace-owned public page at `/p/<slug>/` for an engagement, built from a closed set of blocks, linking any number of the workspace's surveys, showing results and taking event registrations; Pro to build, online after a lapse.
## Requirements
### Requirement: A site is a workspace-owned public page
The system SHALL provide `Site`, owned by one `Organization`, with a title, a plain-text summary, an optional cover picture on the public media tier under a random key, a unique slug, a page language, a visibility (`public` or `unlisted`) and a published flag. Members with the owner, admin or editor role of that workspace SHALL create, edit, publish, unpublish and delete its sites; viewers SHALL see the builder read-only; anyone else SHALL get 404 for a site's builder URL, whatever their active workspace.

The builder SHALL be a canvas: it SHALL render every block with the same templates as the public page, SHALL let the creator edit headings and text in place, SHALL show a toolbar on the hovered block (drag, move up, move down, duplicate, settings, delete) and a "+" between blocks that opens the block library, SHALL list the blocks in an outline that scrolls to and selects a block, and SHALL show the selected block's non-text settings in a side panel (the page's settings when nothing is selected). Changes SHALL be saved automatically: a post with `autosave=1` SHALL answer JSON with the re-rendered block and outline row, or `422` with field errors; a block with incomplete data (empty text, no files, no area, no question, no date) SHALL be kept in the builder and SHALL NOT be drawn on the public page. Publishing, the listed/unlisted switch, the address and the QR code SHALL live in one popover on the Publish button. A desktop / phone toggle SHALL reflow the canvas to 390 px.

#### Scenario: Editor creates a site
- **WHEN** an editor of a Pro workspace posts a title "Riverside Park plan" to create a site
- **THEN** a draft site exists in that workspace with slug `riverside-park-plan` and the browser is sent to its builder

#### Scenario: Viewer cannot change a site
- **WHEN** a viewer posts to any builder endpoint of a site of their workspace
- **THEN** the response is 403 and nothing changes

#### Scenario: Another workspace's site is invisible
- **WHEN** a member of workspace A opens the builder URL of a site of workspace B
- **THEN** the response is 404

#### Scenario: Slug rules
- **WHEN** settings are saved with slug `Edit`, `ab`, or a slug another site has
- **THEN** the save is refused with a field error and the site keeps its slug

#### Scenario: Autosave answers the re-rendered block
- **WHEN** the builder posts a text block's new body with `autosave=1`
- **THEN** the answer is JSON with `ok` true, the block's canvas HTML containing the new body and its outline row, and the body is stored sanitised

#### Scenario: Autosave refusal keeps the block
- **WHEN** the builder posts a button block with URL `javascript:alert(1)` and `autosave=1`
- **THEN** the answer is 422 JSON with an error for `url` and the stored block is unchanged

#### Scenario: Incomplete block stays off the public page
- **WHEN** a text block is added from the library and never written in
- **THEN** the builder shows it (empty, selected) and the published page does not

#### Scenario: Canvas renders every kind editable
- **WHEN** an editor opens a site with one block of every kind
- **THEN** every block renders in the canvas with its kind tag, a toolbar and editable text fields, and a panel exists for each

#### Scenario: Read-only canvas
- **WHEN** a viewer, or an editor of a lapsed workspace, opens the builder
- **THEN** the canvas renders without editable fields, toolbars or the "+" lines, and the panel inputs are disabled

### Requirement: Surveys are linked to sites many-to-many
A site SHALL link any number of canonical surveys of its own workspace (the page shows them where the creator puts their survey cards), and a survey SHALL be linkable to any number of sites. Linking a draft copy or an archived version SHALL link its canonical survey. A survey of another workspace, an archived or a trashed survey SHALL NOT be linkable. Unlinking a survey SHALL remove the survey cards that show it.

#### Scenario: One survey on two sites
- **WHEN** an editor links survey S to site L1 and to site L2
- **THEN** both sites list S and each can show a card for it

#### Scenario: Foreign survey refused
- **WHEN** a link request names a survey of another workspace
- **THEN** the response is 404 and nothing is linked

#### Scenario: Unlinking removes cards
- **WHEN** an editor unlinks survey S from a site that has a card for S
- **THEN** the card is deleted with the link

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

### Requirement: A survey card shows the survey's current state
A survey card SHALL be drawn from the linked survey at request time: a published survey within its period SHALL show "open" and a link to the survey; a published survey before `opens_at` SHALL show the opening date and no link; a closed survey or one past `closes_at` SHALL show "closed" and, when the survey has a published public results page, a link to it; a draft or testing survey SHALL show "coming soon" and no link; an archived, trashed or held survey SHALL not be drawn on the public page.

#### Scenario: Open survey
- **WHEN** a site shows a card for a published survey with no period
- **THEN** the card carries the survey's public URL and the "Take part" label (or the creator's label)

#### Scenario: Closed survey with results
- **WHEN** the linked survey is closed and its public results page is published
- **THEN** the card shows "Closed" and links to `/r/<slug>/`

#### Scenario: Draft survey
- **WHEN** the linked survey is a draft
- **THEN** the card shows "Coming soon" and no link

### Requirement: The public page serves published sites at /p/<slug>/
`/p/<slug>/` SHALL render a published site: the hero (title, summary, cover), an anchor navigation listing the titled blocks, the blocks in order, and a footer with the workspace name, the "Made with Mapsurvey" badge unless the workspace holds `unbranded`, and a report link. An unpublished or held site SHALL answer the same 404 page an unknown survey gets, except to members of the owning workspace, who SHALL see it with a draft banner. An unlisted site SHALL carry `noindex` and SHALL be absent from the sitemap; a public published site SHALL be listed in the sitemap. The page SHALL load no product analytics.

#### Scenario: Draft is private
- **WHEN** an anonymous visitor opens the slug of a draft site
- **THEN** the response is 404 with the survey-unavailable page

#### Scenario: Member previews a draft
- **WHEN** a member of the owning workspace opens the same URL
- **THEN** the page renders with the banner "Draft — only your workspace sees this"

#### Scenario: Unlisted
- **WHEN** a published unlisted site is requested
- **THEN** the page carries `<meta name="robots" content="noindex">` and the sitemap has no entry for it

#### Scenario: No analytics
- **WHEN** a published site is rendered with a PostHog key configured
- **THEN** the response contains no PostHog snippet

### Requirement: Sites are a Pro feature that survives a lapse
Creating, editing and publishing a site SHALL need the `sites` feature (Pro plan, or a Pro trial with its allowance of one site created); refused requests SHALL get the feature-required page with status 403. Creating a site SHALL count one trial use. Unpublishing SHALL always be allowed. A site published while the workspace held the feature SHALL stay online after the subscription lapses; its builder SHALL open read-only with an upgrade banner.

#### Scenario: Free workspace refused
- **WHEN** an editor of a Free workspace whose trial is used elsewhere posts to create a site
- **THEN** the response is 403 with the feature-required page and no site exists

#### Scenario: Lapsed workspace keeps its page
- **WHEN** a site was published under Pro and the subscription has ended
- **THEN** `/p/<slug>/` still renders it, a builder save is refused with 403 and unpublish succeeds

### Requirement: Site text is screened like survey text
Publishing a site, and saving any part of a published site, SHALL run content screening over the site's title, summary, block titles, text, FAQ, phases, captions, button labels and links. A score at or above the hold threshold SHALL open a pending `ContentReview` for the site and mail the moderator; while it is pending the public page SHALL answer the 404 page to everyone outside the workspace. Screening SHALL fail open. A visitor SHALL be able to report a site at `/p/<slug>/report/` with the same reasons and rate limit as a survey report; a report SHALL hold nothing.

#### Scenario: Lure site held
- **WHEN** a site whose text scores above the threshold is published
- **THEN** a pending review names the site, the moderator is mailed and an anonymous request to `/p/<slug>/` gets 404

#### Scenario: Report
- **WHEN** a visitor reports a published site as phishing
- **THEN** a `reported` review names the site, the moderator is mailed and the page keeps serving

### Requirement: A documents block offers files for download
A documents block SHALL hold 1–20 files uploaded by the creator, each with a title (default: the file name without its extension), stored on the public media tier under a random key. A file SHALL be accepted only when its extension is one of `pdf docx xlsx pptx odt ods odp doc xls ppt csv txt`, it is at most 25 MB, and its first bytes match its family (PDF header, zip header for OOXML/ODF, OLE header for legacy Office, UTF-8 text without HTML markup for csv/txt). Saving the block SHALL rename, remove and add files in one post; a block left without files SHALL be refused. The public page SHALL list each file with its title, type and size, linking to the file. File titles SHALL be screened with the site's text.

#### Scenario: PDF added
- **WHEN** an editor adds a documents block with `summary.pdf` starting with `%PDF-`
- **THEN** a file titled "summary" is stored under `site_files/` with a random name and the page lists it as PDF with its size

#### Scenario: Disguised HTML refused
- **WHEN** a file named `boards.pdf` whose content starts with `<html>` is uploaded
- **THEN** the save is refused with an error naming the file and nothing is stored

#### Scenario: Rename and remove in one save
- **WHEN** the block is saved with a new title for one file and the remove box ticked for another
- **THEN** the first keeps its file under the new title and the second is deleted

### Requirement: A map block shows the project area
A map block SHALL hold a FeatureCollection built from an uploaded GeoJSON file (FeatureCollection, Feature or geometry; at most 1 MB and 500 features; Point, LineString, Polygon or their Multi-forms; valid geometries within WGS84 bounds), keeping only each feature's geometry and a name (from `name`, `title` or `Name`), with coordinates rounded to 6 decimals. A save without a new file SHALL keep the stored area. The public page SHALL draw the area read-only on the chosen workspace base map (falling back to Streets), in the chosen colour, fitted to its bounds, and SHALL load the map library only when a map block is on the page.

#### Scenario: Polygon normalised
- **WHEN** a map block is saved with a Feature whose polygon has 10-decimal coordinates and properties `{"name": "Park", "owner": "x"}`
- **THEN** the stored FeatureCollection has one feature with properties `{"name": "Park"}` and 6-decimal coordinates

#### Scenario: Invalid file refused
- **WHEN** the upload is not JSON, has no geometry, or has a latitude of 120
- **THEN** the save is refused with an error and no block is created

#### Scenario: Leaflet only where needed
- **WHEN** a page with no map block renders
- **THEN** it does not load Leaflet; a page with a map block does

### Requirement: A results block shows aggregated answers to one question
A results block SHALL name one question by code of a survey linked to the site (linking it when needed) whose type the public results page can publish: a chart for choice, multichoice, rating, thumbs, number and range; a map for point, line, polygon and spray; a table for objects on the map. Text, date and other types SHALL be refused. Its payload SHALL come from `PublicResultsService` over the clean sessions of the canonical survey and its versions, masked with the survey's results-page K (3 without a page), with no map popups and no free text, and SHALL be cached for 60 seconds. The page SHALL draw it with the same renderer as `/r/<slug>/`, and SHALL load the chart and map libraries only when a results block needs them. A block whose question no longer exists SHALL not be drawn.

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
The browser code that draws result payloads SHALL live in one static file, `js/public_results_render.js`, exposing `renderResultBlocks(blocks, basemaps)`; `/r/<slug>/` and sites SHALL both load it and SHALL NOT carry their own copy.

#### Scenario: Public results page uses the shared renderer
- **WHEN** `/r/<slug>/` renders
- **THEN** it loads `public_results_render.js` and calls `renderResultBlocks`

### Requirement: Residents register for an event on the site
An event block SHALL show the date, the time in the event's time zone, the place and the description, and, while registration is open and the event has not ended, a form with name, email and a consent line stating that the name and email are used only for this event and deleted 30 days after it. A registration SHALL be refused without consent or with an invalid email, SHALL be silently dropped when the honeypot is filled, and SHALL answer 429 after 5 registration posts per hour from one address. The seat limit SHALL hold under concurrent posts; a full event SHALL say so and store nothing. The same email SHALL hold at most one active registration per event; registering again SHALL send the confirmation again and store nothing new.

#### Scenario: Registration stored and confirmed
- **WHEN** a visitor registers "Ana" / "ana@example.org" with consent for an open event
- **THEN** one active registration exists, a confirmation mail with an `.ics` attachment and a cancel link goes to that address, and the page says to check the inbox

#### Scenario: Full event
- **WHEN** an event with 1 seat already has one active registration and a second visitor registers
- **THEN** no registration is stored and the page says the event is full

#### Scenario: Same email twice
- **WHEN** the same email registers twice for one event
- **THEN** one active registration exists and two confirmations were sent

#### Scenario: Honeypot and consent
- **WHEN** a post fills the hidden `website` field, or omits consent
- **THEN** nothing is stored

### Requirement: A registration can be cancelled from the confirmation mail
The cancel link SHALL open a page naming the event with a Cancel button; only a POST SHALL cancel, freeing the seat. An unknown token SHALL be 404.

#### Scenario: Cancel frees the seat
- **WHEN** the registrant of a 1-seat event posts the cancel form
- **THEN** the registration is cancelled and another visitor can register

### Requirement: The workspace sees and removes its attendees
Owners, admins and editors of the site's workspace SHALL see each event's registrations (name, email, time, status), download them as CSV with formula-looking cells guarded, and remove one or all; viewers and outsiders SHALL not (403 / 404). Seeing and removing SHALL NOT need Pro. The builder SHALL show the count and seats left.

#### Scenario: Viewer refused
- **WHEN** a viewer opens an event's attendee list
- **THEN** the response is 403

#### Scenario: CSV
- **WHEN** an editor downloads the CSV of an event with a registrant named `=HYPERLINK("x")`
- **THEN** the file has a header and the name cell starts with an apostrophe

### Requirement: Registrations are deleted 30 days after the event
A daily task SHALL delete the registrations of events that ended more than 30 days before; deleting the event block or the site SHALL delete its registrations. `/terms/` and `/trust/` SHALL state that site-page event registration stores a name and an email for the organising workspace and deletes them 30 days after the event.

#### Scenario: Purge
- **WHEN** the task runs and one event ended 31 days ago and another ends tomorrow
- **THEN** the first event's registrations are gone and the second's remain

#### Scenario: Policy pages
- **WHEN** `/terms/` and `/trust/` render
- **THEN** both mention event registration and the 30-day deletion

### Requirement: A block's primary actions happen in the block
In the builder, the control that makes a block what it is SHALL be inside the block on the canvas, and the Settings panel SHALL hold only secondary options. Primary, in the block: the picture of an image block (drop zone, choose, replace), the link of a video block, the link of a button block, the files of a documents block (add, rename, remove), the area of a map block (drop zone, replace), the questions and answers of an FAQ block (edit, add, remove), the phases of a timeline block (edit, add, remove, mark Now), the survey of an empty survey card, the question of an empty results block, the date, start, end and place of an event block, and the cover picture of the page head (choose, drop, replace, remove). Secondary, in Settings: picture description (of a block and of the cover), button style, map colour and base map, chart style, a card's or a results block's change of survey or question, time zone, seats, the registration switch and the attendee list. No block SHALL tell the creator to go to the settings to fill it in. The values SHALL be saved through the same block form and validation as before.

#### Scenario: Empty image block
- **WHEN** an editor adds an Image block
- **THEN** the block shows a drop zone with a "choose a file" control and no text pointing to the settings

#### Scenario: FAQ edited in place
- **WHEN** the builder renders an FAQ block with two questions
- **THEN** both questions and answers are editable in the block, with a remove control per row and an "Add a question" control

#### Scenario: A row still being written
- **WHEN** the builder autosaves an FAQ row whose answer is typed before its question
- **THEN** the row is kept without an error, and the public page draws only the rows that have a question

#### Scenario: Secondary option in Settings
- **WHEN** the builder renders a map block's settings
- **THEN** the panel offers the colour and the base map and no GeoJSON upload

#### Scenario: Cover picture on the page head
- **WHEN** an editor presses "Add a cover picture" on the page head, or drops a picture onto it
- **THEN** the file chooser opens (or the dropped picture is taken), the cover is saved at once and shown, and a remove control appears beside "Change the cover picture"

### Requirement: The module is called Sites
Every creator surface SHALL name the module **Sites** and the object a **site**: the sidebar item, the list page, the builder, the publish popover, the Pro offer, the help page and the changelog. Editor addresses SHALL live under `/editor/sites/`; the public address SHALL stay `/p/<slug>/`. Text about what is drawn on the canvas MAY keep "page" (for example "Blocks on the page"). The marketing site's "landing pages" (SEO landings) are a different thing and SHALL keep their names.

#### Scenario: Sidebar and list
- **WHEN** a member of a Pro workspace opens the editor
- **THEN** the sidebar shows "Sites" linking to `/editor/sites/`, and the list page offers "New site"

#### Scenario: Old editor address
- **WHEN** someone requests `/editor/landings/`
- **THEN** the answer is 404: the old address never shipped

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

