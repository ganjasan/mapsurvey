# Tasks

## 1. Fix
- [x] 1.1 `editor_base.html`: navbar "Dashboard" link → `{% url 'editor' %}?dashboard=1`, with a comment naming the redirect it bypasses
- [x] 1.2 Test in `EditorZeroSurveyRedirectTest`: create page navbar link carries `?dashboard=1`

## 2. Verification
- [x] 2.1 `./run_tests.sh survey.tests.EditorZeroSurveyRedirectTest` green
- [x] 2.2 Browser: fresh org, click "Dashboard" from the create page → dashboard renders

## 3. Bundled: map picker painted over navbar dropdowns
- [x] 3.1 `survey_create.html`: `.create-map-wrap { z-index: 0 }` isolates Leaflet's panes/controls (400/1000) inside the wrapper, below the sticky navbar (100) — the language/workspace dropdowns were clipped at the map's top edge
