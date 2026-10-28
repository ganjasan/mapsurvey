## Context

The changelog is a directory of HTML files with a `---` header (`survey/changelog.py`), one
watermark per creator (`CreatorPreferences.changelog_seen`), a lazy context processor
(`whats_new`) and one partial, `_whats_new_card.html`, included by `base.html` and
`editor_base.html` — a 360-px fixed card in the bottom-right corner. "Got it", × and "Don't show
these" already move the watermark to the NEWEST entry, so the "one close covers everything" rule
exists for the small card; what does not exist is a shape that can sell a big change, and the
card comes back when its watermark POST fails. The dashboard `editor.html` extends `base.html`
([lesson](../../../CLAUDE.md): not `editor_base.html`) and is where every creator lands after
sign-in.

The agent page (`survey/agent_views.py`, `survey_start_agent.html`, `js/survey_start_agent.js`)
knows whether the creator has an MCP connection (`_new_mcp_connection`: an unrevoked
`TokenProfile` with the `mcp` audience, OAuth grant or a personal token in use). The "?" menu's
*Connect your AI agent* and the account menus' *API & connections* both go to
`/editor/account/connections/` (`api/templates/api/connections.html`).

Mockup of the first hero: `agent-dashboard-banner.mockup.html` in this folder.

## Goals / Non-Goals

**Goals:**
- One mechanism, two tiers: a hero is a changelog entry with more header keys, selected by the
  same watermark, closed by the same endpoints, measured by the same events plus `tier`.
- No queue and no second close: a pending hero suppresses the small card everywhere; closing it
  covers every entry; a close that failed to persist does not come back.
- Audience and lifetime in Python, not templates: named predicates, a 30-day ceiling, a 14-day
  budget enforced by a test.
- The assistant reaches creators who work on existing surveys: the first hero, and the "?" menu
  item pointing at the agent page.

**Non-Goals:**
- A strip in the survey header, a login modal, or email to dormant creators.
- Hero entries for features that already shipped (the MCP and start-card entries of 2026-10-24
  stay small cards); hero is for what ships from now on.
- Changing what the small card looks like, the What's new page, or the watermark model.
- A per-entry template: every hero renders through one partial from header keys.

## Decisions

### D1. A hero is a header, not a template
The entry header gains optional keys; `tier: hero` switches the shape. Keys:

| key | meaning |
|---|---|
| `tier` | `card` (default) or `hero` |
| `art` | named plate style drawn by the partial: `agent` (terracotta, robot, assistant logos) — a registry in the partial's CSS; `image` keeps working as the plate when set |
| `eyebrow` | the monospace line above the title, optional |
| `link` + `link_query` | the CTA target (existing `link` URL name; `link_query` appended, e.g. `from=dashboard`) |
| `cta_label` | the CTA text; required for a hero |
| `help` | a `HELP_URL` key for the secondary "How it works" link, optional |
| `chips` | `\|`-separated example prompts; `{survey}` is replaced by a survey name of the creator |
| `show_if` | comma-separated predicate names, all must hold |
| `note_if` + `note` | a predicate and the line shown under the buttons when it holds (the Pro line) |

Why not a template per hero: the second hero would copy the first partial and drift; the budget
test and the events need one shape to reason about. Alternative considered — a Python registry
of hero objects: the entry file already carries date, title, link and body; splitting a hero
between a file and a dict means two places to update per launch.

The loader rejects a hero without `cta_label` or `link`, an unknown `art`, an unknown
predicate name, and any `show_if`/`note_if`/`chips` on a `card` entry — `ChangelogEntriesTest`
loads every file, so a bad hero fails CI.

### D2. Pending = unseen ∧ within lifetime ∧ audience holds
`changelog.hero_for(seen_id, audience)` returns the newest unseen hero entry whose date is
≤ 30 days ago and whose `show_if` predicates hold, else `None`. Lifetime is computed from the
entry date (the id) against today, in the project timezone; nothing is stored. Predicates are
evaluated lazily and only when an unseen in-lifetime hero exists — for a creator in that window
at most two EXISTS queries per page; for everyone else nothing changes.

Why evaluate predicates on every page rather than only on the dashboard: the suppression rule
("no small card while a hero is pending") needs the same answer everywhere. If a creator has
already connected, the hero is not pending and small cards behave as before; evaluating
predicates only on the dashboard would make the editor pages silent for up to 30 days for that
creator. Alternative — mark the hero seen when its audience fails: that would also hide any
newer small-card entry the creator has not read.

### D3. Audience predicates are a registry
`survey/changelog_audience.py`: `PREDICATES = {name: callable(user, org) -> bool}` with
`has_surveys` (the active workspace has ≥1 survey, trash excluded), `no_mcp_connection` (no
unrevoked `TokenProfile` of the user with the `mcp` audience — the same rows
`agent_views._new_mcp_connection` reads, without the `since`), `free_plan`
(`not entitlements.for_organization(org).has('api')`). An `Audience(user, org)` object memoises
each predicate for the request. New predicate = one row there; the loader validates names
against the registry at load time.

### D4. Suppression and selection live in the context processor
`whats_new` adds `hero` (the entry or `None`), `hero_chips` (the rendered chips), `hero_note`
and keeps `show_card`, which becomes `bool(unseen) and cards and hero is None and
latest_unseen_non_hero is not None`. A hero entry never becomes a small card: the small card
takes the newest unseen entry with `tier == 'card'`. `base.html` and `editor_base.html` keep
including `_whats_new_card.html`; `editor.html` includes `_whats_new_hero.html` between the
header and the import-jobs block. The hero partial renders only when `whats_new.hero` is set,
so a creator on any other page sees nothing while the hero is pending — the dashboard is the
first page after sign-in, so that silence lasts one navigation, not 30 days.

### D5. Closing covers everything, and a failed close stays closed
Both partials post to the existing `whats_new_seen` with `how` ∈ `got_it | close | cta`; the
view moves the watermark to the newest entry (existing helper) and emits
`changelog_card_dismissed` with `tier`, and for `how=cta` also `changelog_card_clicked`
(`target=cta`). The secondary "How it works" link emits `changelog_card_clicked`
(`target=help`) from the browser without moving the watermark — reading the guide is not
closing the banner.

Browser guard: on any close, the partial writes `localStorage['msWhatsNewClosed'] = entry id`
before the POST; on render, a card whose entry id equals that value is hidden at once
(`wn-hidden`) and the POST is retried in the background. The same guard goes into the small
card — the "comes back on the next page" behaviour is the second click the owner named. The
CTA is an `<a>`: the click handler sends the POST with `keepalive` and lets the navigation
proceed; no `preventDefault`, no wait.

"Don't show these" stays on the hero and keeps its meaning (cards off, everything seen).

### D6. Budget: a test, not a rule in a README
`ChangelogEntriesTest.test_hero_budget` loads the shipped directory and asserts that any two
hero entries are ≥ 14 days apart. The README states the rule and that the test enforces it.
A `fixed` entry cannot be a hero (`kind: fixed` + `tier: hero` is rejected): a fix is not news
to sell.

### D7. Chips come from the creator's own surveys
`{survey}` in a chip is replaced with the names of the active workspace's surveys — published
first, newest first — one name per chip, cycling when there are fewer surveys than chips; a chip
whose placeholder cannot be filled is dropped. Names are escaped by the template as usual. The
chips are decoration that makes the banner about *their* work; they are not links.

### D8. Entry points
- `_help_menu.html`: *Connect your AI agent* → `editor_survey_start_agent` + `?from=help`.
  *API & connections* in both account menus stays on the connections page; that page gets a
  one-line link at the top, "Use your AI assistant — connect Claude, ChatGPT or another
  assistant" → the agent page `?from=connections`.
- The agent page reads `from` (`dashboard | help | connections | ''`), renders the back link to
  the dashboard for `dashboard`, and puts the value on the root element so `survey_start_agent.js`
  adds `from` to the events it already sends (`agent_client_chosen`, `agent_install_clicked`,
  `agent_connected`, …). Unknown values are dropped, not echoed.

### D9. Events
`product_events`: `CHANGELOG_CARD_CLICKED = 'changelog_card_clicked'` (`entry_id`, `tier`,
`target`); `changelog_card_shown` (browser) and `changelog_card_dismissed` (server) gain
`tier`. The What's new page is unchanged. Reading interest later: shown → clicked → dismissed
without click, per `entry_id`, plus `$rageclick` autocapture on `.wn-card, .wn-hero`.

## Risks / Trade-offs

- [The hero shows on the dashboard only; a creator who deep-links into Responses sees nothing
  until the next sign-in] → accepted: the dashboard is the landing page after sign-in and the
  lifetime is 30 days; a second surface is exactly the double close we are removing.
- [Predicates add queries on every page for creators inside a hero window] → two EXISTS
  queries, memoised per request, only for creators with an unseen in-lifetime hero; a
  query-count test pins it.
- [A hero's `link` URL name is renamed later] → the partial resolves it with `NoReverseMatch`
  tolerance like the What's new page: the hero then renders without a CTA; the test on the
  shipped directory asserts every hero's link resolves, so it cannot ship that way.
- [`localStorage` unavailable (private mode, blocked)] → the guard is try/except; behaviour
  degrades to today's (the card can return once if the POST fails).
- [A hero for a Free workspace is an upsell on the landing page of the product] → the note says
  "connecting is free" and the CTA leads to the agent page, where the existing Pro strip explains;
  nothing on the banner is a paywall.
- [Creators who dismissed the 2026-10-24 small cards already have `changelog_seen` past them]
  → the hero is a NEW entry dated the release day, so it is unseen for everyone; its text is
  about existing surveys and responses, which is new since those entries (#409, #410).

## Migration Plan

No migration: no model change. Deploy order is irrelevant; the entry file ships in the same
PR. Rollback = revert the PR; a creator who saw the hero keeps a watermark that is simply the
newest id. Nothing to backfill.

## Open Questions

- Release date of the entry file = merge day; the implementer renames the file on the day of
  the merge (the budget test only looks at spacing).
