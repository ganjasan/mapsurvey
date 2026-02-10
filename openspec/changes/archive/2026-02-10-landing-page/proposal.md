## Why

Currently the root URL (`/`) redirects authenticated users to the editor and everyone else to the login page. There is no public-facing entry point that explains what Mapsurvey is, who it's for, or what it can do. The platform needs a landing page at `mapsurvey.org` to attract its primary audience — architectural, urban planning, and urbanism firms — and convert visitors into leads who reach out to order survey creation.

## What Changes

- Replace the redirect-only root view with a public marketing landing page
- Add a hero section with a value proposition targeting architecture and urban planning professionals, with a primary CTA to contact us (email + Telegram)
- Add a "How it works" section explaining the service flow
- Display cards for demo surveys, active surveys, and completed surveys (with results)
- Add a publications/stories section for showcasing survey results as maps, open data, and narratives
- Introduce a separate `base_landing.html` template with its own visual identity (custom fonts, custom CSS, no Bootstrap dependency)
- Add a new `/stories/<slug>/` route for individual story pages
- Contact section at the bottom with email and Telegram links

## Capabilities

### New Capabilities
- `landing-page`: Public marketing page at `/` with hero, how-it-works, contact CTAs (email + Telegram), survey cards, stories. Separate base template with cartographic-editorial visual identity.
- `survey-cards`: Dynamic cards displaying demo, active, and archived surveys with status badges, response counts, and result links
- `public-stories`: Publishing survey results as maps, open data, and editorial content. Includes story model, landing section, and detail pages.

### Modified Capabilities
_None — existing capabilities are not changing at the spec level._

## Impact

- **Views**: `index` view in `survey/views.py` changes from a redirect to rendering a template; new `story_detail` view
- **Templates**: New `base_landing.html` (independent from `base.html`), `landing.html`, `story_detail.html`
- **URLs**: Root path `/` now serves HTML instead of redirecting; new `/stories/<slug>/` route. Authenticated users can still navigate to `/editor/`
- **Models**: `visibility` and `is_archived` fields on `SurveyHeader`; new `Story` model for publications
- **Static assets**: `landing.css` with custom CSS (no Bootstrap), Google Fonts for typography
- **Configuration**: Contact email and Telegram handle stored in Django settings (or template context)
