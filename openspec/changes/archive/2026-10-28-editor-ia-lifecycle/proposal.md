## Why

A UX review (see `docs/ux-review-2026-07/`) found the survey-management IA mixes three ranks of object in one tab row: workspaces (`Editor`, `Analytics`, `Public results`), an action (`Share`), and object properties (`Settings`). The word "Editor" collides with the `/editor/` app prefix, and "published/public" is overloaded across three independent axes (survey status, survey visibility, results-page publish state). As entities accumulated (lifecycle, versioning, public results, tracking links), the hierarchy stopped reading cleanly.

Variant A of the review ("lifecycle") was chosen and prototyped in `docs/ux-review-2026-07/ia-variant-a.mockup.html`. This change implements it (onboarding parts of the mockup are deferred).

## What Changes

- **Three spaces, not five tabs.** The tab row becomes `Build · Results · Publish` (was Editor / Analytics / Public results). Labels only — routes and view names are unchanged (`editor_survey_detail`, `editor_survey_analytics`, `editor_survey_public_results`).
- **Actions leave the tab row.** `Share` and `Preview` become dropdown **actions** in the navbar, each aware of both shareable objects (the survey and the results page). `Settings` becomes a ⚙ button opening the existing in-Build settings panel (`?panel=settings`); the deprecated Settings tab is removed.
- **Unified Publishing widget.** The status chip (`Open · v2`) opens one dropdown grouping the previously-scattered publish controls: Collection (status transitions), Discovery (survey gallery visibility), Results page (live state + link), Version (draft/version actions). This is a **presentation layer over existing fields** — no data-model or state-machine changes; it re-labels the overloaded "published/public" vocabulary as Open/Closed · Listed · Results live. The widget is shared across all three spaces.
- **Analytics becomes the Results space.** The tab is relabeled Results and gets a direct "Download data" action. Its Data workspace is a split-pane IDE (Table/Map/Charts shown simultaneously in resizable panes — the Data Management epic), so it is preserved rather than flattened into a mutually-exclusive sidebar (which the mockup drew without accounting for split-panes); Data/Performance remain internal sub-navigation of Results. A fully unified Results sidebar that keeps split-pane power is deferred.
- **Dashboard cards match.** Card quick-actions become Build / Results / Publish / Share / More; the Settings link and the perma-BETA badges are removed; Public results (as Publish) is now represented.

## Capabilities

### Modified Capabilities
- `survey-editor`: navigation restructured into three lifecycle spaces with action dropdowns and a unified publishing widget; a small visibility-toggle endpoint is added for the widget. No change to survey/section/question CRUD or the editor's data model.

## Impact

- **Templates**: `editor/partials/_survey_nav_tabs.html` (rewritten into the workspace nav), new `editor/partials/_publishing_widget.html` and `editor/partials/_lifecycle_scripts.html` (extracted from `survey_detail.html`), `survey_detail.html`, `analytics_dashboard.html` (nav + sidebar restructure), `public_results.html` (nav), `editor.html` (cards), `editor_base.html` (nav/dropdown CSS).
- **Views/URLs**: new `editor_survey_visibility` (POST, owner) to toggle gallery visibility from the widget. All existing routes/view names unchanged — keeps every current link, bookmark, and test working.
- **No data migrations.** Publishing widget is presentation over `SurveyHeader.status`, `SurveyHeader.visibility`, and `PublicResultsPage.is_published`.
