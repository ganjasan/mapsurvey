## Context

The editor has no channel for "what changed and why". Issue #227 asks for an in-app changelog;
#226 (empty sessions hidden by default) will be its first entry. Mockup:
`whats-new.mockup.html` in this folder (three states: card, page, menu entry).

What exists and is reused:

- `CreatorPreferences` (`survey/models.py`) — "settings a creator chooses for themselves",
  1:1 with the user, created on demand (`update_or_create` in `set_creator_language`). Its
  docstring explains why self-chosen settings do not go on `CreatorProfile` (CRM notes handed
  over verbatim under a GDPR request). The two new fields belong here.
- `survey/stories.py` — customer-story bodies are HTML authored in the repo. Same precedent for
  changelog bodies: no Markdown library is installed and the `markdown` package is not in the
  Pipfile.
- `survey.context_processors` — the navbar already gets `active_org`, `MOBILE_EDITOR_NAV` etc.
  from context processors; the editor's chrome lives in `editor_base.html`, respondent pages in
  `base_survey_template.html`, which must not render the card.
- `survey/product_events.py::emit` — server-side PostHog capture, no-op when PostHog is
  unconfigured. Browser events are sent through `window.posthog` when it exists
  (`share_link_copied` pattern).
- `survey/signals.py::create_personal_org_on_registration` — the `user_registered` receiver,
  where a new account's seen marker is seeded.

## Goals / Non-Goals

**Goals:**
- Tell a creator, once, about the newest change, where they work.
- Keep every entry reachable later, with the unseen one highlighted.
- Let the creator switch the cards off without losing the page.
- Make an entry cheap to write: one file, in the PR that ships the change.
- Zero cost on respondent pages and on pages of users who have seen everything.

**Non-Goals:**
- A public changelog on the marketing site (the same files could feed one later).
- Translated entries (English only, owner decision 2026-10-02).
- Respondent-facing notices, release notes by email, admin-authored entries.
- Showing several unseen entries at once; the card is always the latest only.

## Decisions

### D1. Entries are files in the repo, loaded once per process

`survey/changelog/<YYYY-MM-DD>-<slug>.html`. The file starts with a header block delimited
by `---` lines holding `key: value` pairs, followed by the HTML body:

```
---
title: Empty sessions are now hidden
kind: new
link: editor_survey_responses
image: changelog/2026-10-06-empty-sessions.png
---
<p>Responses, Overview, Map and exports now leave out …</p>
<p><strong>Why.</strong> Creators were deleting these rows one by one …</p>
```

- `id` = filename stem. It starts with an ISO date, so ids sort chronologically as strings;
  the loader sorts by id descending. Two entries on one day differ by slug and the later one
  in sort order wins the card — acceptable, both are "today's".
- `kind` ∈ {`new`, `fixed`}; `link` is a URL name (the page shows "Open …" only when set);
  `image` is a static path under `survey/assets/img/changelog/` (optional, PNG or GIF).
- The header is parsed by hand (`key: value`, first colon splits). No YAML, no Markdown
  dependency — the body is HTML like a story body. The repo review is the editor.
- `changelog.entries()` reads the directory once (`functools.lru_cache`) — the set only changes
  on deploy. A malformed file (no header, unknown kind, missing title) raises at load, which the
  loader test catches before deploy; the loader is never called lazily from a template without
  the test having run on the same files.
- `changelog.latest()` → newest entry or `None`; `changelog.unseen(seen_id)` → entries with
  `id > seen_id`.

*Alternative considered:* Markdown + `python-markdown`. Nicer to write, but a new dependency,
and `pipenv install` rewrites the Pipfile (known trap). HTML `<p>` for a three-paragraph note is
not a burden. *Alternative:* a database model edited in admin. Entries then do not ride the
feature's PR and can describe something not yet deployed; rejected in #227.

### D2. Seen-state is one string on `CreatorPreferences`

- `changelog_seen` `CharField(max_length=80, default='')` — the id of the newest entry the user
  has seen. Unseen = entries with `id > changelog_seen`. Empty string = never looked, so an
  existing creator sees the first entry ever shipped (that is the point of #226's entry).
- `changelog_cards` `BooleanField(default=True)` — the "Tell me about updates in the editor"
  switch. Off suppresses the card only.
- Marking seen always sets `changelog_seen = latest().id` — "seen" is a watermark, not a set,
  so a creator who skipped three releases is asked about the newest once, not three times.
- New accounts: the `user_registered` receiver creates `CreatorPreferences` with
  `changelog_seen = latest().id` (or `''` when there are no entries yet). No backlog of cards on
  first login. Legacy users with no `CreatorPreferences` row read as `seen=''`, `cards=True`.

*Alternative considered:* a `ChangelogSeen` table with one row per entry per user. Needed only
if we ever show "3 unseen" per entry; the watermark covers every behaviour in the spec and is a
single column.

### D3. One lazy context processor feeds the navbar and the card

`survey.context_processors.whats_new(request)` returns `{'whats_new': SimpleLazyObject(...)}`.
Evaluated only when a template touches it, i.e. when `editor_base.html` renders — respondent
templates never read it and pay nothing. For an anonymous user it resolves to a constant
"nothing" object without a query. For a signed-in user it does one `CreatorPreferences` read
and yields:

```
{'latest': entry|None, 'unseen': [entries], 'unseen_count': n,
 'show_card': bool,  # unseen and cards on and latest is not None
 'cards': bool}
```

The navbar renders the gift icon with a dot when `unseen_count`, the account menu item with a
badge, and `_whats_new_card.html` when `show_card`. Two creator bases carry them:
`editor_base.html` (survey pages) and `base.html` (the dashboard — the first page after login,
so the one that matters most — org pages, login). `base_survey_template.html` is untouched.
`base.html` also serves a survey's password gate and the unavailable page, so the processor
additionally resolves to the empty shape (no query) on `/surveys/` and `/r/` paths
(`changelog.RESPONDENT_PREFIXES`): a creator on a respondent surface never sees changelog
chrome, whichever base the page extends. A template test asserts no respondent page carries
the card markup.

### D4. Marking seen is a POST; the page marks seen on GET

- `POST /editor/whats-new/seen/` body `how=got_it|close` → sets the watermark, emits
  `changelog_card_dismissed {entry_id, how}`, returns 204. The card's three buttons: "Got it"
  and × post `how`, then hide the card; "All updates" is a plain link to the page (the page
  marks seen itself, so no POST is needed); "Don't show these" posts to the preference endpoint.
- `GET /editor/whats-new/` renders the list with the unseen entries highlighted (computed
  BEFORE the watermark moves, so the highlight is right on this render), then sets the
  watermark and emits `changelog_page_viewed {entry_id: latest}`. A GET with a side effect is a
  deliberate trade: the deep link from "All updates" and the menu must count as "seen" without
  a round trip, and the write is idempotent.
- `POST /editor/whats-new/cards/` body `enabled=0|1` → sets `changelog_cards`. `enabled=0`
  from the card also moves the watermark (the creator has seen what they are muting) and emits
  `changelog_card_dismissed {how: muted}`. The page's switch posts the same endpoint.
- CSRF: the card and the page read the token from the `csrftoken` cookie, the way
  `layer_editor.js` does (`CSRF_COOKIE_HTTPONLY` is not set).
- If the seen POST fails (network), the card hides for this page and comes back on the next —
  the harmless direction.

### D5. Events

`survey/product_events.py`: `CHANGELOG_CARD_SHOWN = 'changelog_card_shown'` (browser, on card
render, guarded by `window.posthog`), `CHANGELOG_CARD_DISMISSED = 'changelog_card_dismissed'`
(server, from D4, property `how` ∈ got_it/close/muted), `CHANGELOG_PAGE_VIEWED =
'changelog_page_viewed'` (server). Every event carries `entry_id`. The split follows the
existing convention: UI reactions from the browser, navigations and writes from the server.

### D6. Chrome, mobile, i18n

- Gift icon (`fas fa-gift`) in the navbar is `nav-desktop`; the menu item "What's new" goes in
  the desktop account dropdown and in the mobile ⋯ overflow (`MOBILE_EDITOR_NAV`), next to
  "Help & support". On phones the icon is hidden, the menu item is the only entry.
- Card: fixed bottom-right, 360 px, full-width minus 16 px gutters below 480 px; above the
  comments drawer? No — the drawer is `z-index` higher and the card hides while the drawer is
  open only if they overlap; keep the card below the drawer in stacking order.
- Chrome strings ("What's new", "Got it", "All updates", "Don't show these", "Tell me about
  updates in the editor", "Earlier", "New", "Fixed") go through `{% trans %}` and get RU
  catalog rows; entry bodies are English and never translated.
- Image in the card: `object-fit: cover` in a 16:9 box above the title; on the page, the
  natural size capped at the column width.

## Risks / Trade-offs

- [An entry file with a typo in the header 500s every editor page] → the loader raises at
  first use AND a test loads every file in `survey/changelog/`; CI runs it on each PR, so a bad
  file cannot reach master. A load failure in production would surface via PostHog error
  tracking on the first editor request.
- [Watermark compares ids as strings] → ids are `YYYY-MM-DD-slug`; the loader rejects a filename
  not matching `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`, so the order is always the date order.
- [GET with a write on the page] → idempotent single-row update; no CSRF exposure since the
  worst a forged GET does is mark the user's own changelog read.
- [Card shown on a page the creator is mid-task on] → it is bottom-right, never modal, one
  click away, and comes once; the preference switch exists for those who want none.
- [Image bytes on every editor page while unseen] → the card image is a static PNG; the
  guidance in the entry README is "a screenshot, not a 10-second GIF".
- [Legacy users all see the first card at once] → intended; it is the one release announcement.

## Migration Plan

1. Migration `0090` adds the two fields with defaults; no data migration (empty watermark is
   the intended legacy state).
2. Deploy. One entry ships with the change (`2026-10-02-whats-new.html`: what the cards are and
   how to close or mute them), so every existing creator sees the mechanism once on their next
   editor page — which is also the production check of the mechanism itself.
3. #226 adds `survey/changelog/<date>-empty-sessions.html` and its image in its own PR.
4. Rollback: revert the PR; the two columns stay (harmless), per the one-release-later rule for
   dropping columns.

## Open Questions

- None blocking. If the owner later wants a public changelog page, `changelog.entries()` is the
  source and the marketing template renders the same bodies.
