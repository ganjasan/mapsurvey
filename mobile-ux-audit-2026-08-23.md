# Mobile UX/UI Audit — mapsurvey.org

Date: 2026-08-23. Viewport: 390×844 (iPhone 14), Playwright/Chromium.
Scope: landing → registration/login → demo survey flow → public results (`/r/`) → editor (`/editor`, audited on local dev at identical code, branch `feature/public-results-link-recovery`).

Screenshots: `.playwright-mcp/` in the repo checkout (landing-*, survey-*, register-full, login-full, results-*, editor-*).

---

## P0 — conversion / data-loss critical

### 1. Chat widget covers the Register button
On `/accounts/register/` at 375–390px the chat bubble sits directly on top of the right half of the primary **Register** button. Same widget overlaps landing headings and survey-editor preview content. This is the single worst finding: it physically blocks the tap that ends the registration funnel.
Fix: hide the widget on mobile for `/accounts/*` (or move it above the fold-bottom safe area / left side on small viewports).

### 2. Failed survey submission is silent
When the `Finish` POST fails (flaky mobile network — reproduced during audit), htmx fires `sendError` and **nothing appears in the UI**. The respondent taps Finish, nothing happens, answers are lost if they leave. Mobile networks make this a common case.
Fix: htmx error handler → visible toast "Couldn't submit, check connection — Retry", keep the button enabled.

### 3. `/surveys/track/event/` returns HTTP 400 on every event
Console showed consistent 400s from the respondent event tracker during a real demo-survey session (before any network flake). If reproducible, the *sellable* SurveyEvent analytics is not recording sessions like this one. Needs payload/CSRF investigation server-side.

## P1 — major UX

### 4. Landing content invisible without scroll-triggered JS
All sections below the hero start at `opacity: 0` and reveal on scroll. With slow/failed JS the page below the hero is blank; prerender/screenshots capture nothing.
Fix: render visible by default; add animation class only when IntersectionObserver is available; respect `prefers-reduced-motion`.

### 5. Survey: no confirmation after a geometry is applied
After crosshair → Apply → sub-questions → ✓, the panel reopens looking exactly as before answering ("Drop a pin…" card, no counter). Respondent can't tell the answer was recorded; risks duplicates and confusion before pressing Next.
Fix: show "1 place added ✓" chip on the card (+ edit/delete affordance).

### 6. Survey: instruction copy contradicts the actual mobile interaction
Card says "Click or tap the map to place a marker", but tapping the map does nothing until the card itself is tapped (verified). Real flow is: tap card → pan map under fixed crosshair → Apply. Line/polygon copy is likewise desktop-flavored ("Click points on the map … press Finish").
Fix: mobile copy "Tap here, then position the pin on the map"; grammar bug "Draw **a routes** you often walk".

### 7. Sub-question popup collisions and desktop idioms
The attributes popup (after placing a pin) is overlapped by the map search button (z-index collision hides part of the question text). Actions are three icon-only buttons (trash/edit/check) with no labels; native ~13px checkboxes; resizable textarea.
Fix: raise popup z-index above map controls, label the confirm button ("Save"), enlarge touch targets to ≥44px.

### 8. Panel collapse chevron is a 17×20px tap target
The only way to see the map from the question panel is a tiny « chevron. Also the first-screen layout (panel covering the whole map except a ~50px strip) doesn't communicate that a map is behind.
Fix: bottom-sheet layout on mobile (panel as a drag-handle sheet over the map) or at minimum a ≥44px collapse control.

### 9. `/r/galanthus-locations/` — "36 responses" + "No results to show yet"
A published, sitemap-indexed results page with a big response counter and an empty body looks broken and is publicly linkable.
Fix: don't include block-less pages in sitemap / don't allow publish with zero blocks, or auto-draft blocks (#130 work).

### 10. Editor on mobile: honest fallback needed
`/editor/surveys/<uuid>/` has 719px content width on a 390px viewport: toolbar wraps to 4 rows ("Logout" on its own line), the read-only banner's lock icon and "READ ONLY" chip overlap the message text and the right-side button is clipped, the three-pane IDE leaves a ~150px preview column (one word per line). Responses → Data shows only checkbox/eye/trash/#id columns — answers are off-screen; the Violations panel eats half the width; pagination is clipped.
Recommendation: don't make the editor responsive now. Add a <768px notice "The editor is designed for desktop" and keep Dashboard, read-only Responses summary, Share and Public-results preview usable.

### 11. Survey pages have empty `<title>` and no `lang` attribute
Tab shows blank title; screen readers get no language. Set title = survey name, `lang` = survey content language.

## P2 — minor

- **Hero CTA hierarchy**: "Join our Discord" ranks above "Try Demo Survey"; demo drives the funnel — swap.
- **Mobile nav menu**: opens inline (not overlay) with page content visible below, items center-aligned inconsistently, Solutions pre-expanded, hamburger icon doesn't become ✕.
- **Product screenshots on landing** are desktop UI shrunk to ~340px — unreadable; expand affordance (↗) is small.
- **Non-geo section (About You)** still shows the map strip + pin drawing control — noise; hide geo controls on sections without geo questions.
- **Draw-mode tooltip** ("Click to start drawing a line.") is clipped at the top edge; disabled "Finish drawing" is low-contrast grey-on-green.
- **Section URL doesn't change** when moving between sections via Next (stays on first section slug until /thanks/) — refresh/back behavior unclear.
- **Dashboard**: 77 surveys rendered as one 20,000px page, no pagination/lazy load.
- **Login page** header still shows a "Login" link.
- **Rating 1–5 buttons** (~48px) and radio touch targets in section 4 are good — keep this pattern.

## What was NOT verified
- Actual touch line/polygon drawing (synthetic events rejected by Leaflet.draw — automation limitation, not a product bug).
- iOS Safari specifics (safe-area, 100vh, rubber-banding) — Chromium emulation only.
- Editor audited on local dev data; django-debug-toolbar artifacts in some screenshots are local-only.

## Test data created during audit
- Prod: one demo-survey session (pin in Bishkek, "Nice park", one radio answer) — normal demo traffic.
- Local dev DB: user `uxaudit`, password reset on local `admin`/`import_admin`. No prod accounts created.

---

## Scope decision (2026-08-23, owner)

The editor IS in scope for the adaptive refactor — the "desktop-only banner" fallback
recommendation above is REJECTED. Rationale: the existing three-pane layout (sections /
question editor / preview) maps naturally onto mobile patterns — panes become full-screen
tabs or a drill-down flow; the preview pane will render the (newly adaptive) respondent
page as-is. Known hard spots to size in design.md: touch drag-and-drop reordering
(up/down buttons as fallback), the 4-row toolbar header, and the Responses Data table
(candidate for a later iteration).
