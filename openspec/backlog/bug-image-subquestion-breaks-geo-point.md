# Image sub-question breaks point placement on geo question

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-04-25

## Description

When an image sub-question is attached to a geo (point/line/polygon) question, the geo question stops working — the user cannot place a point on the map at all. The image upload widget appears to interfere with the Leaflet drawing handlers, blocking the core geo input.

## Notes

- Reproduce: create a `point` question, add an `image` sub-question under it, open the survey, try to click the map → no marker is placed.
- Likely root cause area: `survey/forms.py` (custom Leaflet draw widgets) or the JS in `templates/survey/survey_section.html` that wires image upload + map handlers. Image widget may be capturing clicks or its initialization may be erroring out before the Leaflet draw handler binds.
- Real-world impact: **pbenassi@agriprotech.fr** (AgriProTech, France) registered 2026-04-23 and built a survey with exactly this pattern — image + point. Their use case (likely field reporting of bird-control sites with photos) is blocked.
- Image + point is also a natural pattern for citizen-science surveys (`Galanthus locations`, `Lost Rural Home`, `Orcas & Otters Sightings`) — silent breakage means we may be losing users without knowing.
- Check JS console for errors during the failing flow — if the widget throws, point handler never binds.
- Related question types to test: image under `line`, `polygon` (probably also broken).
