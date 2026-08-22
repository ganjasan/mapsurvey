## Why

Survey creators share links via multiple channels (email, social, QR posters) but have no way to attribute responses to specific campaigns. The referrer-based tracking (Phase 2) is automatic but imprecise — it only shows broad categories (google/social/direct). UTM parameters give precise, creator-controlled attribution: "this response came from my March newsletter, not my Instagram post."

## What Changes

- **UTM capture**: Parse `utm_source`, `utm_medium`, `utm_campaign` from survey entry URLs, store in session_start event metadata via Django session forwarding
- **TrackedLink model**: Persist created tracking links in DB (survey FK, source, medium, campaign)
- **Share page**: New top-level editor page at `/editor/surveys/<uuid>/share/` with link creation form, link history table, QR code generation, and copy-to-clipboard
- **Campaign analytics**: Campaign breakdown table on Performance tab showing sessions/completions/rate per UTM triple
- **Navigation**: Share icon in editor navbar alongside Edit and Analytics

## Capabilities

### New Capabilities

- `utm-capture`: Store UTM params in Django session on `survey_header`/`survey_language_select`, consume in `build_session_start_metadata()`. Params forwarded through redirect without modifying URLs.
- `tracked-link-model`: TrackedLink (survey FK, utm_source required, utm_medium optional, utm_campaign optional, created_at). `build_url()` method generates full URL with params.
- `share-page`: Editor page with creation form (PRG pattern), link table with copy/QR buttons, HTMX delete. QR via qrcode.js CDN.
- `campaign-analytics`: `get_campaign_breakdown()` in PerformanceAnalyticsService — groups by (source, medium, campaign) with completion rates.

### Modified Capabilities

- `build_session_start_metadata`: Extended to consume UTM params from session
- `analytics-dashboard`: Passes campaign_breakdown to template
- `analytics-performance-tab`: Campaign Breakdown table appended
- `editor-navigation`: Share icon added to survey_detail and analytics_dashboard navbars

## Impact

- **New files**: `survey/share_views.py`, `survey/templates/editor/survey_share.html`, migration 0022
- **Modified files**: models.py, events.py, views.py, analytics.py, analytics_views.py, urls.py, survey_detail.html, analytics_dashboard.html, analytics_performance.html, tests.py

## Out of Scope

- UTM term and content fields in the UI (captured if present in URL, but no form fields)
- Short URL generation / custom slugs
- QR code customization (colors, logo)
- Link click counting (tracked via session_start events instead)
