## Why

The platform's highest-volume public asset — filled-in survey pages — currently converts to
**zero** attributable registrations. The demo `demo_city_feedback` alone has ~1576 sessions and is
still collecting daily, all fed largely by the landing page, yet no respondent has a path (or a
reason) to create their own survey. This is the cheapest, fastest-compounding acquisition loop in
the growth epic (`docs/gtm/gtm-plan-2026-h2.md`, hypothesis H3), and it now pairs directly with the
Phase-1 signup attribution already shipped — a UTM-tagged CTA lands in the dashboard's
registrations-by-source as `viral_loop`.

## What Changes

- Add a tasteful **"Made with Mapsurvey — create your own free map survey"** CTA on public-facing
  survey pages: the survey-answering page (persistent footer) and the thanks page (highest-intent
  moment after submission).
- The CTA links to registration **UTM-tagged** `utm_source=viral_loop&utm_medium=<page>` so the
  channel is measured via Phase-1 attribution.
- A creator-side toggle `SurveyHeader.show_branding` (default **on** for the free-tier loop; off for
  a clean/unbranded look, e.g. government/B2B). Surfaced in the survey settings modal.
- The setting is carried through serialization (export/import) and survey versioning (draft clone
  and publish).

## Capabilities

### New Capabilities
- `viral-loop-branding`: A "Made with Mapsurvey" CTA on public survey + thanks pages, UTM-tagged for
  attribution, controlled by a per-survey `show_branding` toggle (default on).

### Modified Capabilities
<!-- None at spec level. serialization / versioning gain one field but their requirements are unchanged. -->

## Impact

- **Model**: `SurveyHeader.show_branding` BooleanField(default=True) + migration `0034`.
- **Templates**: new partial `partials/_made_with_mapsurvey.html`; included in
  `base_survey_template.html` (survey shell) and `survey_thanks.html`.
- **Editor**: `SurveyHeaderForm` gains `show_branding` (auto-rendered in the settings modal).
- **Serialization**: `serialize_survey_to_dict` + import respect `show_branding`.
- **Versioning**: `clone_survey_for_draft` and `publish_draft` copy `show_branding`.
- **Depends on / pairs with**: Phase-1 `SignupAttribution` (already shipped) — the CTA's UTM is what
  makes the loop measurable.
