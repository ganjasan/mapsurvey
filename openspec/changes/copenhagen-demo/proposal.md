## Why

The landing page's demo (`demo_city_feedback`, April 2026) shows only a point, a line and a polygon with sub-questions. Everything that sets Mapsurvey apart since then is invisible to a visitor: reference layers with object cards, reactions to the creator's objects (👍/👎), the shared map where respondents see and react to each other's marks, question branching, star ratings, photo uploads, and the public results page. The closest free competitor, Partimap, runs its demo as a guided tour that shows one capability per step (walked 2026-08-26, `docs/marketing/competitors/partimap.md`); ours should do the same on our strengths, and it is also the source for the next round of landing screenshots.

## What Changes

- New demo survey **"Cycling in Copenhagen"**, a six-step tour: questions that adapt (choice → branch, stars) → rate real cycling bridges from OpenStreetMap (layer with photo cards, 👍/👎 + comment) → mark an unsafe spot (point, problem, photo) → draw your route (line) → see what others marked (shared map, react) → thanks page linking to a published public results page.
- The survey is **source in the repository** (`survey/demo_data/copenhagen_cycling/`: `survey.json`, bridge GeoJSON + object manifest, Wikimedia Commons photos with attribution) and is installed by a new management command **`seed_demo_survey`**. It builds the ZIP in memory and goes through `import_survey_from_zip`, so the demo is also a standing test of import.
- The command adds what a ZIP cannot carry: about 40 **sample responses** (reactions on bridges, unsafe-spot marks, routes, reactions on others' marks), materialises the shared map with the existing `backfill_question_layer`, and scaffolds + publishes the public results page. Every sample session carries the tag **`sample`**; the welcome text and the results page say plainly that the map holds sample answers. `--remove-samples` deletes them.
- **Import fix**: `stars` survives import as a rating `display_style` and as `style_settings.rating_display_style`. Today both are silently reset although the editor offers them.
- **Import fix**: a shared-map layer's `label_field` (a sub-question code) is remapped with its source question on import; today marks lose their titles whenever codes collide.
- **Funnel fix**: demo opens exclude sessions tagged `sample`, so seeding never inflates the metric.

- **Respondent popup fixes** found while walking the demo: on desktop a popup opened under the panel that overlays the map (and under the address search box), cutting off the card and pushing the answer form out of reach; the object card also overflowed sideways once it scrolled.

Out of scope: switching `DEMO_SURVEY_URL` (an env change on Render after the seed runs), new landing screenshots and the Capabilities copy (follow-up change `landing-capabilities-refresh`).

## Capabilities

### New Capabilities

- `demo-survey`: the demo survey's content contract, the `seed_demo_survey` command, sample-response tagging and removal.

### Modified Capabilities

- `survey-serialization`: `stars` is a known display style on import for rating questions and for the survey-wide default.
- `creator-funnel-dashboard`: demo opens exclude sessions tagged `sample`.
- `marker-popup-isolation`: popups open clear of the panel and the search box.

## Impact

- New: `survey/management/commands/seed_demo_survey.py`, `survey/demo_data/copenhagen_cycling/*` (~1–2 MB with photos), `scripts/build_copenhagen_demo.py` (one-off data builder: Overpass, Wikidata/Commons, bike routing; output committed).
- Changed: `survey/serialization.py` (two whitelists), `survey/funnel.py` (demo count).
- Ops: run `python manage.py seed_demo_survey --org mapsurvey` once on production (Render job, single command, no shell needed), then set `DEMO_SURVEY_URL` to the new survey.
- Data licences: OpenStreetMap (ODbL) for geometry, Wikimedia Commons licences per photo, credited in each object's description.
