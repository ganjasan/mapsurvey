# The survey page always renders the map, so non-geo surveys get a ~370px column

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-05

## Description

`base_survey_template.html:74` renders `<div id="map"></div>` unconditionally, and `#map` takes the
full viewport width behind a fixed-width sidebar (`#info_page`, 420px, `max-width: 460px`). A survey
with no geo question at all therefore hands roughly 80% of the screen to an empty basemap and
squeezes every question into the sidebar.

Measured on a survey containing a single `range` question and nothing else: viewport 1854px,
question column 371px, the slider inside it 337px.

This affects every question type, not one of them. It is simply most visible on the controls that
want horizontal room — sliders, scale strips, long choice labels, wide tables.

## Notes

- Found 2026-08-05 while reproducing backlog #99. Manuel Frost reported the range slider as "too
  short"; the slider is `width: 100%` and behaving correctly, so this layout is the actual cause of
  what he saw. #99 fixed the label alignment, which was a separate and real defect, but not this.
- The fix is not simply "hide the map when there are no geo questions" — decide first what the page
  should look like without one. A centred single-column form is the obvious answer and is what every
  other survey tool does, but it is a visual decision about the product's identity ("Google Forms for
  geodata") rather than a CSS change, since the map is the thing that makes Mapsurvey recognisable.
- Intermediate cases need a rule too: a survey where only section 3 has a geo question, or a section
  whose geo question is optional. Reflowing the layout between sections would be jarring; deciding
  per survey is probably right.
- Cheap first slice, if the full decision stalls: let the sidebar widen when the survey has no geo
  questions, rather than removing the map. Lower risk, most of the benefit.
- Related: [Survey visual customization](improvement-survey-visual-customization.md) (#42) covers
  spacing and separators inside the card; this is the container around it.
