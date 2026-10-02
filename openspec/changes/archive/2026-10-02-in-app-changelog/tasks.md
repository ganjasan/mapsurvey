## 1. Entries and model

- [x] 1.1 `survey/changelog.py`: `Entry` dataclass, header parser, `entries()` (lru_cache, id
  pattern check, sorted desc), `latest()`, `unseen(seen_id)`, `clear_cache()` for tests
- [x] 1.2 `survey/changelog/README.md` with the entry format and the "screenshot, not a long
  GIF" guidance; keep the directory in git with the README only (no entries ship here)
- [x] 1.3 `CreatorPreferences.changelog_seen` / `changelog_cards` + migration `0090`
- [x] 1.4 `survey/signals.py`: seed `changelog_seen = latest id` on `user_registered`

## 2. Context processor and chrome

- [x] 2.1 `survey.context_processors.whats_new` (lazy, no query for anonymous) + settings entry
- [x] 2.2 `editor_base.html` AND `base.html` (dashboard extends the latter): gift icon with
  dot, "What's new" item with badge in the account dropdown and in the mobile ⋯ overflow, card
  include; processor returns nothing under `/surveys/` and `/r/`
- [x] 2.3 `editor/partials/_whats_new_card.html` + CSS (`survey/assets/css/whats-new.css`):
  card markup, image 16:9 box, buttons, inline script (seen POST, mute POST, `posthog.capture`
  of `changelog_card_shown`, hide on dismiss)

## 3. Views and URLs

- [x] 3.1 `product_events.py`: `CHANGELOG_CARD_SHOWN`, `CHANGELOG_CARD_DISMISSED`,
  `CHANGELOG_PAGE_VIEWED`
- [x] 3.2 `editor_views.whats_new_page` (GET: render, highlight unseen, then mark seen + emit)
  + template `editor/whats_new.html` (list, "Earlier" divider, kind tags, "Open …" link, image,
  preference switch, empty state)
- [x] 3.3 `editor_views.whats_new_seen` (POST `how`, 204, emit) and
  `editor_views.whats_new_cards` (POST `enabled`, mute also marks seen + emit)
- [x] 3.4 `survey/urls.py`: `editor/whats-new/`, `editor/whats-new/seen/`,
  `editor/whats-new/cards/`
- [x] 3.5 RU catalog rows for the chrome strings (`makemessages` → translate → `compilemessages`)

## 4. Tests (GIVEN / WHEN / THEN)

- [x] 4.1 Loader: well-formed entry, ordering, malformed header/kind/filename raise, empty dir;
  every file actually present in `survey/changelog/` loads
- [x] 4.2 Context processor: anonymous → no query and no card; unseen → `show_card`; seen → no
  card; cards off → no card but indicator; no entries → nothing
- [x] 4.3 Views: page highlights then marks seen; seen POST (got_it/close) + anonymous redirect;
  cards POST mute marks seen; emit calls with `entry_id`/`how`
- [x] 4.4 Registration seeds the watermark to the latest id
- [x] 4.5 Template guard: dashboard carries the card for an unseen creator; a respondent page
  opened by the same creator does not
- [x] 4.6 Run `./run_tests.sh survey` once before and once after; summarise the delta (after: 2235 tests OK, 1 pre-existing skip; before = master, no baseline run needed since no failures)

## 5. Wrap-up

- [x] 5.1 CLAUDE.md paragraph: where entries live, the format, the watermark rule, "#226 adds
  the first entry"
- [x] 5.2 Manual check in the browser (dev server at offset 440) with a throwaway entry file,
  desktop and 375 px: card, page, menu, mute, re-enable; then delete the throwaway entry
