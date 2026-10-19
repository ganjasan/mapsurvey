## Context

`IconPicker.attach(input)` used to wrap the value input with a preview square and a grid button. Its dropdown was `position: absolute` inside the wrapper, so it inherited the width of a 230 px table cell. #364 gave it a minimum width, but the three-control row and the missing "clear" stayed, and the owner found it still small.

## Decisions

**D1. The button is the picker, the input is a value carrier.** `input.hidden = true`, and the input remains the form field. Everything that reads or writes the value is unchanged: autosave, `serializeChoices()`, star-count defaults and Django validation. Every set goes through `setValue()`, which dispatches `input` so autosave and the live preview react. Code that changes the input directly also repaints the button, because the button listens for `input`.

**D2. Fixed placement, panel kept inside the wrapper.** The panel is not appended to `<body>`: Bootstrap 4's modal focus trap would pull focus back out of the search box. It stays in the wrapper with `position: fixed`, which is safe because `.modal.show .modal-dialog` has `transform: none`. `place()` runs on open, after every grid render (the panel is short while the catalog loads), and on resize and capturing scroll. Placement rules:
- below the button if it fits, else above;
- if neither fits, the larger side with `max-height` set to that space, so the panel never covers its button;
- clamped horizontally into the viewport.

Below 768 px the CSS bottom sheet wins and the inline styles are cleared.

**D3. Clearing has two doors.** "Remove icon" sits next to the search box and is visible only while there is a value. A "No icon" tile is the first cell while browsing; it is not shown while searching, so search results stay pure. Both call `setValue('')`.

**D4. Typed values without a text field.** If the query matches the value grammar (the same regexes as `marker_icons`), a "Use <value>" row appears and Enter applies it. Enter never submits the question form from the search box.

## Risks / Trade-offs

- [Creators who copied the class string from the field] → It shows as the button's tooltip, and "Use <value>" accepts a paste.
- [Strings are English-only] → The picker's strings were never in the catalogs ("Browse icons" included). Translating the whole picker is separate debt and is not widened here.
