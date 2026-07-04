# Tasks — made-with-mapsurvey-viral-loop

## 1. Model + migration

- [x] 1.1 Add `SurveyHeader.show_branding` BooleanField(default=True) with help text
- [x] 1.2 Generate migration `0034_surveyheader_show_branding` (additive, default on)

## 2. CTA component + placement

- [x] 2.1 Reusable partial `partials/_made_with_mapsurvey.html` — minimal badge, guarded by `survey.show_branding`, links to registration with `utm_source=viral_loop&utm_medium=<medium>`
- [x] 2.2 Include on the survey shell (`base_survey_template.html`, `medium=survey`) — persistent footer while answering
- [x] 2.3 Include on the thanks page (`survey_thanks.html`, `medium=thanks`)

## 3. Creator toggle + persistence

- [x] 3.1 Add `show_branding` to `SurveyHeaderForm.Meta.fields` (auto-rendered in the settings modal)
- [x] 3.2 Serialization: export in `serialize_survey_to_dict`; import with default True
- [x] 3.3 Versioning: copy `show_branding` in `clone_survey_for_draft`, the archived snapshot, and the publish field-copy

## 4. Tests

- [x] 4.1 `ViralLoopBrandingTest`: default on; CTA + UTM on thanks (`utm_medium=thanks`) and survey (`utm_medium=survey`); hidden when off; serialization includes the field
- [x] 4.2 Serialization/import round-trip suites still green

## 5. Follow-ups (not in this change)

- [ ] 5.1 CTA on the public results page (`/r/<slug>/`, `medium=results`) — the highest-value placement, pairs with public-results-showcase-seo
- [ ] 5.2 Measure lift: watch `viral_loop` in the funnel dashboard's registrations-by-source after deploy
