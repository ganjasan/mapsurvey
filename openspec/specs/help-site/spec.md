# Help Site Specification

## Purpose

The public help centre at help.mapsurvey.org (Starlight in `help/`): information architecture (Start here, How-to, Reference, Troubleshooting, Learn, Use cases, FAQ), page conventions, search, locale layout, feedback and analytics, deployment as a Render static site, and how the product links into it.
## Requirements
### Requirement: The help site is a Starlight project in `help/`
The repository SHALL contain an Astro + Starlight project in `help/` with its own `package.json`, content in `help/src/content/docs/`, and an authoring guide `help/CONTRIBUTING.md`. `npm ci && npm run build` in `help/` SHALL produce a static site in `help/dist/` with no runtime server and no third-party search service.

#### Scenario: Clean build
- **WHEN** `npm ci && npm run build` runs in `help/` on a clean checkout
- **THEN** it exits 0 and `help/dist/index.html` exists

#### Scenario: Broken internal link fails the build
- **WHEN** a page links to a path that no page in `src/content/docs/` resolves to
- **THEN** the build exits non-zero and names the page and the link

### Requirement: Sections follow Diátaxis
The site SHALL have exactly these top-level sections, each a directory under `src/content/docs/` and a sidebar group: `start-here` (tutorial), `how-to` (task guides), `reference`, `troubleshooting`, `learn` (explanation), `use-cases`, and a single `faq` page. The sidebar SHALL be generated from the directories so adding a page adds a sidebar entry without config changes.

#### Scenario: Sidebar mirrors directories
- **WHEN** a Markdown page is added under `src/content/docs/how-to/`
- **THEN** after a build the How-to group in the sidebar lists it

#### Scenario: No page outside a section
- **WHEN** the content directory is listed
- **THEN** every page is `index.mdx`, `faq.md`, or inside one of the seven section directories

### Requirement: Page shapes per section
Each section SHALL follow its page shape as defined in `help/CONTRIBUTING.md`: how-to pages have an action title in sentence case, a one-line goal, numbered steps with one action each, a "Result" and a "Related" section; troubleshooting pages are titled with the symptom and contain "Why it happens", "What to do" and "If it keeps happening"; reference pages contain descriptions and tables and no procedures; learn pages are explanatory essays that cite their sources and link to the applicable how-to; the FAQ answers are at most three sentences and each links to a full page.

#### Scenario: How-to page
- **WHEN** a reviewer opens any page under `how-to/`
- **THEN** its title starts with a verb, the steps are a numbered list, and "Result" and "Related" headings are present

#### Scenario: Troubleshooting page
- **WHEN** a reviewer opens any page under `troubleshooting/`
- **THEN** the title names the symptom as shown in the product and the three headings are present

#### Scenario: FAQ entry
- **WHEN** a reviewer opens `/faq/`
- **THEN** every answer is at most three sentences and contains a link to a page on the site

### Requirement: FAQ questions come from real sources
The FAQ SHALL contain only questions that were asked through a support channel (tawk.to history, Chatwoot, email, demo requests) or that already appear on a landing FAQ; each entry SHALL record its source in a Markdown comment. Questions SHALL be grouped under headings (Getting started, Surveys & questions, Maps & layers, Responses & export, Sharing & embedding, Account & Pro, Self-hosting), the page SHALL open with jump links to every question, and questions SHALL NOT be hidden in accordions on desktop widths.

#### Scenario: Entry carries a source
- **WHEN** a reviewer reads the FAQ source file
- **THEN** every question is preceded by a comment naming where it was asked

#### Scenario: Jump links
- **WHEN** a visitor opens `/faq/`
- **THEN** the top of the page lists every question as an in-page link and each question heading has an anchor

### Requirement: Stable slugs and redirects
Page slugs SHALL be treated as identifiers: product links and troubleshooting references use them. Renaming or moving a page SHALL add a redirect from the old path in `astro.config.mjs` so the old URL keeps resolving.

#### Scenario: Renamed page keeps its old URL
- **WHEN** a page's slug is changed and a redirect is declared
- **THEN** requesting the old URL on the built site returns the new page (meta refresh or 301 via Render redirect)

### Requirement: Search is built at deploy time
The site SHALL provide full-text search over all pages using Pagefind, indexed during the build, served as static files, with no external service.

#### Scenario: Search finds a page by its body text
- **WHEN** a visitor types a phrase that occurs only in a how-to page body
- **THEN** the results list that page

### Requirement: Root locale and locale layout
English SHALL be the root locale served without a path prefix. Additional locales SHALL be added as `locales.<code>` in the Starlight config plus a `src/content/docs/<code>/` folder; pages missing in a locale SHALL fall back to English with the untranslated notice. Every page SHALL carry a canonical URL and, when more than one locale exists, `hreflang` alternates between locale versions.

#### Scenario: English at the root
- **WHEN** the site is built with only the root locale
- **THEN** `/how-to/<slug>/` resolves and `/en/how-to/<slug>/` does not

#### Scenario: Missing translation falls back
- **WHEN** a locale is configured and a page has no translation in it
- **THEN** the locale URL serves the English content with the fallback notice

### Requirement: Feedback and contact on every content page
Every content page SHALL end with a "Was this helpful?" control (yes/no; a "no" reveals an optional one-line text field) and a "Still stuck?" block that links to support. When PostHog is configured the control SHALL send `help_feedback` with `path`, `helpful` and the optional text; search input SHALL send `help_search` with the settled query once per query. When PostHog is not configured no analytics script SHALL load and the feedback control SHALL still render but send nothing.

#### Scenario: Thumbs down with a note
- **WHEN** a visitor clicks "No" and submits a note
- **THEN** one `help_feedback` event with `helpful: false` and the note is captured and a thank-you line replaces the control

#### Scenario: Analytics unset
- **WHEN** the site is built without `PUBLIC_POSTHOG_KEY`
- **THEN** no request to a PostHog host is made on any page

#### Scenario: Contact block
- **WHEN** a visitor reaches the end of any content page
- **THEN** a "Still stuck?" link to support is present

### Requirement: Indexing and crawl control
Production builds SHALL emit `robots.txt` allowing all crawlers and pointing to the sitemap, and a sitemap listing every page. Preview builds (Render sets `IS_PULL_REQUEST=true`) SHALL emit `<meta name="robots" content="noindex">` on every page.

#### Scenario: Production is indexable
- **WHEN** the site is built without `IS_PULL_REQUEST`
- **THEN** `dist/robots.txt` allows all and references `sitemap-index.xml`, and no page carries a `noindex` meta tag

#### Scenario: Preview is not indexable
- **WHEN** the site is built with `IS_PULL_REQUEST=true`
- **THEN** every page carries the `noindex` meta tag

### Requirement: Theme matches Mapsurvey
The site SHALL use Mapsurvey's palette and type from the landing pages through `customCss`, and SHALL override the header (logo linking to mapsurvey.org and an "Open Mapsurvey" action), the footer (feedback and contact block) and the landing hero (search first, one card per section). No React runtime SHALL be shipped.

#### Scenario: Landing page
- **WHEN** a visitor opens `/`
- **THEN** the page shows a search box above six section cards and a "popular pages" list

### Requirement: Product links resolve to existing pages
The Django project SHALL define `HELP_SITE_URL` (default `https://help.mapsurvey.org`, empty disables help links) and a registry `survey/help_links.py` mapping keys to help-site paths; templates SHALL build help links only from the registry through the `HELP_URL` context variable. A test SHALL assert that every registry path corresponds to a page file under `help/src/content/docs/`. With the MCP server live, the registry SHALL carry `mcp` (`how-to/use-the-mcp-server/`), `mcp_tools` (`reference/mcp-tools/`) and `connected_apps` (`how-to/connect-an-app/`), and those three pages SHALL NOT be `draft: true`; `reference/mcp-tools.md` SHALL be generated from the tool registry by `scripts/build_mcp_reference.py`.

#### Scenario: Registry path exists
- **WHEN** the test suite runs
- **THEN** for every key in `HELP_LINKS` a file `help/src/content/docs/<path>.md|.mdx` or `<path>/index.md|.mdx` exists

#### Scenario: Help links disabled
- **WHEN** `HELP_SITE_URL` is empty
- **THEN** templates render no help-site links and the help menu omits "Help centre"

#### Scenario: Learn more link
- **WHEN** a signed-in creator opens the reference-layers panel in the editor
- **THEN** a "Learn more" link points to `HELP_SITE_URL` + the registry path for reference layers and opens in a new tab

#### Scenario: MCP pages are published
- **WHEN** the help site is built
- **THEN** `/how-to/use-the-mcp-server/`, `/reference/mcp-tools/` and `/how-to/connect-an-app/` are in the build (no `draft: true`) and the connections page links to the first two through `HELP_URL`

### Requirement: Support hand-off from the help site
The main site SHALL open the support chat when a page is requested with `?support=1` by a signed-in creator and the chat is configured; otherwise the parameter SHALL be ignored.

#### Scenario: Signed-in with chat configured
- **WHEN** a signed-in creator opens `/?support=1` and `CHATWOOT_WEBSITE_TOKEN` is set
- **THEN** the Chatwoot widget opens on load

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor opens `/?support=1`
- **THEN** the page renders as usual and the widget does not open

### Requirement: Launch gate before the product links to the site
The help menu change SHALL NOT be merged before the help site is live on `help.mapsurvey.org` with at least: the Start here tutorial, eight how-to pages, reference pages for question types and exports, a seeded FAQ, and three Learn pages.

#### Scenario: Gate checked at review
- **WHEN** the Django PR that changes the help menu is reviewed
- **THEN** its description lists the live URLs of the pages above

### Requirement: Assistant set-up guides follow the agent page
`how-to/use-the-mcp-server.md` SHALL give, per client offered on the agent page
(`agent-connect-page`), the same path the page gives, under a heading per client, with Claude and
ChatGPT first. Claude Desktop SHALL be covered by the Claude connector (one connector serves web,
desktop and phone) and the page SHALL NOT tell readers to put a remote `url` into
`claude_desktop_config.json`. ChatGPT SHALL be described through its current custom-server flow,
with the plans that can add a server. `how-to/connect-an-app.md` SHALL link to those sections
rather than repeat them. `how-to/choose-how-to-start.md` SHALL describe *Use your AI assistant* as
the third way to start. Product links SHALL reach these pages through the `HELP_URL` registry.

#### Scenario: No Desktop config with a URL
- **WHEN** the help site is built
- **THEN** no page under `help/src/content/docs/` contains a `claude_desktop_config.json` example with a `"url"` key

#### Scenario: Every page client has a section
- **WHEN** the test suite runs
- **THEN** every client slug in the agent page registry with a help anchor resolves to a heading in `how-to/use-the-mcp-server.md`

#### Scenario: Third way to start
- **WHEN** a reader opens `/how-to/choose-how-to-start/`
- **THEN** it describes *Use your AI assistant* and links to the MCP guide

