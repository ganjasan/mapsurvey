# In-app changelog entries

One file per entry, shipped in the same PR as the change it describes. Creators see the newest
unseen entry once as a card in the editor and can read every entry at `/editor/whats-new/`.
Loader and rules: `survey/changelog.py`.

## File

`YYYY-MM-DD-slug.html` — the date is the release day, the slug lowercase with hyphens. The id
is the filename stem and orders entries, so get the date right.

```
---
title: Empty sessions are now hidden
kind: new
link: editor
image: changelog/2026-10-06-empty-sessions.png
---
<p>Responses, Overview, Map and exports now leave out sessions where nobody answered
anything. The headline shows how many were hidden; a switch brings them back.</p>
<p><strong>Why.</strong> On busy surveys they outnumbered real responses three to one, and
creators were deleting them one by one.</p>
```

- `title` — required, one line.
- `kind` — `new` or `fixed`.
- `link` — optional URL name without arguments (`editor`, …). The page shows "Open" for it.
- `image` — optional static path under `survey/assets/img/changelog/`. PNG or GIF. The card
  shows it cropped to 16:9 above the title, the page at full width. A screenshot, not a
  ten-second GIF: the card loads on every editor page until the creator dismisses it.
- Body — HTML, two or three short paragraphs: what changed, then why. English only.

A malformed file fails `ChangelogEntriesTest`, which loads every file in this directory.
