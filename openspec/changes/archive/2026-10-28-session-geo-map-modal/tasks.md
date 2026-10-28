## 0. Working checkout

- [x] 0.1 Implement from a worktree branched off `origin/master`, not from the current checkout — it is 27 commits behind and lacks `openspec/specs/responses-detail-drawer/` and the whole V2 dashboard: `git worktree add ../Mapsurvey-session-geo-map -b feature/session-geo-map-modal origin/master`
- [x] 0.2 Bootstrap it: `env` symlink, `.env` copy, a fresh `PORT_OFFSET` in `.env.ports` (update the registry comment), `collectstatic`
- [x] 0.3 Confirm the bug reproduces there first: open a response with geo answers and observe the empty box under Notes — do not start fixing before seeing it

## 1. Survey the blast radius

- [x] 1.1 Grep every partial rendered into `#rv2-drawer-body` for `sessionDetailModal`, `.modal(`, `shown.bs.modal` — report anything else the V1→V2 move left behind (design risk 1)
- [x] 1.2 Determine whether `format_session_answers`' `geo_features` feeds anything besides the detail surface; record the answer in design.md's Open Questions
- [x] 1.3 Decide and record the behaviour at 768–1199px and below 768px, where the detail surface is an overlay/full-screen rather than a drawer

## 2. Feature payload and row values

- [x] 2.1 Add `object_id` (geo `Answer.pk`) and `label` to each feature's properties in `SurveyAnalyticsService.format_session_answers`, leaving `question`, `type`, `attributes` untouched
- [x] 2.2 Move the numbered label ("point feature 2") off the row's display value and onto `label`
- [x] 2.3 Make the row's display value use the attribute-table formatter (coordinates / vertex count) so the two surfaces agree for the same answer
- [x] 2.4 Tests: feature properties for a question with several objects (distinct `object_id`, distinct `label`); `responses-geo-subanswers`' existing properties still present; row value for point and for polygon

## 3. Revive the drawer preview

- [x] 3.1 Expose the partial's `initMiniMap` as a named routine both surfaces call, disposing any existing instance first
- [x] 3.2 V2 initialisation happens in the partial when no `#sessionDetailModal` exists — the host-page `htmx:afterSwap` binding was rejected during implementation (see design decision 1)
- [x] 3.3 Keep the pre-V2 modal binding working (kill switch off must behave exactly as before)
- [x] 3.4 Verify in a browser: preview renders for a geo response; steps correctly through prev/next; no preview at all for a response without geo answers

## 4. Full-size session map

- [x] 4.1 Add the modal markup to `analytics_dashboard_v2.html` near `validationSettingsModal`, reusing `{% include "partials/basemap_layers.html" %}`
- [x] 4.2 Build it from the geo data already in the detail surface — assert no additional request fires when it opens
- [x] 4.3 Colour per question plus a legend naming the questions, following the Map pane's convention
- [x] 4.4 Popups: object label and its `attributes` name/value pairs, escaped; the embedded payload not marked safe
- [x] 4.5 Entry point A — activating the geo preview opens the map fitted to all objects
- [x] 4.6 Entry point B — activating a geo answer row opens the map zoomed to that object with its popup open, keyed by `object_id`
- [x] 4.7 `invalidateSize()` once visible; dispose the instance on close so repeated opens and prev/next do not accumulate detached maps
- [x] 4.8 Read-only: no draw/edit/delete controls reachable

## 5. Regression guard and tests

- [x] 5.1 Test asserting the dashboard template for the active `RESPONSES_V2` state contains the container the partial's initialiser binds to
- [x] 5.2 Test that a response with geo answers renders the preview container and one without does not
- [x] 5.3 Test that a sub-answer containing markup reaches the page escaped
- [x] 5.4 GIVEN/WHEN/THEN docstrings throughout; full suite after the change: 1734 tests, OK (1 skipped). No separate pre-change baseline was captured — an all-green run makes the delta moot

## 6. Browser verification before merge

- [x] 6.1 Exercise the failure modes this change introduces — map in a hidden container, leaked instances across prev/next and repeated opens, popup escaping — in a real browser, since a dead control passes every Django test
- [x] 6.2 Check the surface at the three breakpoints per the decision recorded in 1.3
- [x] 6.3 Screenshot the before/after for the owner

## 8. Drawer scrolling (owner-reported, same review round)

- [x] 8.1 Diagnose: `.rv2` uses `min-height`, so the workspace grows with content and the drawer's `overflow-y: auto` never engages
- [x] 8.2 Measure the symptom the owner saw — table footer at 1162px in a 950px viewport
- [x] 8.3 Switch `.rv2` to `height: calc(100vh - 56px)`; verify panes still scroll internally rather than clipping (Overview/Map/Responses/Charts/Performance all clean)
- [x] 8.4 Verify across viewports: 1600x950, 1600x700, 1280x800 fixed; below 1200px the surface is an overlay and is unaffected
- [x] 8.5 E2E regression test; confirmed it fails with `min-height` restored and passes with the fix
- [x] 8.6 Record the requirement in the `responses-detail-drawer` delta — the original spec never said how the surface scrolls

## 9. Wrap up

- [x] 7.1 Fold the answers from tasks 1.2 and 1.3 back into design.md, removing them from Open Questions
- [x] 7.2 `openspec validate --changes session-geo-map-modal --strict`
- [ ] 7.3 Offer commit / push / PR — do not perform any of them unasked
