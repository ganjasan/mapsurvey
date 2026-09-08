## Why

Creators cannot find a marker icon for their geo question: the editor's icon picker is a
hardcoded list of ~180 Font Awesome 5 classes, and its search matches only substrings of the
English class name. "playground", "bench", "Fahrrad" and "остановка" all return nothing, even
though the loaded Font Awesome stylesheet ships ~1,500 free icons and `fa-child`, `fa-bus`,
`fa-bicycle` are already in the list. The free-text `icon_class` field lets a creator paste any
Font Awesome class, but they would have to know the name first. Our creators author in DE, PL,
PT, RU and ID as well as EN, and Font Awesome is a web-UI set, not a map set: the things people
place on a participatory map (bench, streetlight, bus stop, bike rack, litter bin, crossing) are
mostly absent from it. Nobody has measured what creators actually search for, so the size of the
gap is a guess.

## What Changes

- **Measure misses.** The picker emits a PostHog event when a search returns zero icons,
  carrying the query text, so the real vocabulary creators use becomes visible. Creator-only
  surface (`/editor/`), so the existing analytics exclusion rules already apply.
- **Full Font Awesome set with keyword search.** The picker is fed from a generated static
  catalog covering every free Font Awesome icon (solid + regular) instead of the inline list.
  Each entry carries the upstream `search.terms` plus its label, and search matches on those, not
  on the class name. The Font Awesome CDN link moves from 5.8.1 to the last 5.x release (5.15.4)
  so the catalog and the stylesheet agree; classes are unchanged between them, so stored
  `icon_class` values keep rendering.
- **Multilingual search terms.** The catalog carries translated search terms for the languages
  the product supports (EN, RU, DE, ES, FR, PT, PL, ID). Translations are produced once at
  catalog-build time and shipped as static data; nothing is translated at runtime and no AI call
  is made from the picker.
- **Browse by category.** The picker offers category tabs (transport, nature, buildings,
  people, safety and problems, amenities, shapes, …) derived from Font Awesome's category
  metadata, for the creator who does not know the word but knows the theme. A "Map" category
  groups the map-specific set below.
- **Map-specific icon set.** The picker gains the Maki (Mapbox) and Temaki (OSM iD) icon sets,
  both CC0, both drawn for map POIs (bench, playground, bus stop, bike parking, waste basket,
  street lamp, crossing…). They are SVG, not font glyphs, so `icon_class` gains a second value
  form (`maki:bench`, `temaki:bench`) and every surface that draws a marker resolves it through
  one shared helper: respondent map markers and the crosshair overlay, the creator's Responses
  map, the public results map, the star-rating icon, editor previews, and data export.
- **No change** to the free-text `icon_class` field: a pasted Font Awesome class still works,
  and existing surveys render exactly as before.

## Capabilities

### New Capabilities
- `marker-icon-picker`: how a creator finds and chooses a marker icon in the question editor —
  catalog contents, keyword and multilingual search, category browsing, miss telemetry, and the
  `icon_class` value forms the picker may write.
- `marker-icon-rendering`: how an `icon_class` value (Font Awesome class or `maki:`/`temaki:`
  name) is resolved to a drawn glyph on every surface that shows a question's marker, including
  the fallback for a value no catalog knows.

### Modified Capabilities
- `rating-question-display`: the star icon may be any catalog icon, not only a Font Awesome
  class; default and fallback behaviour unchanged.
- `survey-serialization`: `icon_class` in ZIP export/import accepts the new value forms and
  keeps them verbatim; an unknown value is preserved, not dropped, so a survey round-trips.

## Impact

- **Editor**: `survey/templates/editor/partials/question_form_modal.html` (picker rewritten to
  read a catalog instead of the inline list), `survey/editor_forms.py` (`icon_class` validation
  and help text), `survey/templates/editor/editor_base.html` (picker CSS, Font Awesome version).
- **Rendering**: `survey/assets/js/L.Icon.FontAwesome.js` gains an SVG-glyph branch;
  `base_survey_template.html` (respondent markers, crosshair overlay, popup edit),
  `editor/partials/analytics_geo_map.html`, `editor/public_results.html`, `survey_create.html`,
  `leaflet_draw_button.html`, the star-rating template and `Question.star_icon`.
- **Static data**: a generated icon catalog (JSON) plus Maki/Temaki SVG sprites under
  `survey/assets/`, built by a management command or script from upstream metadata so the set
  can be refreshed; sprites are served like any other static file.
- **Model**: no migration. `icon_class` stays a `CharField(max_length=80)`; the `maki:`/`temaki:`
  prefix fits comfortably.
- **Analytics**: one new PostHog event on the creator surface.
- **Dependencies**: Font Awesome CDN link version bump; Maki and Temaki vendored as static
  assets (CC0), no new Python or npm dependency at runtime.
- **Licensing**: Font Awesome Free icons are CC BY 4.0 (attribution already satisfied by the
  bundled license notice in the CSS); Maki and Temaki are CC0.
- **AI survey generation** already picks marker icons from a curated Font Awesome enum
  (`MARKER_ICONS` in `survey/ai/schema.py`); that enum is untouched here, and widening it to the
  map set is a follow-up once the telemetry shows which icons creators actually reach for.
- **Out of scope** (left for later, pending the miss telemetry): suggestions derived from the
  question title, creator-uploaded custom icons.
