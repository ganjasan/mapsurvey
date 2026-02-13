## Why

Survey questions currently render as plain `<p>` elements via Django's `form.as_p()`. There is no visual separation between questions — they blend together in the narrow sidebar (`#info_page`, max 480px), making the form harder to scan. Radio buttons and checkboxes use default browser styling, which looks dated and is hard to tap on mobile. The UI needs to be scannable and have clear touch targets — this is a field survey tool used alongside a full-screen map.

## What Changes

**Aesthetic direction**: Clean, field-survey utilitarian. Crisp, readable, high-contrast, with clear touch targets. Not decorative — purposeful.

- **Replace `form.as_p()` with custom template iteration** — iterate form fields in `survey_section.html`, wrapping each input-bearing question in a card `<div>` (white background, padding, border-radius, light border)
- **Card scope** — the following question types get cards: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`. The following stay as-is: geo buttons (`point`, `line`, `polygon`) already have good button styling; `html` and `image` are display-only and remain full-bleed; `rating` stays inline (horizontal row) with no card wrapper
- **Custom radio buttons and checkboxes** — CSS-only: hide native input, style `label` with visible circle (radio) / square with checkmark (checkbox), fill animation on select. Min 44px tap target height per WCAG
- **Geo button visual consistency** — minor tweaks to `.drawbutton` to match card border-radius and spacing rhythm
- All changes are CSS/template-only — no model or migration changes

## Capabilities

### New Capabilities
- `question-card-styling`: Template and CSS changes to render survey questions in card layout with custom radio/checkbox styling

### Modified Capabilities

## Impact

- `survey/templates/survey_section.html` — replace `form.as_p` with field-by-field iteration wrapping questions in cards
- `survey/assets/css/main.css` — card styles, custom radio/checkbox, geo button tweaks
- `survey/forms.py` — add `input_type` as a widget attribute so the template can distinguish question types for conditional card wrapping
- `survey/templates/leaflet_draw_button.html` — border-radius and spacing adjustments
