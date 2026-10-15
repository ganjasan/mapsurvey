## Why

A creator with no surveys is sent straight to `/editor/surveys/new/?welcome=1`, a page
that opens with an AI brief and a map centred on Berlin whatever the creator's own city.
There is no moment where the product says "here are the ways to make a survey, pick
one": the empty path is a secondary button, the AI path is the default by layout, and
the third way — letting the creator's own AI agent (Claude, ChatGPT, Cursor) build the
survey through MCP — exists only in untracked docs (#306), nowhere in the product. A
fourth of ChatGPT-sourced registrations already arrive expecting to drive the product
from an agent.

Two decisions sit behind this change. The ways to start are a choice the creator makes
on purpose, like a character's life path in a role-playing game: three cards, one
sentence each, and the choice remembered. And the map a new survey opens on must be as
close to the creator as we can get without asking anything they have not agreed to —
the browser's position when they have granted it, otherwise the places they already
survey, their country, the world; never a city we picked.

## What Changes

- **A start page** at `/editor/surveys/start/` with three cards — *Start from scratch*,
  *Draft with AI*, *Connect your AI agent*. The empty-organization redirect that today
  targets the create page targets this page instead; "+ New Survey" on the dashboard
  leads here too. The first two cards carry an **"Always start this way"** choice stored
  server-side in `CreatorPreferences` (`survey_start_default`): once set, "+ New Survey"
  goes straight to that path and the start page stays reachable from the dashboard's ⋯
  menu ("Start another way…") and from a link on the create page. The third card is a
  teaser until the MCP server ships.
- **Start from scratch creates the survey in one request** — `POST
  /editor/surveys/new/blank/` makes a survey named "Untitled survey" in the creator's
  interface language, with the suggested map start, a first section and the owner
  collaborator, and opens the editor. The create page with its map picker is no longer
  on this path; name, languages and map are edited in place in the editor and Survey
  settings, which already support all three.
- **A map-start suggester**, `survey/map_start.py::suggest_start_position(request, …)`,
  shared by the start page, the blank-create endpoint and the create page's initial
  centre: browser position (only when the creator has granted it — the page asks
  permission tied to an action, never on load) → the latest survey in the organization
  that has a map start → the country from the edge's `CF-IPCountry` (Render's proxy;
  trusted only under `CLOUDFLARE_TRUSTED`) or the `Accept-Language` region → the world.
  The source rides on `survey_created` as `map_source`, next to `map_touched`, so we
  learn which rung works and how often creators then move the map. The create page
  starts on the suggested centre instead of Berlin, which also fixes the AI draft path:
  a brief that names no place gets the form's initial position, which was Berlin.
- **An agent-access page** at `/editor/account/mcp/` — the URL `docs/mcp.md` already
  promises and #306 will fill. Until then it explains what connecting an agent does, shows
  one example prompt, and offers **"Tell me when it's ready"**, which records
  `CreatorPreferences.agent_access_requested_at` and emits `agent_access_requested`. The
  account menu (both bases) gets "AI agents & MCP" with a *soon* badge; the "?" menu gets
  "Connect your AI agent". #306 replaces the teaser body with the token page and keeps
  the URL and the menu entries.
- **`survey_created` carries `surface`** (`start_blank` | `create_page`) and
  `map_source`; a changelog entry announces the start page.

Not in this change: the MCP server, tokens and the agent hand-off with a prefilled
prompt (#306 and a follow-up); city-level IP geolocation (would need a GeoIP database
or a third-party lookup for a suggestion the browser already gives better); the
respondent-side Berlin fallback in `views.py` (every survey created from now on has a
start position).

## Capabilities

### New Capabilities
- `survey-start-chooser`: the start page, its three cards, the remembered default and
  the one-request blank creation.
- `map-start-position`: the ordered chain that suggests where a new survey's map
  opens, the permission rule for the browser position, and the `map_source` property.
- `agent-access-teaser`: the `/editor/account/mcp/` page before the MCP server exists,
  the interest signal and the menu entries.

### Modified Capabilities
- `survey-editor`: *New-user redirect to survey creation* targets the start page;
  *Dashboard integration* routes "+ New Survey" by the remembered default; *Survey
  creation* opens the map on the suggested centre and shows a way back to the start page.
- `creator-funnel-events`: `survey_created` gains `surface` and `map_source`;
  `agent_access_requested` joins the creator-lifecycle events.

## Impact

- Code: `survey/views.py` (`editor` redirect), `survey/editor_views.py` (start page,
  blank create, agent page, create page centre), new `survey/map_start.py` and
  `survey/country_centroids.py`, `survey/product_events.py`, `survey/urls.py`,
  `survey/models.py` + one migration (`CreatorPreferences.survey_start_default`,
  `agent_access_requested_at`), templates `editor/survey_start.html`,
  `editor/account_mcp.html`, `editor.html` (button + ⋯ menu), `base.html` and
  `editor/editor_base.html` (account menu), `editor/partials/_help_menu.html`,
  `editor/survey_create.html` (initial centre, geolocation rule, back link), a
  `survey/changelog/` entry, tests in `survey/tests.py`.
- Analytics: two new properties on an existing event and one new event; no PostHog
  dashboard changes required.
- No external services, no new dependencies, no respondent-facing change.
