## ADDED Requirements

### Requirement: A landing is a workspace-owned public page
The system SHALL provide `Landing`, owned by one `Organization`, with a title, a plain-text summary, an optional cover picture on the public media tier under a random key, a unique slug, a page language, a visibility (`public` or `unlisted`) and a published flag. Members with the owner, admin or editor role of that workspace SHALL create, edit, publish, unpublish and delete its landings; viewers SHALL see the builder read-only; anyone else SHALL get 404 for a landing's builder URL, whatever their active workspace.

#### Scenario: Editor creates a landing
- **WHEN** an editor of a Pro workspace posts a title "Riverside Park plan" to create a landing
- **THEN** a draft landing exists in that workspace with slug `riverside-park-plan` and the browser is sent to its builder

#### Scenario: Viewer cannot change a landing
- **WHEN** a viewer posts to any builder endpoint of a landing of their workspace
- **THEN** the response is 403 and nothing changes

#### Scenario: Another workspace's landing is invisible
- **WHEN** a member of workspace A opens the builder URL of a landing of workspace B
- **THEN** the response is 404

#### Scenario: Slug rules
- **WHEN** settings are saved with slug `Edit`, `ab`, or a slug another landing has
- **THEN** the save is refused with a field error and the landing keeps its slug

### Requirement: Surveys are linked to landings many-to-many
A landing SHALL link any number of canonical surveys of its own workspace (the page shows them where the creator puts their survey cards), and a survey SHALL be linkable to any number of landings. Linking a draft copy or an archived version SHALL link its canonical survey. A survey of another workspace, an archived or a trashed survey SHALL NOT be linkable. Unlinking a survey SHALL remove the survey cards that show it.

#### Scenario: One survey on two landings
- **WHEN** an editor links survey S to landing L1 and to landing L2
- **THEN** both landings list S and each can show a card for it

#### Scenario: Foreign survey refused
- **WHEN** a link request names a survey of another workspace
- **THEN** the response is 404 and nothing is linked

#### Scenario: Unlinking removes cards
- **WHEN** an editor unlinks survey S from a landing that has a card for S
- **THEN** the card is deleted with the link

### Requirement: Blocks are a closed set validated by one function
A landing SHALL hold an ordered list of blocks of the kinds `text`, `image`, `button`, `video`, `faq`, `timeline` and `survey`, each with an optional title. Every write of a block SHALL pass `landings.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same landing. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another landing SHALL be refused.

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

### Requirement: A survey card shows the survey's current state
A survey card SHALL be drawn from the linked survey at request time: a published survey within its period SHALL show "open" and a link to the survey; a published survey before `opens_at` SHALL show the opening date and no link; a closed survey or one past `closes_at` SHALL show "closed" and, when the survey has a published public results page, a link to it; a draft or testing survey SHALL show "coming soon" and no link; an archived, trashed or held survey SHALL not be drawn on the public page.

#### Scenario: Open survey
- **WHEN** a landing shows a card for a published survey with no period
- **THEN** the card carries the survey's public URL and the "Take part" label (or the creator's label)

#### Scenario: Closed survey with results
- **WHEN** the linked survey is closed and its public results page is published
- **THEN** the card shows "Closed" and links to `/r/<slug>/`

#### Scenario: Draft survey
- **WHEN** the linked survey is a draft
- **THEN** the card shows "Coming soon" and no link

### Requirement: The public page serves published landings at /p/<slug>/
`/p/<slug>/` SHALL render a published landing: the hero (title, summary, cover), an anchor navigation listing the titled blocks, the blocks in order, and a footer with the workspace name, the "Made with Mapsurvey" badge unless the workspace holds `unbranded`, and a report link. An unpublished or held landing SHALL answer the same 404 page an unknown survey gets, except to members of the owning workspace, who SHALL see it with a draft banner. An unlisted landing SHALL carry `noindex` and SHALL be absent from the sitemap; a public published landing SHALL be listed in the sitemap. The page SHALL load no product analytics.

#### Scenario: Draft is private
- **WHEN** an anonymous visitor opens the slug of a draft landing
- **THEN** the response is 404 with the survey-unavailable page

#### Scenario: Member previews a draft
- **WHEN** a member of the owning workspace opens the same URL
- **THEN** the page renders with the banner "Draft — only your workspace sees this"

#### Scenario: Unlisted
- **WHEN** a published unlisted landing is requested
- **THEN** the page carries `<meta name="robots" content="noindex">` and the sitemap has no entry for it

#### Scenario: No analytics
- **WHEN** a published landing is rendered with a PostHog key configured
- **THEN** the response contains no PostHog snippet

### Requirement: Landings are a Pro feature that survives a lapse
Creating, editing and publishing a landing SHALL need the `landing_pages` feature (Pro plan, or a Pro trial with its allowance of one landing created); refused requests SHALL get the feature-required page with status 403. Creating a landing SHALL count one trial use. Unpublishing SHALL always be allowed. A landing published while the workspace held the feature SHALL stay online after the subscription lapses; its builder SHALL open read-only with an upgrade banner.

#### Scenario: Free workspace refused
- **WHEN** an editor of a Free workspace whose trial is used elsewhere posts to create a landing
- **THEN** the response is 403 with the feature-required page and no landing exists

#### Scenario: Lapsed workspace keeps its page
- **WHEN** a landing was published under Pro and the subscription has ended
- **THEN** `/p/<slug>/` still renders it, a builder save is refused with 403 and unpublish succeeds

### Requirement: Landing text is screened like survey text
Publishing a landing, and saving any part of a published landing, SHALL run content screening over the landing's title, summary, block titles, text, FAQ, phases, captions, button labels and links. A score at or above the hold threshold SHALL open a pending `ContentReview` for the landing and mail the moderator; while it is pending the public page SHALL answer the 404 page to everyone outside the workspace. Screening SHALL fail open. A visitor SHALL be able to report a landing at `/p/<slug>/report/` with the same reasons and rate limit as a survey report; a report SHALL hold nothing.

#### Scenario: Lure landing held
- **WHEN** a landing whose text scores above the threshold is published
- **THEN** a pending review names the landing, the moderator is mailed and an anonymous request to `/p/<slug>/` gets 404

#### Scenario: Report
- **WHEN** a visitor reports a published landing as phishing
- **THEN** a `reported` review names the landing, the moderator is mailed and the page keeps serving
