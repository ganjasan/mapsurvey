## ADDED Requirements

### Requirement: Shared preview links resolve to the public results page
The editor preview URL `/editor/surveys/<uuid>/public-results/preview/` SHALL render only for users with the `editor` role on that survey. When the requester lacks that role and the survey has a `PublicResultsPage` with `is_published=True`, the system SHALL redirect to that page's public URL `/r/<slug>/` instead of denying the request. This SHALL apply whether the requester is anonymous or signed in to a different organization. The redirect SHALL be evaluated by reading the existing page only: the system SHALL NOT create a `PublicResultsPage` while serving a request from a user who lacks the `editor` role. The page's `visibility` SHALL NOT affect the redirect, because an `unlisted` page is one the creator handed out by link and `/r/<slug>/` already serves it.

#### Scenario: Anonymous visitor follows a shared preview link
- **WHEN** an anonymous visitor requests the preview URL of a survey whose results page is published
- **THEN** the system responds with a redirect to `/r/<slug>/` and does not send the visitor to the login page

#### Scenario: Signed-in visitor from another organization
- **WHEN** a user who is authenticated but has no role on the survey requests its preview URL, and the survey's results page is published
- **THEN** the system responds with a redirect to `/r/<slug>/` rather than `404`

#### Scenario: Unlisted page still redirects
- **WHEN** an anonymous visitor requests the preview URL of a survey whose results page is published with `visibility="unlisted"`
- **THEN** the system redirects to `/r/<slug>/`

#### Scenario: No page row is created for a non-editor
- **WHEN** an anonymous visitor requests the preview URL of a survey that has no `PublicResultsPage` row at all
- **THEN** no `PublicResultsPage` is created by that request

### Requirement: Denial is preserved where there is no public destination
The redirect SHALL exist only where a published results page can receive the visitor. Where none exists, the system SHALL deny the request exactly as it did before this capability: an anonymous requester SHALL be redirected to the login page, and any other requester without the `editor` role SHALL receive `404`. Surveys that are trashed (`deleted_at` set) SHALL NOT be reachable through the preview URL under any circumstances, including when a published results page exists.

#### Scenario: Results page exists but is not published
- **WHEN** an authenticated user with no role on the survey requests its preview URL and the results page has `is_published=False`
- **THEN** the system responds with `404`

#### Scenario: Anonymous visitor, unpublished results page
- **WHEN** an anonymous visitor requests the preview URL of a survey whose results page is not published
- **THEN** the system redirects to the login page

#### Scenario: Trashed survey never redirects
- **WHEN** a request is made for the preview URL of a survey with `deleted_at` set, whose results page is published
- **THEN** the system does not redirect to `/r/<slug>/`

#### Scenario: Unknown survey UUID
- **WHEN** an authenticated user requests the preview URL for a UUID that matches no survey
- **THEN** the system responds with `404`

### Requirement: Editors still see the preview
Removing the blanket permission decorator from the preview view SHALL NOT change what an editor or owner sees. The preview SHALL continue to render for authorised users regardless of the results page's publish state, and SHALL continue to be embeddable in the editor's same-origin iframe.

#### Scenario: Owner loads the preview directly
- **WHEN** the survey's owner requests the preview URL
- **THEN** the system responds `200` and renders the public results template with `preview` set

#### Scenario: Owner previews an unpublished page
- **WHEN** the survey's owner requests the preview URL while the results page has `is_published=False`
- **THEN** the system responds `200` and renders the preview, without redirecting

#### Scenario: Preview remains iframe-embeddable
- **WHEN** the survey's owner loads the preview
- **THEN** the response permits same-origin framing

### Requirement: Fallback is disableable without a deploy
The redirect behaviour SHALL be gated by the setting `PUBLIC_RESULTS_PREVIEW_FALLBACK`, defaulting to enabled. When disabled, the preview URL SHALL deny non-editors exactly as it did before this change.

#### Scenario: Fallback switched off
- **WHEN** `PUBLIC_RESULTS_PREVIEW_FALLBACK` is `False` and an anonymous visitor requests the preview URL of a survey with a published results page
- **THEN** the system redirects to the login page instead of `/r/<slug>/`

### Requirement: A 404 on a survey URL explains why
When a request for a survey-facing URL results in `404` — the survey does not exist, was deleted, or its results page is not published so the denial branch above ends in `404` — the system SHALL render a branded page that names the likely causes (the survey is not published yet, was removed, or the link is wrong) rather than the default server 404. The page SHALL offer a way forward: a link to the public survey list and, for a signed-in user, a link to their dashboard. Survey-facing URLs are those under `/surveys/`, `/r/`, and `/editor/surveys/`. A `404` on any other path SHALL render the same branded template with generic copy, never survey-specific text.

#### Scenario: 404 on a survey path shows survey guidance
- **WHEN** a visitor requests `/r/<slug>/` for a slug that matches no published results page
- **THEN** the response status is `404` and the body explains that the survey may be unpublished, deleted, or that the link is wrong

#### Scenario: 404 on the preview denial path shows survey guidance
- **WHEN** a signed-in user with no role on a survey requests its preview URL and the results page is not published
- **THEN** the `404` response body explains the likely causes rather than showing a bare server error

#### Scenario: 404 on a non-survey path stays generic
- **WHEN** a visitor requests a non-survey path that does not exist
- **THEN** the branded 404 renders without survey-specific wording

### Requirement: The editor offers the public link directly
The survey editor SHALL present a control that copies the public results URL `/r/<slug>/` to the clipboard, so that copying the editor URL from the address bar is not the most convenient way to share results. The control SHALL appear only while the results page is published, and the existing "Preview" control SHALL be labelled so that it does not read as the shareable link.

#### Scenario: Copy control on a published page
- **WHEN** an editor opens the public-results configuration tab for a survey whose page is published
- **THEN** the page offers a control that copies the `/r/<slug>/` URL

#### Scenario: No copy control before publishing
- **WHEN** an editor opens the configuration tab while the results page is not published
- **THEN** no copy-public-link control is offered

### Requirement: Editor workspace tabs have non-colliding labels
The three editor workspace tabs SHALL be labelled so that no two share a word and none collides with a survey lifecycle action. The tab for building the survey SHALL read "Survey" (not "Build"), the tab for responses and analysis SHALL read "Responses" (not "Results"), and the tab for the shareable public page SHALL read "Public results" (not "Publish"). The internal `active_tab` codes (`build`/`results`/`publish`) are implementation detail and MAY remain unchanged.

#### Scenario: Tabs read Survey / Responses / Public results
- **WHEN** an editor views the survey navigation tabs
- **THEN** the tabs read "Survey", "Responses", and "Public results"

#### Scenario: The old colliding labels are gone
- **WHEN** an editor views the survey navigation tabs
- **THEN** no tab reads "Build", "Results", or a bare "Publish", so "Responses" and "Public results" are no longer confusable and "Publish" no longer overlaps the survey's "Publish — open for responses" action
