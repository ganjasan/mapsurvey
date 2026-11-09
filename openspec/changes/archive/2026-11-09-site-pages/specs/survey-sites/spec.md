## ADDED Requirements

### Requirement: A site is made of pages
A site SHALL have one or more pages (`SitePage`): a title (plain text, at most 60 characters), an address segment, an order and a menu flag. Every site SHALL have exactly one **home page**, created with the site, always first in the order, which SHALL NOT be deleted and SHALL be served at the site's address `/p/<slug>/`. Every other page SHALL be served at `/p/<slug>/<page-slug>/`, where the page slug follows the site slug rules (lowercase letters, digits and single hyphens, at most 64 characters), is unique within the site and SHALL NOT be one of the reserved segments (`report`, `events`, `updates`, `embed`, `review`, `feed`, `new`, `edit`, `admin`, `api`, `static`, `media`). Every block SHALL belong to exactly one page of its own site. A site SHALL have at most 12 pages. A new site — blank, from a starter without pages, or duplicated from a one-page site — SHALL start with the home page only; there SHALL be no choice between one page and several before the site is created.

#### Scenario: New site has one page
- **WHEN** an editor creates a site with *New site*
- **THEN** the site has exactly one page, the home page, and the builder shows no page tabs other than it

#### Scenario: Existing site becomes a one-page site
- **WHEN** the migration runs over a site with five blocks created before pages existed
- **THEN** the site has one home page holding the five blocks in their order, and `/p/<slug>/` renders the same blocks as before

#### Scenario: Page address
- **WHEN** a page titled "Take part" is added to the site `riverside-park`
- **THEN** it is served at `/p/riverside-park/take-part/`, and a second page with the same title gets `take-part-2`

#### Scenario: Reserved and invalid page slugs
- **WHEN** a page's address is saved as `report`, `events`, `Take Part` or the slug of another page of the same site
- **THEN** the save is refused with a field error and the page keeps its address

#### Scenario: Home page cannot be deleted
- **WHEN** an editor posts the delete action for the home page
- **THEN** the answer is 400 and the page and its blocks remain

#### Scenario: Page limit
- **WHEN** an editor adds a page to a site that has 12
- **THEN** no page is created and the builder says the site has the most pages it can have

#### Scenario: Block of another site's page
- **WHEN** a block is posted with, or moved to, a page of another site
- **THEN** the answer is 404 and the block keeps its page

### Requirement: The menu lists pages when there are several
On a site with one page the public menu SHALL be the anchor navigation of the page's titled blocks with the menu flag, as before pages existed. On a site with two or more pages the menu SHALL list the pages whose menu flag is on, in order, home first, with the current page marked `aria-current="page"`; the current page's block anchors SHALL be a second line under it when there are two or more. A page with the menu flag off SHALL be reachable by its address and SHALL NOT be listed. The home page SHALL show the hero (title, summary, cover); every other page SHALL show a compact header with the workspace brand, the site title as a link to the home page and the page title as the page's main heading, without the cover. Links between pages SHALL keep the visitor's language and an open review link. The page `<title>` of a non-home page SHALL be "<page title> · <site title>".

#### Scenario: One page keeps the block menu
- **WHEN** a published one-page site with three titled blocks is opened
- **THEN** the menu lists the three block headings as anchors and no page links

#### Scenario: Several pages
- **WHEN** a published site with pages Home, Take part and Documents is opened at `/p/<slug>/take-part/`
- **THEN** the menu lists the three pages with Take part marked current, the page's own blocks are drawn, the other pages' blocks are not, and the main heading is "Take part"

#### Scenario: Hidden page
- **WHEN** a page has its menu flag off
- **THEN** it is absent from the menu and its address still renders it

#### Scenario: Unknown page
- **WHEN** `/p/<slug>/no-such-page/` is requested on a published site
- **THEN** the response is the unavailable 404

#### Scenario: Language and review link travel
- **WHEN** a visitor reading `?lang=es`, or a client on a review link, follows a page link in the menu
- **THEN** the next page opens in Spanish, or still through the review link

### Requirement: The builder edits one page at a time
The builder's outline rail SHALL list the site's pages above the blocks of the selected page, with *Add page*, which SHALL create an untitled page at the end in one click and select it. Pages other than home SHALL be reordered by dragging; the home page SHALL stay first. Selecting a page SHALL show its settings in the side panel — title, address, menu flag and, except for home, *Delete page* — saved by autosave like a block. Deleting a page SHALL ask through the app's confirmation dialog, naming how many blocks go with it, and SHALL delete the page with its blocks, their files and their event registrations. The canvas SHALL show the blocks of the selected page only, named by `?page=<id>` (home when absent); adding, duplicating, reordering and deleting blocks SHALL act within that page. Like the public page, the canvas SHALL show the page menu under the page head when two or more pages are in the menu, with the current page marked; a menu link SHALL open that page in the builder, never the public site. A block's Settings SHALL offer *Move to page*, which SHALL put the block at the end of the chosen page and keep its data. Page writes SHALL go through the sites service. Viewers and a lapsed workspace SHALL see the pages read-only.

#### Scenario: Add a page in one click
- **WHEN** an editor presses *Add page*
- **THEN** a page "Untitled page" with address `untitled-page` exists at the end, the builder shows it selected with an empty canvas, and the menu of the published site lists it after the next save

#### Scenario: Canvas shows the selected page
- **WHEN** an editor opens the builder with `?page=<id of Documents>`
- **THEN** the canvas and the outline list only the Documents page's blocks, and a block added there belongs to Documents

#### Scenario: Canvas shows the page menu
- **WHEN** an editor opens the builder of a site with pages Home, Take part and Documents on Take part
- **THEN** the canvas carries the same page menu as the public page, Take part marked current, and its links lead to `?page=<id>` of the builder

#### Scenario: Reorder pages
- **WHEN** the builder posts a new order of the pages other than home
- **THEN** the pages take that order and home stays first; an order that moves home or names a page of another site is refused

#### Scenario: Delete a page with blocks
- **WHEN** an editor confirms deleting a page with two blocks, one of them an event with registrations
- **THEN** the page, both blocks and the registrations are gone, and the builder shows the home page

#### Scenario: Move a block
- **WHEN** an editor moves a documents block from Home to Documents
- **THEN** the block is the last block of Documents with its files, and Home no longer shows it

#### Scenario: Page settings autosave
- **WHEN** the builder posts a page's new title with `autosave=1`
- **THEN** the answer is JSON with `ok` true and the page's tab label, and a wrong address answers 422 with the field error

#### Scenario: Viewer cannot change pages
- **WHEN** a viewer posts to any page endpoint
- **THEN** the answer is 403 and nothing changes

### Requirement: Pages are translated, screened and listed like the rest of the site
A page title SHALL be a translatable field of the site: a row on the site's Translations tab under the page, keyed `page:<id>:title`, with the same outdated detection, CSV round trip and fallback to the primary text as every other site field, and written only through the sites service. The Translations tab SHALL list occurrences page by page, each page's title before its blocks. Content screening SHALL read page titles and their translations. The sitemap SHALL list every page of a public, published, not held site, and each page SHALL carry `hreflang` alternates for the site's languages. The a11y check for heading order SHALL run per page.

#### Scenario: Translated page title
- **WHEN** a site in English with Spanish offered has the page "Take part" translated as "Participa"
- **THEN** the Spanish menu and page heading read "Participa", and with the translation removed they read "Take part"

#### Scenario: Outdated page title
- **WHEN** the page title is changed after its Spanish translation was written
- **THEN** the Translations tab shows that row as outdated

#### Scenario: Sitemap lists pages
- **WHEN** a public published site has three pages
- **THEN** the sitemap has three entries for it, the home page at `/p/<slug>/`

#### Scenario: Page title is screened
- **WHEN** a live site gets a page titled with a phishing lure that crosses the hold threshold
- **THEN** the site is held for review as for any other site text

### Requirement: Events return to their page
Registering for an event, a refused registration and the cancel page's link back SHALL lead to the page the event block is on, with the block's anchor.

#### Scenario: Register on a page
- **WHEN** a resident registers for an event block on the page Take part
- **THEN** the browser is sent to `/p/<slug>/take-part/?registered=<block>#b-<block>`

## MODIFIED Requirements

### Requirement: The public page serves published sites at /p/<slug>/
`/p/<slug>/` SHALL render a published site's home page and `/p/<slug>/<page-slug>/` its other pages: the hero (title, summary, cover) on the home page and the compact page header elsewhere, the menu, the page's blocks in order, and a footer with the workspace name, the "Made with Mapsurvey" badge unless the workspace holds `unbranded`, and a report link. An unpublished or held site SHALL answer the same 404 page an unknown survey gets, on every page, except to members of the owning workspace, who SHALL see it with a draft banner. An unlisted site SHALL carry `noindex` on every page and SHALL be absent from the sitemap; every page of a public published site SHALL be listed in the sitemap. The page SHALL load no product analytics.

#### Scenario: Draft is private
- **WHEN** an anonymous visitor opens the slug of a draft site, or the address of one of its pages
- **THEN** the response is 404 with the survey-unavailable page

#### Scenario: Member previews a draft
- **WHEN** a member of the owning workspace opens the same URL
- **THEN** the page renders with the banner "Draft — only your workspace sees this"

#### Scenario: Unlisted
- **WHEN** a published unlisted site is requested on any of its pages
- **THEN** the page carries `<meta name="robots" content="noindex">` and the sitemap has no entry for it

#### Scenario: No analytics
- **WHEN** a published site is rendered with a PostHog key configured
- **THEN** the response contains no PostHog snippet

### Requirement: A site can be duplicated
An owner, admin or editor SHALL be able to duplicate a site from the Sites list and from Site settings. The copy SHALL be a new unpublished site titled "<title> (copy)" with a fresh address, the original's settings (language, width, visibility, cover and its description), survey links, pages in order with their titles, addresses, menu flags and translations, and on each page its blocks in order with their headings, menu flags, data, pictures and document files; stored files SHALL be shared, not re-uploaded. Event registrations SHALL never be copied. Survey cards and results blocks of the copy SHALL point at the copy's own survey links. Duplicating SHALL be a Pro use exactly like creating a site.

#### Scenario: Copy for the next engagement
- **WHEN** an editor duplicates a published site with a survey card, an event with registrations and a documents block
- **THEN** a new unpublished site opens in the builder with the same blocks, its survey card on its own link, the same stored file, and no registrations

#### Scenario: Pages are copied
- **WHEN** an editor duplicates a site with pages Home, Take part and Documents, each with blocks and a Spanish page title
- **THEN** the copy has the same three pages with the same addresses, Spanish titles and blocks on the same pages

#### Scenario: Viewer cannot duplicate
- **WHEN** a viewer posts the duplicate action
- **THEN** the answer is 403 and no site is created

#### Scenario: Free workspace refused
- **WHEN** a member of a workspace without Pro and with its trial used duplicates a site
- **THEN** no site is created and the Pro offer is shown

### Requirement: Sites start from templates
The Sites list SHALL offer *From a template* next to *New site* with the Mapsurvey starters (Consultation, Master plan, Municipal site) and the workspace's own templates. A starter SHALL create a draft site whose blocks pass the same validation as any block, with the blocks that need the creator's material added empty; the Consultation and Master plan starters SHALL be one page, and the Municipal site starter SHALL create the pages About (the home page), Take part, Documents and News, each with its starter blocks. *Save as template* SHALL create a copy of a site marked as a template, with its pages, without survey links (its survey cards and results blocks kept, empty) and without event registrations; starting from it SHALL copy its pages and blocks into a new draft. A template SHALL never be published or opened publicly. Starting a site from a starter or a template SHALL count as a Sites use; a template of another workspace SHALL be refused.

#### Scenario: Master plan starter
- **WHEN** an editor picks the Master plan starter
- **THEN** a draft opens with heading, text, map, timeline, survey card, heading, results, documents and contacts blocks, the text and phases filled in

#### Scenario: Municipal site starter
- **WHEN** an editor picks the Municipal site starter
- **THEN** a draft opens with the pages About, Take part, Documents and News in that order, About as the home page at the site's address, and each page holding its starter blocks

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
