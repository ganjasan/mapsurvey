## 1. Import and funnel fixes

- [x] 1.1 `serialization.py`: accept `stars` as a rating `display_style` and as `style_settings.rating_display_style`
- [x] 1.2 `funnel.py`: demo total excludes sessions tagged `sample`
- [x] 1.3 `resolve_question_layers`: remap a question layer's `label_field` (a sub-question code) together with its source code
- [x] 1.4 Tests: stars round-trip; sample sessions not counted as demo opens; shared-layer label survives a remapped import

## 2. Demo data

- [x] 2.1 `scripts/build_copenhagen_demo.py`: bridges from Overpass (longest way per bridge), Wikidata facts + Commons photo (≤ 800 px) and credit, bike-routed sample routes, unsafe-spot samples near real junctions; writes `survey/demo_data/copenhagen_cycling/`
- [x] 2.2 Hand-written `survey.json`: six sections, branching, stars, bridges layer with category style, shared layer, thanks page
- [x] 2.3 Run the builder, review the bridge texts and photos, commit the output

## 3. Command

- [x] 3.1 `seed_demo_survey --org <slug> [--replace] [--remove-samples]`: zip + import, publish, resolve questions by names
- [x] 3.2 Sample sessions (tag `sample`): trips, bridge reactions + comments, unsafe spots, routes, reactions on others' marks; `backfill_question_layer`
- [x] 3.3 Public results page: scaffold, slug `copenhagen-cycling-demo`, published, unlisted, sample-data intro
- [x] 3.4 Tests (GIVEN/WHEN/THEN): fresh install shape, already-installed stop, replace, codes remapped on a second org, remove-samples keeps real sessions, shared layer holds sample marks, results page reachable

## 4. Respondent popup fixes found while building the demo

- [x] 4.1 `_subquestionPopupOptions`: auto-pan padding clears the open desktop panel and the address search box
- [x] 4.2 `main.css`: `.lo-card` loses its side bleed (-4px) that overflowed once the popup scrolled vertically

## 5. Verify

- [x] 5.1 Seed locally, walk the demo in a browser at desktop and 390 px, check the results page
- [x] 5.2 Full test suite
