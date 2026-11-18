## MODIFIED Requirements

### Requirement: Submit buttons show a busy state and cannot send twice
A button that sends a request SHALL show a busy state: when a form is submitted natively or
over HTMX by a submit button, or an HTMX button with a non-GET verb sends its request, that
button SHALL at once get `aria-busy="true"` and the class `is-busy` and show a spinner in place of its leading icon (or prepended when it has none) while
keeping its label, and SHALL be disabled on the next tick — after the event dispatch completes —
so a native submitter's `name`/`value` still reach the server and delegated click handlers
(Bootstrap `data-toggle`) still see the click. An HTMX button with a GET verb SHALL NOT get the
busy state. A second native `submit` event on the same form while the
first is in flight SHALL be `preventDefault`ed. The button SHALL be restored to its original
markup when the HTMX request completes (success or error), when the page is restored from the
back/forward cache (`pageshow` with `persisted`), or when the navigation watchdog (30 s) fires.
Programmatic HTMX submits (`htmx.trigger(form, 'submit')`) SHALL NOT be suppressed.
A button inside `[data-no-spinner]` (itself or an ancestor) SHALL get the busy state without
the spinner: its icon is left as it is and nothing is prepended.

#### Scenario: Double click on Save
- **WHEN** a creator double-clicks the question modal's Save button (HTMX submit)
- **THEN** one request is sent, the button is disabled with a spinner until the response arrives, then restored

#### Scenario: Enter twice on a native form
- **WHEN** a creator presses Enter twice in the sign-in form before the page unloads
- **THEN** the form is submitted once; the submit button is disabled and busy

#### Scenario: Submitter value reaches the server
- **WHEN** a native form is submitted by a button with `name` and `value` (an org switch)
- **THEN** the server receives that `name`/`value` pair

#### Scenario: Back button restores the page
- **WHEN** the creator navigates Back to a page that was left with a busy button and a visible bar
- **THEN** the bar is hidden and the button is in its original state

#### Scenario: A GET button that opens a modal
- **WHEN** a creator clicks a question's Edit button (`hx-get` plus `data-toggle="modal"`)
- **THEN** the modal opens and the button gets no busy state

#### Scenario: Section form autosave keeps working
- **WHEN** the section form autosaves through `htmx.trigger(form, 'submit')` several times in a row
- **THEN** every save is sent; no button is blocked

#### Scenario: A block library tile keeps its icon
- **WHEN** a creator clicks a tile in the block library of the report or Sites builder
- **THEN** the tile is disabled and busy until the page reloads, its icon square does not turn into a spinner, and the top bar shows progress
