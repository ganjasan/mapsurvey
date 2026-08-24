## Context

`/editor/surveys/new/` (survey_create.html) currently runs two layouts off one form:

- **Desktop / flag off**: one screen — name + languages, AI brief panel (goal, audience,
  map target, use-case chips), "Generate draft" (primary) and "Create empty" (secondary).
- **`MOBILE_EDITOR_NAV` on, <1024px**: a wizard — step `goal` (brief + footer with
  "✨ Draft my survey" → draft path, ghost "Skip and start from scratch" → empty
  path) → step `map` ("Where?") → one Create button that dispatches to the chosen path
  (`wizardNext(p)` sets `path`, `wizard-create-btn` clicks `generate-btn` or `empty-btn`).
  Name and languages leave the flow (hidden inputs; `ensureName()` derives the name from
  the goal or "Untitled survey"). The hidden `map_lat/lng/zoom` are live-synced from the
  Leaflet map centre from page init, so they always hold a valid framing (Berlin default,
  possibly geolocation-adjusted) even if the map pane was never shown.

The empty path costs one click; the AI path costs a paragraph plus three more fields.
Both `ai_draft_requested` (PostHog, server-side) and `survey_created` with
`creation_method` already exist; nothing records that a creator saw the AI offer and
declined it.

Constraints: merges reach production within minutes (no staging gate); the create page is
the single entry point for every new creator; existing tests assert that "Create empty"
works with an untouched brief; `{% comment %}` blocks must be used for multi-line
template comments; PostHog client snippet is present on editor pages (gated by
`POSTHOG_PROJECT_KEY`) and absent on `/surveys/` and `/r/`.

## Goals / Non-Goals

**Goals:**
- Make the AI draft the path of least resistance without removing or hiding the empty
  path.
- Cut the visible brief to one field; keep the extra steering fields reachable.
- Stop forcing wizard users who chose the empty path through the "Where?" step.
- Measure the steering: who saw the intercept, who converted, who declined.
- One env-var kill switch over the new behavior.

**Non-Goals:**
- No change to server-side creation or generation endpoints, quotas, or the AI pipeline.
- No dark patterns: the empty path stays one extra click at most, and only when the
  creator has already written a goal.
- No example-brief chips and no AI entry point inside the empty editor (separate,
  already-discussed ideas — deliberately out of this change).
- No changes to the customer-facing `SurveyEvent` analytics system.

## Decisions

**D1. The intercept is client-side only.**
A `maybeOfferDraft(surface)` guard wraps both empty entries (desktop `#empty-btn`
click, wizard `wizardNext('empty')`). If the goal is non-empty, the flag is on, AI is
available, and the offer hasn't been shown this page load → `preventDefault`, render the
inline prompt, emit the `shown` event, return. "Generate draft" in the prompt routes to
the existing draft path (desktop: `#generate-btn` click; wizard: `wizardNext('draft')`);
"Create empty anyway" re-triggers the original empty flow, which now passes the guard
(once-per-page-load latch). *Why not server-side*: no state worth persisting, no
round-trip worth paying, and the existing "legacy POST without action → manual creation"
contract stays untouched. Alternative — a modal — rejected: heavier, and browser-dialog
patterns are banned in this codebase's UX reviews.

**D2. Disclosure via a `<details>` element, server-rendered open when dirty.**
Audience, map target, and use-case chips move inside
`<details class="ai-more"><summary>Add details (optional)</summary>…</details>`. The
`open` attribute is rendered by the template when any of those bound fields has a value
(form re-render after a validation error must not swallow filled inputs). Native
`<details>` needs no JS, is keyboard-accessible, and degrades to always-open without CSS.
The goal textarea gets `autofocus` (the name field is hidden under the wizard flag at
all widths, so focus cannot be contested; with the flag off, autofocus is not emitted —
the name field keeps first position).

**D3. Wizard empty path submits from step 1.**
`wizardNext('empty')` (after D1's guard) no longer calls `wizardGoto('map')`: it sets
`path='empty'`, runs `ensureName()`, and clicks `#empty-btn`. Map framing comes from the
already-synced hidden fields — the same values the map step would have started from. The
draft path is untouched: goal → map → create. The step-dots markup stays as-is (the
empty path simply never reaches the chrome that shows them).

**D4. One PostHog event, client-side: `ai_empty_intercept`.**
Properties: `outcome` (`shown` | `accepted` | `declined`) and `surface`
(`desktop` | `wizard`). Captured via `window.posthog && posthog.capture(...)` (same
guard as `_ai_feedback_strip.html`), so an unset key or a blocker degrades to silence.
Brief content is never attached. *Why one event with an `outcome` property rather than
three events*: the three are one interaction; trend/funnel breakdowns by property cover
every question we have. Downstream conversion is measured against the existing
`ai_draft_requested` and `survey_created` (`creation_method`) events, not duplicated
here. Reach stays on `$pageview` for `/editor/surveys/new/` — no new page-view event.

**D5. Kill switch: `CREATE_STEER_AI` env var, default on.**
Read in `settings.py` (same idiom as `MOBILE_EDITOR_NAV`), exposed through the existing
context processor, gating in the template: intercept JS, `<details>` collapse, autofocus,
and the wizard step-1 direct submit. Flag off reproduces today's markup and wizard flow
exactly. *Why one flag for all four*: they are one product bet; per-feature flags would
triple the template's conditional surface for no operational gain.

## Risks / Trade-offs

- [Intercept breaks the empty path (top of funnel)] → the guard's only side effect is
  `preventDefault` on the first qualifying click; every other path falls through to the
  browser-native submit. Tests cover: blank goal ⇒ no intercept; declined intercept ⇒
  empty survey created; flag off ⇒ no intercept markup at all. Kill switch reverts in
  one deploy-less env change.
- [`#empty-btn` is a submit button — a mis-ordered listener could both intercept and
  submit] → the guard runs in the capture phase (as the existing `ensureName` listeners
  do) and calls both `preventDefault` and `stopPropagation` when it fires.
- [Collapsed details hide fields a validation error refers to] → server renders `open`
  whenever any collapsed field is bound with a value or carries errors.
- [Wizard empty path submits a never-seen map framing] → identical to today's desktop
  behavior when the creator ignores the map; the framing is editable later in Survey
  settings. Accepted.
- [Autofocus scrolls the page on load on short mobile viewports] → step `goal` is the
  first screen and the textarea is at its top; acceptable. If it misbehaves, drop
  autofocus under the wizard only — it's a one-line gate.
- [One-event analytics undercounts if the page reloads mid-interaction] → accepted;
  the numbers are directional, the authoritative outcome is `survey_created`.

## Migration Plan

Template + settings only; no migrations, no new dependencies. Deploy = merge to master.
Rollback = set `CREATE_STEER_AI=False` on the web service (no redeploy of code needed)
or revert the merge. Guard test for template comments runs right after template edits.

## Open Questions

- None blocking. Copy for the intercept prompt ("You already described your project —
  draft it with AI (~10 s)?") to be finalized in review.
