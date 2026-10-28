## 1. Loader and audience

- [x] 1.1 `survey/changelog.py`: `Entry` gains `tier`, `art`, `eyebrow`, `link_query`, `cta_label`, `help`, `chips` (tuple), `show_if` (tuple), `note_if`, `note`; `_parse` accepts the keys, defaults `tier='card'`, rejects a hero with `kind: fixed`, without `link`/`cta_label`, with an unknown `art` (registry `ARTS = ('agent',)`), an unknown predicate, and a `card` entry carrying `show_if`/`note_if`/`chips` — every error names the file
- [x] 1.2 New `survey/changelog_audience.py`: `PREDICATES` registry (`has_surveys`, `no_mcp_connection`, `free_plan`) and an `Audience(user, org)` memo; `changelog.py` validates `show_if`/`note_if` names against it at load time
- [x] 1.3 `changelog.hero_for(seen_id, audience, today=None)`: newest unseen hero within `HERO_LIFETIME_DAYS = 30` whose predicates hold, predicates evaluated only inside the window; `changelog.latest_card(seen_id)` for the small card (skips heroes)
- [x] 1.4 `changelog.render_chips(entry, survey_names)`: `{survey}` cycling, placeholder-less chips literal, unfillable chips dropped
- [x] 1.5 Tests (`ChangelogEntriesTest`): hero parses; missing `cta_label`, unknown predicate, unknown art, `fixed` hero, `chips` on a card each rejected naming the file; `test_hero_budget` (≥14 days apart over the shipped directory); every shipped hero's `link` resolves; `hero_for` window and audience; `render_chips`

## 2. Context processor and dashboard

- [x] 2.1 `context_processors.whats_new`: add `hero`, `hero_chips`, `hero_note`, `hero_link`; `show_card` = unseen card entry ∧ cards on ∧ no pending hero; survey names for chips from the active org (published first, newest first, trash excluded) only when a hero is pending; `assertNumQueries` test — zero audience queries when the watermark is past every hero
- [x] 2.2 New `editor/partials/_whats_new_hero.html` (plate by `art`/`image`, eyebrow, title, body, chips, CTA, "How it works" via `HELP_URL[help]`, note, ×, "Don't show these"), included in `editor.html` between the header and the import-jobs block; styles in `whats-new.css` (`.wn-hero`, `.wn-hero-art.agent`, phone layout)
- [x] 2.3 Hero script: `changelog_card_shown` with `tier`; × → `how=close`; CTA `<a>` → keepalive POST `how=cta` then navigation; "How it works" → `changelog_card_clicked target=help`; "Don't show these" → cards endpoint; `localStorage['msWhatsNewClosed']` guard (hide on render when it matches, retry the POST)
- [x] 2.4 `_whats_new_card.html`: same `localStorage` guard; `tier=card` on `changelog_card_shown`; `data-entry-id` already there
- [x] 2.5 `editor_views.whats_new_seen`: accept `how=cta` and `entry_id`; emit `changelog_card_dismissed` with `tier`, and `changelog_card_clicked` (`target=cta`) for `cta`; `product_events.CHANGELOG_CARD_CLICKED`
- [x] 2.6 Tests (`ChangelogContextTest`, `WhatsNewViewsTest`): dashboard renders the hero and no card; editor page renders neither while pending; expired / out-of-audience hero → small card for a newer card entry, none for the hero; Free note shown / hidden; `how=cta` moves the watermark and emits both events; chips carry the creator's survey names escaped

## 3. The first hero and the entry points

- [x] 3.1 `survey/changelog/<release-date>-assistant-for-your-surveys.html` with the header from the spec and a two-paragraph body; `survey/changelog/README.md` documents the hero keys, the 30-day lifetime, the 14-day budget and "hero is for what ships from now on"
- [x] 3.2 `agent_views.editor_survey_start_agent`: read `from` ∈ `dashboard|help|connections`, back link "Dashboard" → `/editor/` for `dashboard`, `data-from` on the page root, unknown values dropped; `survey_start_agent.js` adds `from` to every event it sends; tests for both scenarios
- [x] 3.3 `_help_menu.html`: *Connect your AI agent* → `editor_survey_start_agent` + `?from=help`; `api/templates/api/connections.html`: "Use your AI assistant" link above the tokens section → `?from=connections`; update the existing menu tests
- [x] 3.4 New creator strings ("Connect your assistant", "How it works", "Part of Pro · connecting is free", "Dashboard", "Use your AI assistant — connect Claude, ChatGPT or another assistant") appended by hand to every offered catalog (`TranslationCatalogHygieneTest`)

## 4. Wrap-up

- [x] 4.1 Register the worktree offset 880 in `.env.ports.example`
- [x] 4.2 CLAUDE.md "In-app changelog" paragraph: the hero tier in three sentences (header, pending rule, budget test)
- [ ] 4.3 `./run_tests.sh survey.tests.ChangelogEntriesTest survey.tests.ChangelogContextTest survey.tests.WhatsNewViewsTest` plus the agent-page and menu tests; rename the entry file to the merge date before merging
- [ ] 4.4 PostHog after launch (not code): an insight `changelog_card_shown → clicked → dismissed` by `entry_id`, `$rageclick` on `.wn-card, .wn-hero`
