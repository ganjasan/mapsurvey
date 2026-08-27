# Proposal: fix-preview-double-load

## Why

Every entry into the editor's Live preview loads the iframe twice: the section-click
handler (and the initial page template) sets `iframe.src`, then the global
`htmx:afterSwap` listener — which excludes only the two modal bodies — fires for the
`#section-content` swap and reloads the same URL ~0.5–1s later. Confirmed locally
(network log shows two identical GETs per section switch and per editor open) and in
production PostHog session replays: on the 0.5-CPU Render instance the second
navigation aborts the first document mid-render and pins a blank white iframe on
screen for the whole second wait — replays show a 43-second white hang, dead-clicks
into the editor under the preview, and a frustration-scored session of 7/10 from an
active user. Even legitimate reloads (autosave-driven) flash white with no signal
that loading is in progress, which replays show users interpreting as breakage.

## What Changes

- Eliminate the duplicate load: the `htmx:afterSwap` preview-refresh listener no
  longer fires for swaps into `#section-content` (the click handler and
  `sectionSaved`/`questionSaved` events already cover those paths). One user action
  produces exactly one preview GET.
- Double-buffer the preview iframe: a reload renders into a hidden iframe and swaps
  it in only when loaded, so the previous preview stays visible during the entire
  wait — the white-document phase never reaches the screen.
- Loading indicator: while a reload is in flight, the preview panel shows a loading
  overlay (spinner) over the still-visible stale content; it hides when the new
  document swaps in. Waiting is distinguishable from breakage.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `survey-editor`: the "Live inline preview" requirement gains explicit behavior —
  single load per trigger, stale content stays visible during refresh behind a
  loading indicator, no blank-iframe phase during section switches or
  autosave-driven refreshes.

## Impact

- `survey/templates/editor/survey_detail.html` — preview iframe markup (buffer
  pair + overlay), section-click handler, `refreshPreview()`, `htmx:afterSwap`
  listener.
- `survey/assets/css/` — overlay/spinner styles (then `collectstatic`).
- No server-side, model, or URL changes; respondent pages untouched.
- Production effect: halves preview render load on the web instance from editor
  usage; removes the dominant frustration pattern found by Replay Vision scanners.
