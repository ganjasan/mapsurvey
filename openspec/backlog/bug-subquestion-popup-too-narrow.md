# Sub-question popup is too narrow (Leaflet default width)

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-07-28

> **Promoted to the OpenSpec change `fix-geo-form-ui` on 2026-07-28.** The width/height
> defaults were fixed there. The **side-panel redesign** described under "Longer-term"
> was deliberately left out of that change and is still open.

## Description

When a geo question has several sub-questions, the popup that opens after placing a
point/line/polygon is a narrow 300px column with an internal scrollbar. The respondent has
to scroll a long list of radio groups inside a small box floating over the map, while the
popup simultaneously hides the feature being described.

This matters more than it looks: sub-questions of a geo question are the **only** way to get
attributes into the exported GeoJSON `properties` (see `survey/views.py:941`), so any survey
that produces a usable attribute layer is pushed into exactly this pattern. The richer the
data model, the worse the form.

## Root cause

`survey/templates/base_survey_template.html:383` (and the duplicate at `:513`)

```js
layer.bindPopup(_buildPopupHtml(formId, sqHtml), {
    maxHeight: $(document).height()*0.8,
});
```

**`maxWidth` is never set**, so Leaflet's default of 300px applies. Height is configured;
width is not. Note also that `maxHeight` is derived from `$(document).height()`, which is the
document, not the viewport — on a long page this can exceed the visible area.

## Reproduce

1. Create a `point` question and attach 6-8 `choice` sub-questions.
2. Open the survey, place a point.
3. The popup is ~300px wide with a scrollbar; options wrap onto two lines each.

Live example: the ThINK demo survey (`user_surveys/waermeplanung_quedlinburg_demo/`), where
the building point carries 8 attribute sub-questions.

## Proposed fix

**Do not expose width/height as author-facing settings.** The survey author does not know the
respondent's screen, will mostly leave the default alone, and can only make it worse. Ship
sensible defaults first; a per-survey override can come later if a real case demands it.

```js
maxWidth:  Math.min(520, $(window).width() * 0.9),
minWidth:  300,
maxHeight: $(window).height() * 0.7,
```

- Width driven by the **viewport**, capped around 520px so desktop gets a comfortable column
  and mobile gets nearly the full screen.
- Height from `$(window).height()`, not `$(document).height()`.
- Apply to **both** call sites (`:383` and `:513`) — they are currently duplicated.

## Longer-term

A form of 8 attributes does not belong in a popup over the map at all. In GIS tooling the
attribute form lives in a **side panel**: there is room, the map stays visible, and the
feature being edited is not covered by its own form. Worth a separate change proposal —
render sub-questions in the left panel (with the feature highlighted on the map) instead of,
or in addition to, the popup.

## Notes

- Raised by the user 2026-07-28 while reviewing the ThINK demo.
- Related: [Rating question clips text labels](bug-rating-text-labels-clipped.md),
  [Image sub-question breaks point placement](bug-image-subquestion-breaks-geo-point.md).
