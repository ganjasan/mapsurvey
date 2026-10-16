## Context

Creator pages are served from two base templates: `base.html` (dashboard, organisation pages,
sign-in/registration, preferences) and `editor/editor_base.html` (Build, Settings, Share,
Responses, Public results, layer editor). `editor_base.html` loads HTMX 1.9.10; `base.html` does
not, but the dashboard (`editor.html`) loads it in its own `extra_scripts` block. Respondent pages
use `base_survey_template.html` and are out of scope (issue #337).

Three kinds of request leave a creator page today:

1. **Native navigation** — `<a href>` links (tabs in `_survey_nav_tabs.html`, dashboard cards,
   menu items) and plain `<form method="post">` submits (settings, share, create, org,
   sign-in, delete/purge/restore).
2. **HTMX requests** — `hx-post`/`hx-get` on forms and buttons (question modal Save/Create,
   section form, Responses panes, import cards polling every 3 s, generation status polling).
3. **Hand-written `fetch`** — autosave (`editor_autosave.js`, `panel_autosave.js`), comments,
   clipboard, layer editor, the question modal's Apply (which already shows its own spinner).

No shared indicator exists for any of them. The question modal's Apply button and the analytics
table engine have one-off spinners; everything else shows nothing.

## Goals / Non-Goals

**Goals:**
- One script and one stylesheet, included once per base template, that cover kinds 1 and 2
  without any page knowing about them.
- Fast navigations stay silent (bar after ~150 ms for navigation, ~300 ms for HTMX), so the bar
  is a sign of waiting, not a flash on every click.
- A submit button cannot send its form twice: disabled and visibly busy from the first click.
- Never leave the page in a stuck state: no bar that stays forever, no button that stays
  disabled after Back, after an HTMX error, after a cancelled navigation.
- A small public API (`window.LoadingFeedback`) so kind 3 call sites can opt in later without a
  second implementation.

**Non-Goals:**
- Retrofitting every `fetch` call site. Autosave has its own saved/saving indicator by design
  (`EDITOR_AUTOSAVE`); the Apply button keeps its spinner.
- Respondent and marketing pages.
- A progress bar for the AI draft wait (own progress screen) or for file downloads.
- Changing any button's label or adding translations: the busy state swaps the icon, not the
  text.

## Decisions

**D1 — One partial in the `<head>` of both bases, script creates its own DOM.**
`partials/_loading_feedback.html` links `css/loading-feedback.css` and loads
`js/loading_feedback.js`. The script appends the bar element to `document.body` on first use,
so the partial has no body markup and can sit in `<head>` where both bases already list their
assets. *Alternative:* a body-end include with inline markup — rejected because `base.html`
and `editor_base.html` end their bodies differently and an include in the head is the pattern
`_analytics.html` already uses.

**D2 — Listen on `window` in the bubble phase for `click` and `submit`.**
Handlers registered on elements and on `document` run before a `window` bubble listener, so
`event.defaultPrevented` is final when we read it: a link the gate modal intercepts, a form a
`confirm()` cancelled, a form HTMX took over (HTMX calls `preventDefault`) — none of those start
a navigation bar. *Alternative:* capture-phase listener plus `setTimeout(0)` re-check —
rejected as more fragile (a handler can call `stopPropagation`, which also, correctly, means
"not ours").

**D3 — Link filter.** A click starts the bar only when it is a plain left click (no modifier
keys), on an `<a href>` whose URL is same-origin, not a fragment (`#…`), not `javascript:` or
`mailto:`, with no `download` attribute, no `target` other than `_self`, no `data-toggle`
(Bootstrap dropdowns and tabs), no `hx-*` attribute (HTMX events cover it), and no
`data-no-progress` on it or an ancestor. The `data-no-progress` escape hatch is the only
per-page knob.

**D4 — Native submit: busy the submitter, disable it on the next tick, suppress re-submits.**
`event.submitter` names the button (fallback: the focused submit button of the form, then the
first one). Disabling happens in `setTimeout(0)` for every busy button, native or HTMX: the HTML
spec drops a disabled submitter from the form data set (views such as the publishing widget and
`org_switch` read the button's `name`/`value`), and jQuery skips delegated click handlers on an
element that is disabled when the click is dispatched — a synchronous disable broke Bootstrap's
`data-toggle="modal"` on the question Edit button, found in the browser check. The form gets a `data-ms-submitting` flag; a second `submit` event while it is
set is `preventDefault`ed. Forms with `target` other than `_self` or `data-no-progress` are
skipped. Nothing blocks programmatic HTMX re-submits (`htmx.trigger(form, 'submit')` is the
section form's autosave and must keep working).

**D5 — HTMX: `htmx:beforeSend` starts, `htmx:afterRequest` ends, per `xhr`.**
`htmx:beforeRequest` can be cancelled by another listener (then `afterRequest` never fires), so
the bar starts on `htmx:beforeSend`, which fires right before `xhr.send`. `htmx:afterRequest`
fires on load, error, abort and timeout, so it is the single end. The two are paired through a
flag on `event.detail.xhr`, and a 60 s safety timer releases a request that never reported
back. Requests from elements whose `hx-trigger` contains `every` (polling) are skipped: the
import cards and the generation status poll every few seconds and must not pulse the bar. The
busy button is `detail.elt` when it is a button whose verb is not GET, else
`detail.requestConfig.triggeringEvent.submitter` for a submitted form; other triggers (a
button that GETs a pane or a modal body, a `change` on a select, a `load` pane) get the bar
only — they send nothing that could be sent twice.

**D6 — Reset on `pageshow` with `persisted`, and a 30 s navigation watchdog.**
Back/forward cache restores the page exactly as it was — bar visible, button disabled — so
`pageshow` with `persisted === true` resets both. A navigation that never unloads the page
(the server answered with a download, the user pressed Escape) is reset by a 30 s watchdog;
a genuinely slower page loses its bar at that point, which is the lesser harm.

**D7 — Busy look: swap the leading icon, keep the label.**
If the button's first element child is a Font Awesome `<i>`, its classes are replaced by
`fas fa-spinner fa-spin`; otherwise a spinner is prepended. The label stays, so the button keeps
its width and its meaning; `disabled` and `aria-busy="true"` are set, class `is-busy` is added.
Release restores the original icon classes or removes the prepended spinner. *Alternative:*
replacing the label with "Saving…" — rejected: needs translations and changes button widths.

**D8 — Bar look.** Fixed, top, 3 px, `#4f46e5` (the editor's `--accent`), `z-index: 2000`
(above Bootstrap modals at 1050 and the mobile overlays at 700/800, so a submit from inside a
modal is visible). Shown at 30 % width, trickles towards 90 % while waiting, jumps to 100 % and
fades on completion. Under `prefers-reduced-motion` it shows without the trickle. The bar is
`aria-hidden`; a screen-reader user gets the button's `aria-busy` instead.

**D9 — API.** `window.LoadingFeedback = { start(delayMs?), done(), busy(button) → release(),
reset() }`. `start`/`done` are counted, so overlapping HTMX requests keep one bar until the last
one ends.

## Risks / Trade-offs

- [A view that reads the submitter's `name`/`value`] → disabling on the next tick (D4) keeps the
  submitter in the form data; a test asserts the `setTimeout` placement in the source.
- [An HTMX swap replaces the busy button before release] → release is a no-op on a detached
  element; the new markup arrives in its normal state.
- [A link that opens a download (`download_data`) without the `download` attribute] → the bar
  stays up to the 30 s watchdog. The export dialog navigates through `window.location`, which
  does not fire `click`, so the common path is unaffected; `data-no-progress` is the fix for a
  specific link.
- [Section form autosave pulses the bar on slow saves] → only past 300 ms, and the autosave is
  an honest save; accepted. If it proves noisy, `data-no-progress` on that form is one attribute.
- [Login page double-submit after a password-manager autofill] → the busy state applies there
  too (it extends `base.html`); the suppression is per form, so a second account form on the
  page is independent.

## Migration Plan

No data or settings change. Deploy = merge. Rollback = revert the two includes; the static
files are inert when not included.

## Open Questions

None blocking. Whether the autosave `fetch` call sites should adopt `LoadingFeedback.busy`
is left to a follow-up once the bar is in production.
