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
image: img/changelog/2026-10-06-empty-sessions.png
---
<p>Responses, Overview, Map and exports now leave out sessions where nobody answered
anything. The headline shows how many were hidden; a switch brings them back.</p>
<p><strong>Why.</strong> On busy surveys they outnumbered real responses three to one, and
creators were deleting them one by one.</p>
```

- `title` — required, one line.
- `kind` — `new` or `fixed`.
- `link` — optional URL name without arguments (`editor`, …). The page shows "Open" for it.
- `image` — optional static path, relative to `survey/assets/` (so `img/changelog/<file>.png`; the template passes it to `{% static %}` as is). PNG or GIF. The card
  shows it cropped to 16:9 above the title, the page at full width. A screenshot, not a
  ten-second GIF: the card loads on every editor page until the creator dismisses it.
- Body — HTML, two or three short paragraphs: what changed, then why. English only.

A malformed file fails `ChangelogEntriesTest`, which loads every file in this directory.

## Hero entries

The biggest changes get a second shape (change `changelog-hero`): a full-width banner on the
dashboard above the survey list, instead of the corner card. It is the same file with more
header keys — never a template of its own:

```
---
title: Edit these surveys and read their responses from Claude or ChatGPT
kind: new
tier: hero
art: agent
eyebrow: Your surveys, from your assistant
link: editor_survey_start_agent
link_query: from=dashboard
cta_label: Connect your assistant
help: mcp
chips: Summarise the responses to {survey}|Give me the QR code for {survey}
show_if: has_surveys,no_mcp_connection
note_if: free_plan
note: Part of Pro · connecting is free
---
<p>One short paragraph. The title carries the benefit; the button carries the action.</p>
```

- `tier: hero` — required for all of the below; `kind` must be `new` (a fix is not news to sell).
- `art` — a plate style the partial draws (`agent`), or use `image` for a screenshot. One of the two.
- `link` + `link_query` — the ONE call to action; `cta_label` its text. Required.
- `help` — a key of `survey/help_links.py` for the secondary "How it works" link. Optional.
- `chips` — example prompts separated by `|`; `{survey}` becomes one of the creator's own survey
  names (published first, newest first), so the banner is about their work. Optional.
- `show_if` — predicate names from `survey/changelog_audience.py`, all must hold (`has_surveys`,
  `no_mcp_connection`, `free_plan`). `note_if` + `note` — a line under the buttons when the
  predicate holds. An unknown name fails the loader.

Rules the code enforces, so you do not have to remember them: a hero is *pending* for a
creator while it is unseen, at most **30 days** old and in audience; while one is pending no
corner card shows anywhere, and the hero shows only on the dashboard; closing it (×, the
button, "Don't show these") marks every entry seen, so no card follows; a hero never falls
back to a corner card. **Budget: two heroes are at least 14 days apart** — the test fails
otherwise. Hero is for what ships from now on; do not promote an old entry.
