## Context

The platform has 4 separate base templates (`base_survey_template.html`, `base.html`, `base_landing.html`, `editor/editor_base.html`). Yandex Metrica is hardcoded (counter ID 53686546) only in `base_survey_template.html` — covering just survey section pages. Landing, editor, auth, and thanks pages have zero analytics. The counter ID is not configurable.

The established pattern for site-wide configuration: environment variable → `settings.py` → context processor → template variable (used by Mapbox tokens, contact info).

## Goals / Non-Goals

**Goals:**
- Plausible Analytics script on all pages, configurable via environment variables
- Remove hardcoded Yandex Metrica
- Track survey funnel events: start, section complete, survey complete
- Zero analytics output when not configured (safe for dev/test)

**Non-Goals:**
- Server-side event tracking (e.g., via Plausible API) — client-side only
- Per-survey analytics dashboards or in-app analytics display
- Yandex Metrica as a configurable option (removed entirely)
- Session replay or heatmaps (Plausible doesn't support these)

## Decisions

### 1. Single template partial with `{% include %}`

Include `partials/_analytics.html` in all 4 base templates' `<head>` sections. The partial renders nothing when `PLAUSIBLE_DOMAIN` is empty.

**Why over per-template inline code**: DRY — one file to change if the script tag format changes. All 4 base templates are independent (no shared ancestor), so a partial is the cleanest way to share.

**Why over Django template tag**: A simple `{% include %}` is sufficient. A custom template tag would be over-engineering for a single `<script>` element.

### 2. Context processor (not direct `settings` access in templates)

New `analytics()` context processor exposes `PLAUSIBLE_DOMAIN` and `PLAUSIBLE_SCRIPT_URL`.

**Why over `{% load settings %}` or `django.conf.settings` in templates**: Follows the established codebase pattern (mapbox, contact processors). Templates don't import settings directly anywhere in this project.

### 3. Client-side custom events via Plausible JS API

Fire `plausible('event_name', {props: {...}})` from inline `<script>` tags in survey templates.

- `survey_start`: fires on page load of the first section (detected by `section_current == 1`)
- `survey_section_complete`: fires on form submit via `addEventListener('submit', ...)`
- `survey_complete`: fires on page load of thanks page

**Why form submit listener for `survey_section_complete`**: POST always redirects (no template rendered after save). The `submit` event fires before navigation, and Plausible uses `navigator.sendBeacon()` internally which survives page unload.

**Why not server-side events**: Would require adding `requests` dependency and async HTTP calls in views. Client-side is simpler, matches Plausible's design, and the data (pageviews + funnel) doesn't need 100% accuracy.

### 4. `PLAUSIBLE_SCRIPT_URL` for self-hosted support

Default: `https://plausible.io/js/script.js`. Override for self-hosted Plausible instances.

**Why a separate env var**: The script URL differs between cloud and self-hosted. Hardcoding the cloud URL would break self-hosted setups.

## Risks / Trade-offs

- **Ad-blockers block Plausible** → Accepted. This is inherent to all client-side analytics. Data will undercount by ~15-30%. Mitigation: can use a proxied script URL via `PLAUSIBLE_SCRIPT_URL` if needed.
- **`defer` script timing** → The Plausible script loads with `defer`. Custom event scripts in `{% block section_scripts %}` run after DOM parse, so `plausible()` function is available. Guard with `typeof plausible !== 'undefined'` for ad-blocker edge cases.
- **No rollback needed** → Feature is purely additive (env var controlled). Unsetting `PLAUSIBLE_DOMAIN` disables everything. Yandex Metrica removal is intentional and non-reversible.
