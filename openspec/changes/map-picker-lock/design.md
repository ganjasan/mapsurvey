## Context

`MapPositionPicker` (one module, three call sites) treats the map centre as the position and saves every
settled move after 800 ms. That model is right when the creator is framing the map, and wrong when the map
is merely in the way of a scroll: on the two settings surfaces the map is 300–460 px of a scrolling column.

## Goals / Non-Goals

- Goal: a move of the settings map can only come from a creator who asked to move it.
- Goal: keep centre-is-position and autosave; no Save button returns.
- Non-goal: the section modal, the create page (`survey_create.html`, nothing is saved there until submit).
- Non-goal: undo / position history.

## Decisions

**Lock, not "Ctrl + scroll to zoom".** Turning off only the wheel leaves the touch drag (a page scroll that
starts on the map) and trackpad pinch; a modifier-key hint also means nothing on a phone. A lock closes
every accidental path with one rule and one visible control.

**The lock lives in the picker module** (`lock: true`), so both settings surfaces get it from one place and
the section modal opts out by not passing it. Locking disables the Leaflet interaction handlers and lays a
transparent overlay over the whole map container, above Leaflet's controls: zoom buttons and "My location"
are covered too, so the only thing a click on a locked map can do is unlock it. With the handlers off
Leaflet drops its `touch-action: none` classes, so a touch scroll over the map scrolls the page.

**Clicking anywhere on the locked map unlocks**, not only the button: a creator's first instinct is to grab
the map, and the click itself changes nothing.

**Re-lock is automatic**: "Done", a pointer press outside the map container, or the map leaving the
viewport (`IntersectionObserver`, when available). Without it a creator who framed the map once would be
back in the unprotected state for the rest of the visit.

**Programmatic moves are not locked.** Place search and the courtesy geolocation flight call
`setView`/`flyTo`, which do not go through the handlers. A chosen search result therefore still moves and
saves the position while locked — it is as deliberate as pressing the button.

## Risks / Trade-offs

- One more click before framing the map → accepted; the position is set once and read many times.
- A creator may not notice the button → the whole map is the click target and the button sits on it.
