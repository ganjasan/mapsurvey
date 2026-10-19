## Why

Owner feedback right after #364 shipped. Each choices-table row spent three controls on one icon: a preview square, a text field showing `maki:airfield`, and a grid button. There was no visible way to clear an icon. The dropdown was still small and cramped inside the table cell, because its size was tied to the cell and the modal around it.

## What Changes

- **One control.** The icon picker is a single square button that shows the current icon, or a dashed "+" when there is none. The value input stays in the DOM, hidden, and is what the form submits. This applies to every picker: the question's marker icon, star ratings and the choices table.
- **A panel instead of a dropdown.** The button opens a panel about 560 × 520 px, placed with `position: fixed` next to the button. It goes below the button when it fits, above it otherwise. When neither side fits, it takes the roomier side, shrinks, and never covers the button. Below 768 px it remains the full-width bottom sheet. The grid uses 48 px cells.
- **Clearing an icon.** The panel has a "Remove icon" button next to the search box, and a "No icon" tile first in the grid while browsing.
- **Typed values.** A search query that is itself a valid value (`fas fa-x`, `maki:x`) offers "Use <value>" (Enter applies it). Pasted Font Awesome Pro classes keep working without a text field.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `marker-icon-picker`: the picker is one button plus a fixed-position panel with remove / no-icon / use-typed-value. This replaces the input-width dropdown, and the ≥440 px rule from `icon-grid-color-picker`.

## Impact

`survey/assets/js/icon_picker.js` (attach UI), the picker CSS in `editor/editor_base.html`, `editor/partials/question_form_modal.html` (strings, narrower Icon column), and tests. No model or data change.
