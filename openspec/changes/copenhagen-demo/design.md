## Context

A demo must show features a ZIP only partly carries. Structure, layers, object cards, photos, styles, branching and icons round-trip through `import_survey_from_zip`; answers tied to layer objects (`Answer.layer_object`) and shared-map marks (`LayerObject.source_session`) do not, and the public results page is excluded from ZIPs on purpose. Question codes are globally unique, so an import on a database that already holds a code remaps it.

## Goals / Non-Goals

**Goals:** a demo a buyer finishes in about three minutes, where each step names the capability it shows; reproducible from the repository on any environment (local, PR preview, production); honest about sample data; removable sample data.

**Non-Goals:** translations of the demo (English only for now), a generic "seed any survey" tool, changing the old demo survey (it keeps its 85 sessions and simply stops being the demo).

## Decisions

- **Structure through the real import, extras through the ORM.** `seed_demo_survey` zips `survey/demo_data/copenhagen_cycling/` in memory and calls `import_survey_from_zip(organization=…)`. Everything the ZIP cannot carry is created directly afterwards. Alternative (all ORM) rejected: it would bypass the import path creators use and duplicate its validation.
- **Questions are resolved by section name + question name after import**, never by archive code, because codes may be remapped.
- **Shared map via `backfill_question_layer`**, the same function the editor uses when a layer is added after collection started, so sample marks get keys `s<session>-<n>` exactly as real ones.
- **Sample sessions**: `tags=['sample']`, `opened_by_kind='external'`, `validation_status=''` (clean, so they count in public aggregates), start times spread over the last 30 days, `end_datetime` set. Deterministic (`random.Random(20261001)`) so a re-seed produces the same data.
- **Sample data lives in `samples.json`**, generated once by `scripts/build_copenhagen_demo.py` together with the geometry, and committed. Routes follow real streets (bike routing), unsafe spots sit near real busy junctions with jitter. The command does not call the network.
- **Idempotency**: an existing survey with the same name in the org stops the command with a message; `--replace` deletes it first (with its sessions and page); `--remove-samples` deletes only sessions tagged `sample` and rebuilds the shared layer.
- **Public results page**: `scaffold_page`, then slug `copenhagen-cycling-demo`, `is_published=True`, `visibility='unlisted'` (sample data should not be indexed), intro body stating that answers are samples.
- **Bridges layer**: lines (OSM ways, longest way per bridge), categories `Cycle & foot bridge` / `Road bridge with cycle lanes` styled by a categories rule; each object carries a Commons photo, one or two factual sentences checked against Wikidata, a Wikipedia link, and the photo credit.
- **Imports keep `stars`**: the rating whitelist on import becomes `default, scale_strip, list_pips, stars`, same as the editor form; `style_settings.rating_display_style` accepts `stars`, same as `SurveyHeader.get_default_rating_display_style`.

## Risks / Trade-offs

- [Sample answers could be mistaken for real engagement] → tag, visible disclosure on welcome and results page, one-flag removal, funnel exclusion.
- [Photos add ~1–2 MB to the repository] → downscaled to ≤ 800 px JPEG.
- [A real city may be read as a client] → welcome text: "a demo, not a survey run by the City of Copenhagen".
- [Code remap on production] → resolution by names, covered by a test that seeds twice into one database.

## Migration Plan

No schema change. Deploy, run `seed_demo_survey --org mapsurvey` as a Render job, check the survey and `/r/copenhagen-cycling-demo/`, then set `DEMO_SURVEY_URL`. Rollback: point `DEMO_SURVEY_URL` back to the old survey.
