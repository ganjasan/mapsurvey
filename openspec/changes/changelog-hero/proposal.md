## Why

The in-app changelog (change `in-app-changelog`, #227) has one shape: a small fixed card in the
corner, the same for a typo fix and for the MCP launch. The biggest changes need a bright,
promotional banner where every creator passes — and the one we need now is the assistant.
The agent page `/editor/surveys/start/agent/` (#312) is reachable only through **+ New Survey**,
the "?"-menu item *Connect your AI agent* leads to the tokens page, so a creator who edits a
survey or reads responses never learns that an assistant can do that for them, although the
response tools (#409) and share tools (#410) are the part that is useful to them now. First day on
production (2026-10-24/25): 30 external creators opened the start page, 1 opened the agent page,
0 connected. A separate banner per feature would mean a queue of cards to close — the thing that
produces rage clicks — so this is a second tier of the one mechanism we have (issue #423).

## What Changes

- **Hero tier for changelog entries.** An entry may declare `tier: hero` with a visual plate
  (named art style or image), a benefit headline, ONE call to action, example chips that take the
  creator's own survey names, and a named show condition. A hero renders on the dashboard
  (`/editor/`) above the survey list as a full-width banner; ordinary entries keep the small card.
- **No queue, no second close.** While a hero is pending for a creator, no small card renders on
  any page; closing the hero (×, the CTA, "Don't show these") moves the watermark to the newest
  entry, so no small card follows it. A hero entry never renders as a small card. A failed
  watermark POST keeps the card hidden in the browser (`localStorage`) instead of bringing it
  back on the next page — today's behaviour is the second click.
- **Lifetime and audience.** A hero shows until closed, until its "done" predicate holds
  (assistant: an MCP connection exists), and at most 30 days after the entry date; after that it
  shows nothing. Show/done conditions are named predicates from a registry in Python
  (`has_surveys`, `no_mcp_connection`, `free_plan`), never an `if` in the template.
- **Budget.** At most one hero per 14 days — enforced by `ChangelogEntriesTest` over the entry
  dates, not by convention.
- **Measurement.** `changelog_card_shown` and `changelog_card_dismissed` carry `tier`; a new
  `changelog_card_clicked` fires on the CTA. One set of numbers per big feature: seen, clicked,
  closed unread.
- **The first hero.** A new entry, dated the release day: "Edit these surveys and read their
  responses from Claude or ChatGPT", art `agent`, CTA to the agent page with `?from=dashboard`,
  "How it works" to the help-centre MCP guide, shown to creators whose workspace has a survey and
  who have no MCP connection; Free workspaces see "Part of Pro · connecting is free".
- **Entry points for the assistant.** The "?"-menu item *Connect your AI agent* leads to the agent
  page (not the tokens page); *API & connections* in the account menus stays on the connections
  page, which gains a "Use your AI assistant" link at the top. The agent page accepts `?from=`
  and the back link reads "Dashboard" when it came from there.

## Capabilities

### New Capabilities
- `changelog-hero-banner`: the hero tier — entry header keys, the dashboard banner, the no-queue
  rules (hero suppresses small cards, closing covers everything, closed stays closed), lifetime,
  audience predicates, the 14-day budget test, the events, and the first hero entry.

### Modified Capabilities
- `in-app-changelog`: the entry header accepts the hero keys; the small card requirement gains
  "not while a hero is pending for this creator" and "a hero entry never renders as a small
  card"; `changelog_card_shown`/`changelog_card_dismissed` carry `tier`.
- `agent-access-teaser`: the "Entrances to the agent page" requirement changes — the "?" menu's
  *Connect your AI agent* links to `/editor/surveys/start/agent/`; the connections page links to
  the agent page; the "Tell me when it's ready" block is gone since change `mcp-server` (the
  requirement text still describes it — this change retires that paragraph). The changelog
  events are specified only in `in-app-changelog`, so `changelog_card_clicked` lands there.

## Impact

- `survey/changelog.py` (header keys `tier`, `art`, `cta`, `cta_label`, `secondary`, `chips`,
  `show_if`, `done_if`; `hero_for(user, org)` selection), new `survey/changelog_audience.py`
  (predicate registry), `survey/context_processors.py::whats_new` (`hero` and the suppression of
  the small card), `survey/editor_views.py` (`whats_new_seen` accepts `how=cta`, emits
  `changelog_card_clicked`), `survey/product_events.py`.
- Templates: new `editor/partials/_whats_new_hero.html` included from `editor.html` above the
  survey list; `_whats_new_card.html` (localStorage guard, `tier` on events, nothing while a hero
  is pending); `partials/_help_menu.html`; the connections page; `survey_start_agent.html`
  (`?from=`). CSS in `survey/assets/css/whats-new.css`.
- `survey/changelog/<release-date>-assistant-for-your-surveys.html`, `survey/changelog/README.md`.
- Queries: the hero predicates add at most two cheap EXISTS queries on the dashboard only, for a
  creator with an unseen hero; no change on other pages, none on respondent surfaces.
- Specs touched: `in-app-changelog`, `agent-access-teaser`; new `changelog-hero-banner`.
- Help centre: no page change (the MCP guide exists); the hero's "How it works" uses
  `HELP_URL.mcp`.
- Translations: the banner chrome strings ("Connect your assistant", "How it works", "Part of
  Pro · connecting is free", "Don't show these") go into every offered catalog; entry text stays
  English like every changelog entry.
