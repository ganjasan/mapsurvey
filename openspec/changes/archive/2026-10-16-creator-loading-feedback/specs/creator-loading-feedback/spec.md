## ADDED Requirements

### Requirement: One shared loading-feedback partial on creator pages
Every page built on `base.html` or `editor/editor_base.html` SHALL include the partial
`partials/_loading_feedback.html`, which loads one stylesheet (`css/loading-feedback.css`) and one
script (`js/loading_feedback.js`). The respondent base `base_survey_template.html` and the
marketing base `base_landing.html` SHALL NOT include it. The script SHALL work on a page with or
without HTMX loaded.

#### Scenario: Creator bases include the partial
- **WHEN** `base.html` or `editor/editor_base.html` is rendered
- **THEN** the HTML references `js/loading_feedback.js` and `css/loading-feedback.css` exactly once

#### Scenario: Respondent and marketing bases do not
- **WHEN** `base_survey_template.html` or `base_landing.html` is rendered
- **THEN** the HTML does not reference `js/loading_feedback.js`

### Requirement: Top progress bar on navigation
A creator page SHALL show a thin progress bar fixed to the top of the viewport, starting
approximately 150 ms after a same-origin navigation starts, and SHALL NOT show it when the page
unloads before that delay. A navigation is a plain left click without modifier keys on an `<a href>` that is same-origin, not a fragment, not `javascript:`/`mailto:`, has no
`download` attribute, no `target` other than `_self`, no `data-toggle` and no `hx-*` attribute,
or a native form submit whose event was not `preventDefault`ed and whose form has no `target`
other than `_self`. An element with `data-no-progress` on itself or an ancestor SHALL NOT start the
bar. A click or submit that another handler cancelled (`defaultPrevented`) SHALL NOT start the
bar.

#### Scenario: Slow page shows the bar
- **WHEN** a creator clicks the Responses tab and the next page takes 2 s to arrive
- **THEN** a bar appears at the top of the current page within about 150 ms and stays until the page unloads

#### Scenario: Fast navigation stays silent
- **WHEN** the next page arrives in under 150 ms
- **THEN** no bar is shown

#### Scenario: Intercepted click
- **WHEN** a click on a link is `preventDefault`ed by another handler (a gate modal, a dropdown toggle)
- **THEN** no bar is shown

#### Scenario: New-tab clicks, downloads and anchors
- **WHEN** the click carries Ctrl/Cmd/Shift/Alt, or the link has `download`, `target="_blank"`, a `#` fragment href or a different origin
- **THEN** no bar is shown

#### Scenario: Opt-out attribute
- **WHEN** a link or form, or one of its ancestors, has `data-no-progress`
- **THEN** no bar is shown for it

### Requirement: Top progress bar on long HTMX requests
For an HTMX request sent from a creator page (`htmx:beforeSend`), the page SHALL show the same
bar if the request has not completed (`htmx:afterRequest`, which also fires on error, abort and
timeout) within approximately 300 ms, and SHALL hide it when the last in-flight request
completes. Requests issued by an element whose `hx-trigger` contains `every` (polling) SHALL
NOT show the bar. Overlapping requests SHALL share one bar. A request that never reports back
SHALL release its hold on the bar after 60 s.

#### Scenario: Slow HTMX pane
- **WHEN** a Responses pane requested over HTMX takes 1 s
- **THEN** the bar appears after about 300 ms and disappears when the response is swapped in

#### Scenario: Failed HTMX request
- **WHEN** an HTMX request ends in a network error or a 500
- **THEN** the bar disappears as it would on success

#### Scenario: Polling does not pulse the bar
- **WHEN** the import-jobs card polls every 3 s
- **THEN** no bar is shown for those requests

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

### Requirement: Script API for hand-written requests
The script SHALL expose `window.LoadingFeedback` with `start(delayMs)` and `done()` (counted, so
overlapping holds keep one bar), `busy(button)` returning a release function, and `reset()`.

#### Scenario: Manual hold
- **WHEN** a script calls `LoadingFeedback.start()` twice and `done()` once
- **THEN** the bar remains visible until the second `done()`

### Requirement: Bar presentation
The bar SHALL be 3 px high, fixed at the top of the viewport, `z-index` above Bootstrap modals
and the mobile editor overlays, coloured with the editor accent (`#4f46e5`), `aria-hidden`, and
SHALL show without the trickle animation under `prefers-reduced-motion: reduce`.

#### Scenario: Submit from inside a modal
- **WHEN** a form inside a Bootstrap modal is submitted and the bar shows
- **THEN** the bar is visible above the modal backdrop

### Requirement: In-app changelog entry
The change SHALL ship a `survey/changelog/` entry announcing the loading bar and busy buttons.

#### Scenario: Entry loads
- **WHEN** `ChangelogEntriesTest` parses every entry
- **THEN** the new entry parses with `kind: new`
