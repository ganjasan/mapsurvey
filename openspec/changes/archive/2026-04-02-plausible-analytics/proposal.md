## Why

The platform has hardcoded Yandex Metrica (counter 53686546) only on survey section pages. The landing page, editor, thanks page, and auth pages have no analytics. The counter ID is not configurable via environment variables. We need privacy-friendly, configurable analytics across all pages with survey funnel event tracking to understand user behavior.

## What Changes

- **Remove** hardcoded Yandex Metrica script from `base_survey_template.html`
- **Add** Plausible Analytics integration configurable via environment variables (`PLAUSIBLE_DOMAIN`, `PLAUSIBLE_SCRIPT_URL`)
- **Add** analytics context processor to inject config into all templates
- **Add** shared template partial (`partials/_analytics.html`) included in all 4 base templates
- **Add** custom Plausible events for survey funnel: `survey_start`, `survey_section_complete`, `survey_complete`
- **No analytics rendered** when `PLAUSIBLE_DOMAIN` is unset (safe default for development)

## Capabilities

### New Capabilities
- `plausible-analytics`: Configurable Plausible Analytics integration with pageview tracking on all pages and custom survey funnel events

### Modified Capabilities
_(none — this is a new cross-cutting capability, no existing spec requirements change)_

## Impact

- **Templates**: All 4 base templates modified to include analytics partial (`base_survey_template.html`, `base.html`, `base_landing.html`, `editor/editor_base.html`). Event scripts added to `survey_section.html` and `survey_thanks.html`
- **Settings**: Two new env vars (`PLAUSIBLE_DOMAIN`, `PLAUSIBLE_SCRIPT_URL`)
- **Context processors**: New `analytics()` context processor registered in settings
- **No database changes**: No migrations needed
- **No new dependencies**: Uses Plausible's CDN script, no Python packages
