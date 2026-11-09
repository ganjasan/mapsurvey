## ADDED Requirements

### Requirement: A site has a feed of updates
A site SHALL have a feed of updates (`SiteUpdate`), each of one kind: **news** — a title (plain, at most 160 characters), a date, rich text, an optional link (an absolute http(s) URL) and an optional survey of the site — or **"You said, we did"** — a title, a date, what residents said (plain text, at most 2000 characters), what was done (rich text), a status `included`, `partly` or `not` and an optional survey of the site. Rich text SHALL pass `coerce_creator_html`. An update SHALL be a draft until published; only published updates SHALL appear on the public site. Updates SHALL be ordered by date, newest first, then by creation. Deleting the linked survey's link SHALL keep the update without it. Duplicating a site and saving it as a template SHALL NOT copy its updates (they are the record of that engagement). Every write SHALL go through the sites service.

#### Scenario: News update
- **WHEN** an editor adds a news update titled "Draft plan published" dated 2027-03-01 with a body and publishes it
- **THEN** the site's feed has it with that date, and a draft added after it stays off the public site

#### Scenario: You said, we did
- **WHEN** an editor saves a "You said, we did" update with "More shade by the playground", what was done and status `partly`
- **THEN** the public card shows "You said", the residents' words, "We did", the answer and the badge "Partly included"

#### Scenario: Bad values refused
- **WHEN** an update is saved with link `javascript:alert(1)`, an empty title, a date that is not a date, or status `maybe`
- **THEN** the save answers 422 with a field error for each and the stored update is unchanged

#### Scenario: Updates are not copied
- **WHEN** a site with two updates is duplicated or saved as a template
- **THEN** the copy has no updates

### Requirement: The updates block shows the feed
Block kind `updates` SHALL show the site's published updates: the latest 3, 5, 10 or all (Settings, default 3) of one kind or both (Settings, default both). Any number of `updates` blocks SHALL show the same feed. When the feed holds more matching updates than the block shows, the block SHALL end with a link to the full feed at `/p/<slug>/updates/`. A block with no published update to show SHALL NOT be drawn on the public page. In the builder the block SHALL show drafts too, marked as drafts, and SHALL offer *Add news* and *Add "You said, we did"* in the block; each creates a draft dated today and opens it in the side panel. Clicking an update's card SHALL open it in the side panel, where its fields autosave (`autosave=1` → JSON, 422 with field errors), the *Published* switch publishes it, and *Delete update* asks through the app's confirmation dialog.

#### Scenario: Latest three on home, all on News
- **WHEN** a site has five published updates, a block on home set to 3 and a block on News set to all
- **THEN** home shows the newest three and a link to `/p/<slug>/updates/`, and News shows all five without the link

#### Scenario: Kind filter
- **WHEN** a block is set to "You said, we did" only
- **THEN** it shows only decision updates

#### Scenario: Empty block stays off the page
- **WHEN** a site has an updates block and only draft updates
- **THEN** the public page does not draw the block, and the builder shows the drafts marked as drafts

#### Scenario: Add an update in the block
- **WHEN** an editor presses *Add "You said, we did"* in the block
- **THEN** a draft decision update dated today exists and the builder opens it in the side panel

#### Scenario: Viewer cannot change updates
- **WHEN** a viewer posts to the add, edit or delete endpoint of an update
- **THEN** the answer is 403 and nothing changes

### Requirement: Every published update has an address
A published update SHALL be served at `/p/<slug>/updates/<id>/` and the whole feed at `/p/<slug>/updates/`, both with the site's header and menu, under the site's access rules (draft site → unavailable 404 except to members; unlisted → `noindex`). A draft update, or an update of another site, SHALL answer the unavailable 404 to visitors. Both addresses of a public published site SHALL be in the sitemap, and the review link and the visitor's language SHALL carry over as on any page.

#### Scenario: Update page
- **WHEN** a visitor opens `/p/<slug>/updates/<id>/` of a published update
- **THEN** the page shows the update with its date and kind, the site's menu, and `<title>` "<update title> · <site title>"

#### Scenario: Draft update is private
- **WHEN** a visitor opens the address of a draft update
- **THEN** the answer is the unavailable 404

#### Scenario: Sitemap
- **WHEN** a public published site has two published updates and one draft
- **THEN** the sitemap lists the feed and the two published updates, not the draft

### Requirement: Updates are translated and screened
An update's title, body and residents' words SHALL be translatable fields of the site on the Translations tab, keyed `update:<id>:title|body|said`, with outdated detection, the CSV round trip and fallback to the primary text. Content screening SHALL read updates, drafts included, and their translations.

#### Scenario: Translated update
- **WHEN** a site offered in Spanish has an update titled "Draft plan published" translated "Plan borrador publicado"
- **THEN** the Spanish feed and update page read "Plan borrador publicado"

#### Scenario: Update is screened
- **WHEN** a live site gets an update with a phishing lure that crosses the hold threshold
- **THEN** the site is held for review as for any other site text

## MODIFIED Requirements

### Requirement: Sites start from templates
The Sites list SHALL offer *From a template* next to *New site* with the Mapsurvey starters (Consultation, Master plan, Municipal site) and the workspace's own templates. A starter SHALL create a draft site whose blocks pass the same validation as any block, with the blocks that need the creator's material added empty; the Consultation and Master plan starters SHALL be one page, and the Municipal site starter SHALL create the pages About (the home page), Take part, Documents and News, each with its starter blocks, News holding an `updates` block that shows all updates. *Save as template* SHALL create a copy of a site marked as a template, with its pages, without survey links (its survey cards and results blocks kept, empty), without updates and without event registrations; starting from it SHALL copy its pages and blocks into a new draft. A template SHALL never be published or opened publicly. Starting a site from a starter or a template SHALL count as a Sites use; a template of another workspace SHALL be refused.

#### Scenario: Master plan starter
- **WHEN** an editor picks the Master plan starter
- **THEN** a draft opens with heading, text, map, timeline, survey card, heading, results, documents and contacts blocks, the text and phases filled in

#### Scenario: Municipal site starter
- **WHEN** an editor picks the Municipal site starter
- **THEN** a draft opens with the pages About, Take part, Documents and News in that order, About as the home page at the site's address, each page holding its starter blocks, and News an `updates` block set to all

#### Scenario: Workspace template
- **WHEN** a site with a survey card is saved as a template and a new site is started from it
- **THEN** the template keeps both blocks without survey links, publishing it is refused, its address is 404, and the new site has the same blocks

#### Scenario: Template keeps pages
- **WHEN** a site with three pages is saved as a template and a new site is started from it
- **THEN** the new site has the same three pages with their blocks

#### Scenario: Another workspace's template
- **WHEN** an editor posts the template of another workspace
- **THEN** the answer is 404 and nothing is created

#### Scenario: Trial used up
- **WHEN** a free workspace whose trial is used picks a starter
- **THEN** no site is created
