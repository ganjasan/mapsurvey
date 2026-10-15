## Context

Today's entry into the product is one page. `views.editor` redirects an organization with
no surveys to `/editor/surveys/new/?welcome=1`; "+ New Survey" links there too. That page
(`editor/survey_create.html`, `editor_views.editor_survey_create`) carries the AI brief,
a "Skip and start from scratch" button and a Leaflet picker whose first `setView` is
`[52.52, 13.405]` — Berlin — followed by an unexplained `navigator.geolocation` request
on load with a 5-second timeout. The AI path posts the picker's hidden `map_lat/lng/zoom`
and `map_touched`; `survey/ai/tasks.py` overrides them with a geocoded brief location only
when the brief names a place and the creator did not frame the map. So a brief about
"our neighbourhood" with the permission refused yields a draft that opens on Berlin.

`CreatorPreferences` (OneToOne to the user, `ui_language`, `changelog_seen`,
`changelog_cards`) is where a creator's own choices live. `docs/mcp.md` (untracked)
describes an MCP server at `mcp.mapsurvey.org` with a token page at
`/editor/account/mcp/`; neither exists (#306). Production sits behind Render's Cloudflare
edge: `CF-Connecting-IP` is trusted under `CLOUDFLARE_TRUSTED`, and the same edge sends
`CF-IPCountry`; city-level headers are a setting on an account we do not have.

Constraints that shape the design: the public repo rule (no personal data in events),
`MOBILE_EDITOR_NAV` (the start page must work below 768 px as a normal page, not a pane),
both base templates carry global creator chrome (`base.html` for the dashboard,
`editor/editor_base.html` for everything else — a menu item added to one is missing from
the other), and the `RussianLandingHreflangTest`-style discipline: new creator-facing
strings go through `{% trans %}`.

## Goals / Non-Goals

**Goals:**
- One page where a creator chooses how to start, on the first visit and on demand later,
  with the choice remembered server-side.
- An empty survey in one request from that page, opening the editor with a map that is
  already near the creator.
- One ordered, testable chain for "where should this map open", used by every creation
  path, with its outcome measurable.
- A real URL and a demand signal for the agent path before the server exists, so #306
  lands into a place that already has an entrance.

**Non-Goals:**
- The MCP server, tokens, and the agent hand-off (prefilled prompt + waiting for the
  survey to appear). #306 and a follow-up change.
- City-level IP geolocation. The browser gives a better point when the creator agrees;
  the country rung is the honest server-side limit without a GeoIP dependency.
- Changing the respondent map fallback or `SurveyHeader` defaults.
- A picture per card. Cards ship with an icon and copy; illustrations are a later,
  separate decision.

## Decisions

### D1 — A dedicated start page, not a modal on the dashboard
`GET /editor/surveys/start/` (`editor_survey_start`) renders three cards. A page, because
it is the redirect target for an empty organization (a modal has no URL to redirect to),
it must work on a phone as a full screen, and the create page needs a plain link back to
it. Alternative considered: cards inlined into the dashboard's empty state. Rejected —
the empty state is reached only through `?dashboard=1`, and the choice must also be
reachable by a creator with forty surveys.

The empty-organization redirect in `views.editor` targets the start page with
`?welcome=1` (the create page's `welcome` branch moves with it: "Skip to dashboard" with
`?dashboard=1`). Viewers are exempt as before. The start page requires the `editor` role.

### D2 — Three cards, two of them actions, one of them a door
- *Start from scratch* — a `<form method="post">` to `editor_survey_create_blank`.
  POST, never GET: a link the browser prefetches or a crawler follows must not create
  surveys.
- *Draft with AI* — a link to `/editor/surveys/new/?from=start`. The create page under
  `from=start` replaces "Skip and start from scratch" with a link "Start another way"
  back to the start page: the creator just chose AI; offering the empty path again on
  the next screen is noise, and the way back covers a change of mind. Without the
  parameter the create page is unchanged for old links and scripts. When no LLM
  provider is configured (`ai_client.provider_configured()` false) the card renders
  disabled with "Not available on this server", matching what the create page already
  does.
- *Connect your AI agent* — inert: a `div` with `aria-disabled`, no link, no selection,
  dimmed and taped over with *Coming soon* (owner decision 2026-10-14: the card exists to
  say the path is coming, not to be clicked). The agent page (D6) is reached from the menus.

Copy per card is one line of what happens plus one line of who it is for; the
chosen card shows a short paragraph underneath (the "life path" pattern the owner
pointed at), on wide screens; on phones the paragraph sits inside each card.

### D3 — The remembered default lives in `CreatorPreferences`
`survey_start_default = CharField(choices=('', 'blank', 'ai'), default='')`. A route
preference, not cosmetics, so it follows the creator across devices; `localStorage`
(`EditorConfirm`) stays for confirmation suppression. The checkbox "Always start this
way" sits on the two actionable cards and posts with the card's action: the blank form
carries it as a field; the AI card becomes a tiny POST form too (`action=ai`) when the
box is ticked, so the preference is written by the start view and the creator is then
redirected to the create page. One writer: `editor_survey_start` (POST) and
`editor_survey_create_blank` both call `preferences.set_survey_start_default(value)`.

Routing by default: the dashboard's "+ New Survey" is rendered from a context value
`survey_start_default` (a tiny context processor over `request.user.preferences`, or a
template tag — processor, since `base.html` and `editor_base.html` both need it):
- `''` → `<a href="{% url 'editor_survey_start' %}">`
- `'ai'` → `<a href="{% url 'editor_survey_create' %}">`
- `'blank'` → a `<form method="post">` button to `editor_survey_create_blank` — the
  same one-click the card gives, with the geolocation step of D5.
The start page is always reachable: the ⋯ menu on the dashboard gets "Start another
way…", the create page's `from=start` link covers the AI side, and the start page itself
shows "Your default: … · Clear" when one is set (POST `action=clear`).

Alternative considered: making "+ New Survey" a dropdown. Rejected — one click must stay
one click, and a dropdown hides the choice instead of presenting it.

### D4 — Blank creation is the existing empty path, extracted
`editor_survey_create` keeps its `action=empty` branch; the survey-building block
(header, `SurveyCollaborator(owner)`, section `S1`, `SURVEY_CREATED`) moves into a
module-level helper `_create_blank_survey(request, *, name, languages, start, surface)`
that both the create page and `editor_survey_create_blank` call, so the two can never
drift. The new endpoint fills in:
- `name`: `_('Untitled survey')` under the creator's UI language. Content, renamed in
  the editor header (`SurveyRenameForm`). `max_length=45` and `url_name_validator`
  (`\w`) are satisfied in every catalog; a test asserts it for each `LANGUAGES` entry.
- `available_languages`: `[ui_language]` when the creator's UI language is a key of
  `settings.LANGUAGES`, else `['en']`. One language is the right first step; Survey
  settings adds more.
- `start`: `map_start.suggest_start_position(request, browser=<posted lat/lng/zoom>)`
  (D5); the survey always gets a position, so the editor's picker opens there.
- `surface='start_blank'`; the create page passes `'create_page'`.
It redirects to `editor_survey_detail`. Role `editor` or above, enforced like the create
view.

### D5 — `map_start.suggest_start_position`: an ordered chain with a named outcome
```
StartPosition(lat, lng, zoom, source)
sources, in order:
  'browser'     posted lat/lng (+zoom, default 13) — only ever present when the
                browser's permission was already granted or was asked tied to a click
  'org_survey'  start_map_postion of the newest canonical, non-deleted survey in the
                active organization that has one (zoom: its own, else 12)
  'country'     CF-IPCountry (only under CLOUDFLARE_TRUSTED) else the region subtag of
                the first Accept-Language entry (never `en-US`: the stock-browser default
                put the owner in Kansas on the dev stand) → country centroid, zoom 5
  'world'       (20, 0), zoom 2
```
`country_centroids.py` is a dict of ISO 3166-1 alpha-2 → (lat, lng), roughly 250
entries, hand-maintained; a test asserts every `CF-IPCountry` value we have seen in
tests resolves and that unknown codes fall through to `world`. The chain never raises
and never performs I/O beyond one indexed query. `org_survey` is per organization, not
per creator: a consultant's second workspace has its own city, and an editor who has
not created anything still gets the workspace's map.

Browser position, two rules. (1) Nothing asks for permission on page load; the current
on-load request on the create page is replaced by a `navigator.permissions.query`
probe that reads the position silently only when the state is `granted`. (2) Permission
is asked tied to a click: the *Start from scratch* form's submit handler asks when the
state is `prompt`, with a 3-second ceiling, then submits with or without coordinates;
the create page keeps its on-map "My location" button and adds, above the map, a
one-line hint with a "Use my location" link that is shown only when the server source
is `country` or `world`. Browsers without the Permissions API (older Safari) are
treated as `prompt` on the start page and as `denied` on the create page (no silent
read). The start-page card copy says the map will open on the creator's location.

The create page's first `setView` uses the server suggestion (the view calls the chain
with no browser input and passes `initial_lat/lng/zoom/map_source` to the template);
the hidden `map_source` field posts back and `_start_survey_generation` /
`_create_blank_survey` put it on `survey_created`. Because the AI path reads the same
hidden fields, a brief with no place now materializes on the suggestion rather than on
Berlin; `tasks.py` is untouched.

The respondent fallback at `views.py` (Berlin) stays: no survey created after this
change lacks a position, and the old rows are the owner's to fix in settings.

### D6 — `/editor/account/mcp/` ships as a page with a signal, not a disabled card
`editor_account_mcp` (login required, no org role needed — the token will be personal)
renders `editor/account_mcp.html`: three short paragraphs (what an agent can do, what it
cannot see, when), one example prompt, and a POST button "Tell me when it's ready" that
sets `CreatorPreferences.agent_access_requested_at = now()` (idempotent; the page then
shows "We'll email you") and emits `agent_access_requested`. The timestamp is a
`DateTimeField(null=True)`: it is the mailing list for the launch, and #306 reads it. The
page is linked from the account menu in both bases ("AI
agents & MCP" + `soon` badge) and the "?" menu ("Connect your AI agent"). Under #306 the
template body changes and the badge goes; the URL name `editor_account_mcp` and the menu
entries stay, which is why they are introduced here and not there.

Alternative considered: a disabled third card and nothing else. Rejected — the card is
disabled (D2), but on its own it measures nothing; the page behind the menu entries gives a
count before the server costs anything.

### D7 — Events
`survey_created` gains `surface` (`start_blank` | `create_page`) and `map_source` (the
chain's outcome, `brief` when `tasks.py` replaced it with a geocoded location — the task
already knows that and sets the property itself). `agent_access_requested` is a new
creator-lifecycle event in `product_events` with no properties beyond the user. The
start page needs no event of its own: PostHog's `$pageview` on
`/editor/surveys/start/` and the next `survey_created` already give the card split.

### D8 — Where things render
The start page and the agent page extend `editor/editor_base.html` like the create page
(top strip under `MOBILE_EDITOR_NAV` shows the page title and a back link; no bottom
pane bar). The dashboard's `+ New Survey` and ⋯ menu are in `editor.html` (extends
`base.html`). Styles go into the "create" block of the editor CSS, not inline `<style>`.
Strings are `{% trans %}`/`{% blocktrans %}` with Russian in the same PR, per the
`creator-ui-localization` rule.

## Risks / Trade-offs

- [An extra page before every survey for creators who never set a default] → the
  checkbox is on the card they are about to click, the default takes one tick, and a
  creator with a default never sees the page again unless they ask.
- [A POST "+ New Survey" button when the default is `blank` differs from a link:
  middle-click/open-in-new-tab stop working for that one button] → acceptable; the
  button's job is one click, and the start page is one menu item away.
- [`Untitled survey` surveys pile up from mis-clicks] → trash + the dashboard's search
  already handle it; `surface='start_blank'` in PostHog shows if it happens often, and
  the editor header's rename is the first thing a creator sees.
- [`CF-IPCountry` turns out absent or wrong behind Render] → the rung is guarded by
  `CLOUDFLARE_TRUSTED`, falls through to `Accept-Language` and then `world`; the
  `map_source` property reveals the real distribution within a day of deploy.
- [Asking for geolocation on the *Start from scratch* click adds a browser dialog to
  the one-click path] → it is asked once, after a sentence that says why, with a
  3-second ceiling; a refusal is remembered by the browser and never asked again, and
  the survey is created either way.
- [Permissions API gaps (Safari before 16)] → start page asks (that is the click
  path anyway); create page reads nothing silently and shows the hint link.
- [Two menus, two bases] → the account-menu partial is edited in both files in the
  same commit; a test renders the dashboard and an editor page and asserts the new item
  on both.
- [A `soon` badge that stays for months] → `agent_access_requested_at` counts are the
  argument for prioritising #306; the badge text is one string.

## Migration Plan

One migration adds two nullable/defaulted columns to `CreatorPreferences`; no backfill.
Deploy is additive: old links to `/editor/surveys/new/` keep working, `?welcome=1` on
the create page keeps rendering, and the empty-organization redirect simply changes
target. Rollback is a revert; the two columns are harmless when unread.

## Open Questions

- Card illustrations: icon-only now; the owner decides later whether to commission
  three pictures (the game reference) — a template-only change.
- Whether `org_survey` should prefer the creator's own surveys inside a large
  organization. Starting with "newest in the organization"; revisit if `map_touched`
  after `org_survey` turns out high.
