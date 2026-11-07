## Why

The owner (2026-11-07): the dashboard hero banner and the corner "What's new" card take the creator's working space — the banner sits above the survey list, the card covers maps (the style editor's preview, the Responses map). The application sidebar (#538) has an empty stretch between the navigation and its footer that is enough for one entry.

## What Changes

- **Removed**: the dashboard hero banner (`editor/partials/_whats_new_hero.html`) and the corner card (`editor/partials/_whats_new_card.html`) and their includes in `editor.html`, `base.html`, `editor_base.html`.
- **Added**: a compact *What's new* block in the sidebar above the footer (`partials/_sidebar_whats_new.html`): the entry the banner or the card would have shown — a pending hero, else the newest unseen card entry — with its picture, date, title, the hero's call to action when it has one, *Read more* (the What's new page), *Don't show these* and ×. Hidden in the rail; inside the drawer on phones.
- Seen-state, the cards preference, hero audiences and expiry, the endpoints and the PostHog events are unchanged (`changelog_card_shown` gains `surface: sidebar`).
- Hero-only presentation goes: chips, the "Part of Pro" note line, the art plate, the phone disclosure. Hero entries keep their header keys; the sidebar uses `title`, `image`, `link`/`link_query`, `cta_label`.

## Capabilities

### Modified Capabilities
- `in-app-changelog`: the card requirement becomes the sidebar block.
- `changelog-hero-banner`: a pending hero renders in the sidebar block on every creator page, not as a dashboard banner; chips and the note are no longer rendered.

## Impact

Templates and CSS of the sidebar, three base templates, two partials deleted, changelog tests. No model, endpoint or event change. The Map styles epic (#545, PR #557) edits `_whats_new_card.html`; merging `master` into `epic/map-styles` after this lands resolves that by taking the deletion.
