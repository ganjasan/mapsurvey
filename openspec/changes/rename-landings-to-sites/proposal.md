## Why

The platform Vision session (owner, 2026-11-09) named the module **Sites** — one of Surveys · Map apps · Sites · Data — and moved its concept toward project sites for landscape and planning firms and municipal sites, not a single landing page. The epic (#348) is not merged yet: its migrations exist only on `epic/landing-pages`, so this is the cheapest moment to rename everything once rather than carry "landing" in code under a "Sites" product.

## What Changes

- **BREAKING (unreleased only):** models `Landing`, `LandingSurvey`, `LandingBlock`, `LandingFile` become `Site`, `SiteSurvey`, `SiteBlock`, `SiteFile`; `ContentReview.landing` → `site`; migrations `0118`–`0120` are rewritten in place (no production row exists; dev and preview databases are recreated).
- Modules `survey/landings.py`, `landing_views.py`, `landing_events.py`, `templatetags/landing_tags.py` → `sites.py`, `site_views.py`, `site_events.py`, `site_tags.py`; templates `landings/` → `sites/`; `css/landing_builder.css`, `css/landing_public.css`, `js/landing_builder.js`, `js/landing_confirm.js` → `site_*`. The marketing `css/landing.css` and the SEO landings are untouched.
- Editor URLs `/editor/landings/…` → `/editor/sites/…`, URL names `editor_landing*` → `editor_site*`; the public address stays `/p/<slug>/` (platform Vision FE-9).
- Billing feature key `landing_pages` → `sites`; help page `how-to/landing-pages` → `how-to/sites`; changelog entry renamed.
- Creator wording: the object is a **site** ("New site", "Site settings", "Delete site", "Surveys on this site"); what is drawn on the canvas keeps "page" ("Blocks on the page").
- Spec `survey-landings` → `survey-sites`; test module `test_survey_landings` → `test_survey_sites`. Archived changes keep their names.
- CSS class prefixes `lp-` / `lb-` stay as internal names.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `survey-sites` (was `survey-landings`): the module and every creator surface are named Sites.

## Impact

Code of the epic only (shared files changed only where the epic added lines), 11 creator catalogs (msgids carried over, wording revised), help, changelog, `TERMS_UPDATED`. Dev database of the worktree recreated.
