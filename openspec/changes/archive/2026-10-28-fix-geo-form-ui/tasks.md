# Tasks

## 1. Rating: stop clipping worded labels (backlog #85)

- [x] 1.1 In `survey/assets/css/main.css`, change `.question-card--rating > div > div`
      from `flex: 1; min-width: 0` to content-driven sizing (`flex: 1 1 auto`,
      `min-width: min-content`) so an option is never squeezed below its text.
- [x] 1.2 On `.question-card--rating label:has(input[type="radio"])`, add `width: 100%`,
      `overflow-wrap: anywhere` and `hyphens: auto` so a long single word wraps rather
      than overflowing. Padding raised from `8px 4px` to `8px 8px` for breathing room.
- [x] 1.3 Verify the existing `flex-wrap: wrap` now actually wraps a long scale onto a
      second row once the basis is content-driven. Confirmed: the five-option scale
      "very unsure … very confident" wraps to three rows in the 350px side panel, all
      labels fully readable.
- [x] 1.4 Check that a numeric scale (1-5) still renders as evenly sized buttons —
      equal-length labels give equal widths via `flex-grow`.

## 2. Sub-question popup width (backlog #86)

- [x] 2.1 Added `_subquestionPopupOptions()` in
      `survey/templates/base_survey_template.html` (next to `_buildPopupHtml`) returning
      `maxWidth: min(520, 90vw)`, `minWidth: min(300, 90vw)`,
      `maxHeight: 70vh` — width was previously unset, so Leaflet's 300px default applied.
- [x] 2.2 Both `bindPopup` call sites now use the shared helper instead of duplicating
      inline options, so they cannot drift apart again.
- [x] 2.3 Verified with the 8-sub-question building form: popup renders at 520px on a
      1854px viewport (was 300px). Options that previously wrapped onto two lines each
      now fit on one. A scrollbar remains for 8 groups, which is expected — the deeper
      fix is the side-panel redesign left open in backlog #86.

## 3. Verify

- [x] 3.1 `python manage.py collectstatic --noinput` — 2 files copied, 169 post-processed.
- [x] 3.2 Checked in a browser against the local Quedlinburg demo survey (id 720), which
      still carries the original worded rating scale and the 8-sub-question geo point.
- [x] 3.3 `./run_tests.sh survey` — **711 tests, OK**.
- [x] 3.4 Backlog #85 struck through in `openspec/backlog/INDEX.md`; both files carry a
      "promoted to `fix-geo-form-ui`" note. #86 stays open for the side-panel redesign.

## 4. Not done here (deliberate)

- Author-facing settings for popup width/height — rejected in the proposal: the author
  cannot know the respondent's screen, so the default has to be right on its own.
- Moving the attribute form from the popup into a side panel — larger change, still
  tracked under backlog #86.
