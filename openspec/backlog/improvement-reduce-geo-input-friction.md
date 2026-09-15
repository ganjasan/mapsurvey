# Reduce geo-input friction (geo questions are the most-skipped type)

**Type**: improvement
**Priority**: high
**Area**: frontend
**Epic**: —
**Created**: 2026-06-10
**Related**: [Finish Drawing Buttons for Polygon and Line](improvement-finish-drawing-buttons.md)

## Description

Geo questions — the platform's core differentiator — are also the highest-friction element for respondents. Make map input as low-effort as possible by default: simplest interaction first (tap-to-place point), clear optionality, visible progress, and inline guidance.

## Evidence (2026-06-10 analysis)

Answer-rate by question type, across clean sessions in surveys with ≥5 responses (share of respondents who actually answered each question; `konuchovartem` demo excluded):

| Type | Answer rate |
|------|-------------|
| rating | 96.7% |
| text | 47.6% |
| multichoice | 45.0% |
| range / number | 44.7% |
| choice | 40.0% |
| **point (geo)** | **31.8%** |
| **line (geo)** | **31.2%** |
| **polygon (geo)** | **16.5%** |

Geo questions are answered by 16–32% of respondents vs 40–48% for non-geo. **Polygon is the worst (16.5%).** This is the most-skipped substantive question type on the platform — the very feature that differentiates Mapsurvey creates the biggest respondent drop.

Caveat: answer-rate conflates "didn't reach", "reached but skipped", and "optional question". But the gradient (point > line > polygon, all well below non-geo) is consistent with rising interaction cost, not just optionality.

## Scope / ideas

- **Lowest-effort default**: tap/click-to-place for points (no mode switch), with the map already centered (geolocation centering already shipped).
- **Make optionality explicit**: clear "skip / optional" affordance on geo questions so respondents don't bail on the whole survey.
- **Finish/confirm affordance for line & polygon** — see [finish drawing buttons](improvement-finish-drawing-buttons.md) (likely a prerequisite sub-task).
- **Inline guidance**: short instruction + example near the map ("Tap on the map to place a point").
- **Progress indication** so a hard geo question mid-survey doesn't read as a dead end (ties to [progress bar](feature-progress-bar.md)).
- Consider lighter polygon UX or a simpler alternative for casual audiences.

## Notes

- This is a respondent-completion fix, distinct from creator activation. High product priority because it touches the core value prop.
- Measure impact via answer-rate-by-type before/after (the query above is the baseline).
- Worth running through OpenSpec (`/opsx:new`) — touches respondent-facing forms and Leaflet widgets in `survey/forms.py` + `survey_section.html`.
- **2026-08-10 — partially shipped.** Crosshair tap-to-place (`base_survey_template.html:94-105,313-340`), geolocation centering (`:815-817`) and the finish/cancel draw bar (#34) all landed. Still open: an explicit skip affordance, inline "tap the map" guidance, a real progress bar (#39), and any measurement of whether the answer rate moved.

## Field evidence — 2026-09-03 (respondents, not analytics)

Cllr Julian Thomas (Whitehouse Community Council) ran a dog-bin siting survey with real residents
and reported back:

> "Several residents have told me that the main 'place your pin' page isn't very mobile-friendly,
> and the big button you click on to place a pin was not intuitive. I fixed this by minimising the
> explanatory text so that the big button is more visible, and also relabelling that button to
> 'CLICK HERE' — but I did expect to just be able to click on the map without first needing to
> click that separate button, so I can see why they struggled"

Three separate findings in one paragraph:

1. **The crosshair entry button is a mode switch nobody expects.** The 2026-08-10 note above says
   "crosshair tap-to-place shipped" — but shipped as *tap the button, then tap the map*. Both the
   creator and his residents expected the first tap on the map to place the pin. The intended
   lowest-effort default in this item's Scope section is therefore still not what respondents get.
2. **Explanatory text pushes the control below the fold on phones.** He worked around it by
   deleting his own instruction text — i.e. the fix cost him content he wanted respondents to read.
   The button competes with `subtext`/`subheading` for the same first screen.
3. **There is no button label to fix — the button *is* the question.**
   `leaflet_draw_button.html` renders `widget.title` (the question's `name`) as the button text and
   `widget.subtitle` (its `subtext`) underneath; nothing on that control says "tap to place a pin".
   So Julian's fix — relabelling to "CLICK HERE" — means he renamed his actual question, and his
   exported CSV/GeoJSON column is now called "CLICK HERE". He traded his data's labelling for a
   working affordance. The control needs its own verb, separate from the question text.

This is a creator who liked the product ("intuitive", "very well-received") and still had to
hand-patch the pin page. Weight this item accordingly: the answer-rate table above said geo is the
most-skipped type, and this is the first direct account of *why*.

Source: `docs/marketing/user-outreach/julian_thomas/correspondence/2026-09-03_reply-received.md`
