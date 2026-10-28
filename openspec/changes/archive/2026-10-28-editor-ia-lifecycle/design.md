## Context

The survey-management surface accreted five top-level tabs of three different ranks plus a scattered set of publish/visibility controls. The UX review picked "Variant A (lifecycle)". The guiding constraint here: **change presentation, not routes or data model** — so the whole change is template/CSS plus one thin endpoint, and every existing test/link keeps working.

## Goals

- Three lifecycle spaces (Build / Results / Publish) reading as peers of equal rank.
- Actions (Share, Preview) and properties (Settings) visibly demoted out of the space row.
- One place that answers "who can see / do what with this survey and its results" (the Publishing widget).
- Results adopts the same sidebar shell as Build and Publish.

## Non-Goals

- No rename of URLs or view functions (`editor_survey_detail`/`_analytics`/`_public_results`/`_share` stay).
- No change to the lifecycle state machine (`VALID_TRANSITIONS`), versioning, or the `visibility`/`status`/`is_published` fields.
- Onboarding (first-run, checklist, tour) — prototyped in the mockup but deferred.

## Decisions

### D1: Labels + chrome only; routes frozen
Editor→**Build**, Analytics→**Results**, Public results→**Publish** are label changes on the same `<a href="{% url ... %}">`. `active_tab` keys are also renamed (`editor`→`build`, `analytics`→`results`, `public_results`→`publish`) but that's an internal template token; the three templates that pass it are updated together. This keeps `reverse()`, deep links, and the ~30 tests that hit these URLs untouched.

### D2: Share stays a page, reached via a dropdown
The Share page owns tracking-link CRUD — rebuilding it as a popover would be churn. `Share ▾` is a lightweight menu: *Copy survey link*, *QR code* (reuses existing survey QR affordance), *Tracking links…* (→ existing Share page), and, when a results page is live, *Copy results link*. Menu items that copy use inline JS + `navigator.clipboard`; "Tracking links…" navigates to `editor_survey_share`.

### D3: Preview is a dropdown over both objects
`Preview ▾`: *Survey — as respondent* (existing `survey` public URL, new tab) and *Results page* (the editor preview endpoint `editor_public_results_preview`, which always renders regardless of publish state — avoids a 404 on an unpublished `/r/<slug>/`).

### D4: Publishing widget = presentation over three existing axes
The status chip dropdown groups, top to bottom:
- **Collection** — the current status-transition actions (reuses `doTransition`/`showPublishConfirm` and `editor_survey_transition`). The chip label reads Open (published) / Closed / Draft / Testing / Archived — mapping straight onto `status`. No new states.
- **Discovery** — "Listed in public gallery" toggle ↔ `visibility` (`public` on / `private` off; `demo` shown as on, left intact). New endpoint `editor_survey_visibility` (POST, owner) writes only this field.
- **Results page** — reads `survey.public_results_page` (reverse OneToOne, silent-fail in templates when absent): shows Live/Draft + `/r/<slug>/`, with a jump to the Publish space.
- **Version** — existing version number + draft actions (`Create draft`, draft Publish/Discard) for draft copies.

Because the widget must appear on all three spaces, its markup moves to `_publishing_widget.html` and the lifecycle JS + modals move from `survey_detail.html` into `_lifecycle_scripts.html`, both included by all three space templates. `survey.public_results_page` is accessed defensively (ObjectDoesNotExist is `silent_variable_failure` in templates), so no extra view context is required.

### D5: Results sidebar
`analytics_dashboard.html` currently nests `Data | Performance` over `Table | Map | Charts`. Flatten to a single sidebar: **Table / Map / Charts / Performance**, plus a **Download data** control in the sidebar footer (the dashboard overflow menu keeps export/backup, but primary "download responses" now lives with the data). Internal HTMX/JS and the analytics URLs are unchanged — only the tab shell around them is replaced by the sidebar shell already used in Build/Publish.

### D6: Dashboard cards
Card actions become Build / Results / Publish / Share / More (overflow). The standalone Settings link is dropped (Settings is now the ⚙ inside Build). Perma-BETA badges removed. A "Results live" chip mirrors `public_results_page.is_published`.

## Risks / Trade-offs

- **Largest surface: the analytics restructure (D5)** — the analytics screen has the most JS/HTMX. Mitigation: keep every analytics endpoint and its inner partials; only swap the outer tab bar for the sidebar; verify Table/Map/Charts/Performance switching in the browser against real data.
- **Shared lifecycle JS** — moving `doTransition` et al. out of `survey_detail.html` into a shared include risks double-definition if a template still defines them. Mitigation: define once in `_lifecycle_scripts.html`, remove from `survey_detail.html`, include in all three.
- **Widget on non-owner / draft-copy surveys** — the widget degrades: non-owners see a static chip; draft copies show the "Draft of X" + Publish Version/Discard affordances (kept in Build).

## Migration Plan

Pure template/CSS + one additive endpoint/URL. No data migration. Ship behind no flag; revertable by restoring the old `_survey_nav_tabs.html` and `survey_detail.html` navbar.
