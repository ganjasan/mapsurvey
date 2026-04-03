## Context

Phase 2 event tracking is live: SurveyEvent model captures session_start (with referrer, user agent, device info), section_view, section_submit, survey_complete, page_load, page_leave. Performance tab shows funnel, traffic sources, device breakdown, completion by referrer, time on section.

UTM parameters are the standard way to attribute traffic to specific campaigns. They travel in the URL query string (`?utm_source=newsletter&utm_medium=email&utm_campaign=spring2026`).

Problem: `survey_header` view redirects to the first section, discarding query string params. UTM params must survive this redirect.

## Goals / Non-Goals

**Goals:**
- Capture UTM params from survey URLs and store in session_start event metadata
- Provide a Share page for creating and managing tracked links
- Show campaign breakdown in analytics
- QR code generation for printed materials

**Non-Goals:**
- Short URLs / vanity slugs
- Link click counting (use session_start events)
- UTM term/content form fields (captured silently if present)

## Decisions

### 1. UTM forwarding via Django session (not query string)
**Choice**: Store UTM params in `request.session['utm_params']` during `survey_header`, consume in `build_session_start_metadata()` during `survey_section`.
**Why**: `survey_header` builds redirect URLs via string concatenation. Appending query params to relative URLs is fragile. The session is already used for `survey_session_id` and `survey_language` — consistent pattern.

### 2. TrackedLink model in DB
**Choice**: Persist links as TrackedLink rows (survey FK, utm_source, utm_medium, utm_campaign, created_at).
**Why**: User requested link history. Enables future features (link-level analytics, deactivation).

### 3. Share as top-level editor page
**Choice**: `/editor/surveys/<uuid>/share/` — same level as Edit and Analytics, own template extending editor_base.html.
**Why**: User clarified Share is a peer page, not a tab or modal.

### 4. QR via client-side qrcode.js
**Choice**: CDN-loaded qrcode.js, render into modal on click.
**Why**: No server dependency, no image storage. QR is ephemeral — rendered from the URL string.

### 5. Campaign analytics on Performance tab
**Choice**: Additional table after Traffic Sources, not a separate tab.
**Why**: User chose this. Keeps analytics focused on one page.

### 6. @survey_permission_required('editor') for Share page
**Choice**: Editor role minimum for creating/deleting links.
**Why**: Viewers should see analytics but not create tracking links.

## Component Interaction

```
Editor creates link on Share page
  → POST /editor/surveys/<uuid>/share/
  → TrackedLink.objects.create(survey, source, medium, campaign)
  → Redirect back (PRG)
  → Template renders link.build_url(request) for each row

Respondent visits tracked URL
  → GET /surveys/<slug>/?utm_source=newsletter&utm_campaign=spring
  → survey_header view
      → store_utm_in_session(request)  [saves to session]
      → redirect to first section

  → GET /surveys/<slug>/<section>/
  → survey_section view (new session)
      → build_session_start_metadata(request)
          → consume_utm_from_session(request)  [pops from session]
      → emit_event('session_start', metadata={..., utm_source, utm_campaign})

Editor views analytics
  → Performance tab
  → PerformanceAnalyticsService.get_campaign_breakdown()
  → Groups session_start events by (utm_source, utm_medium, utm_campaign)
  → Table: source | medium | campaign | started | completed | rate
```
