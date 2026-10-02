## Why

When creator-facing behaviour changes (first case: #226 hides empty sessions on Responses by
default), nothing in the product tells creators what changed or why. A creator who opens
Responses and sees 146 where yesterday there were 350 can only guess or write to support. We
have no place for "what changed and why" (GitHub issue #227).

## What Changes

- A changelog of entries written in the repository, one file per entry, shipped in the same PR
  as the change they describe. English only. An entry may carry one picture.
- A "What's new" card in the editor: a signed-in creator with an unseen entry sees the latest
  one once, bottom-right, with "Got it", "All updates" and "Don't show these". Dismissing it,
  acknowledging it or opening the page marks everything seen.
- A "What's new" page (`/editor/whats-new/`) listing every entry, newest first, reachable from
  the account menu (badge when unseen) and from a gift icon in the navbar (dot when unseen).
- A per-user preference "Tell me about updates in the editor", default on. Off disables the
  card only; the page, the menu entry and the badge stay.
- New accounts start with every entry marked seen.
- PostHog events for card shown, card dismissed (with how) and page viewed, carrying the entry
  id, so we can see whether entries are read.
- The first entry ships with this change and announces the cards themselves (what they are, how
  to close or mute them); #226 writes the next one.

## Capabilities

### New Capabilities
- `in-app-changelog`: repository-authored changelog entries, the once-only card, the What's
  new page and its entry points, the per-user card preference, seen-state semantics and the
  analytics events.

### Modified Capabilities

(none — `product-analytics` requirements are unchanged; the new events follow its existing
rules and are specified under the new capability)

## Impact

- `survey/models.py`: two fields on `CreatorPreferences` (`changelog_seen`, `changelog_cards`)
  + migration `0090`.
- New module `survey/changelog.py` (entry loader) and entry files under `survey/changelog/`.
- `survey/context_processors.py`: one lazy context processor feeding the navbar and the card.
- `survey/editor_views.py` + `survey/urls.py`: page view, "seen" POST, preference POST.
- `survey/signals.py`: registration seeds the seen marker.
- `survey/templates/editor/editor_base.html` (icon, menu items, card include), new
  `editor/whats_new.html`, new partial `editor/partials/_whats_new_card.html`, small CSS in
  `survey/assets/css/`.
- `survey/product_events.py`: three event names.
- `survey/tests.py`: loader, context processor, views, registration, template guard.
- No new Python dependency.
