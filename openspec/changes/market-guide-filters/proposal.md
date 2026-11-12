## Why

`/participatory-mapping-tools/` is read and cited by AI assistants (ChatGPT and Perplexity
referrals every week; Search Console shows it at positions 1–4 for long, assistant-style
questions), but it is awkward for a person to use and silent on two things buyers ask:

- Only 3 of 22 tool names are links, and those go to our own `/alternatives/` pages. The name is
  a link only when `landing_key` is set; every vendor's `url` is in the registry and never shown.
- Where a tool comes from and who is behind it (a public administration, a non-profit,
  university researchers, a company) sits only inside the free-text `maker`. Many free tools
  are publicly built or funded and tied to one market (DIPAS by Hamburg's administration,
  PARTIMAP by a Budapest NGO with EU funding, Decidim and Consul by a non-profit association
  and a foundation), and the page can neither say so nor filter on it.
- A cell's source is in `title=`, which a phone never shows.
- The open-source category says "drawing is not the point" while its DIPAS row draws lines and
  polygons.
- The only `SoftwareApplication` in the structured data is ours; nothing lists the tools.

Issue #651, epic `seo-coverage` (#257).

## What Changes

- Every tool name, in the table and in the category lists, links to the vendor's own site
  (`rel="noopener"`); "vs Mapsurvey in detail" stays a separate link where an alternatives page
  exists.
- Registry: `country` per vendor (region derived from it, never set by hand), `backing` as a
  sourced, dated `Fact`, `backing_kind` (`public | nonprofit | academic | commercial`) and an
  `open_source` flag. The import-time validator refuses an unknown country, an unknown kind or a
  missing backing Fact. Backing facts read on 2026-11-11 from each vendor's own page.
- Table: a "Who is behind it" column; the maker line carries the country; every cell also
  prints its source host and date, visible on touch screens only.
- Filter chips above the table — kind of tool, maker based in, who is behind it, must have
  (free plan that publishes, same-day sign-up, lines and polygons, price is public, open
  source). Progressive enhancement: the bar is `hidden` in the server HTML, every row is always
  rendered, the script only hides rows; state lives in a `#tools?…` hash written with
  `replaceState`, so a filtered view is shareable and never a new URL to index.
- Phone layout (owner request during the change): below 720 px each row is a card of
  label/value pairs instead of an 11-column sideways scroll, with ARIA roles kept explicit; the
  chip groups fold behind one "Filters (n)" button.
- Verdict: an eighth scenario, "a tool from a public body, a non-profit or a university", whose
  list is computed from `backing_kind`, with a link that applies the filter.
- JSON-LD `ItemList` of every tool (name, URL, summary), plain `ListItem`s.
- FAQ: "Are there participatory mapping tools run by governments or non-profits?"; `lastmod`
  bumped.
- Category text for open-source frameworks no longer contradicts the DIPAS row.

## Capabilities

### Modified Capabilities

- `market-guide-hub`: vendor links, who is behind each tool, filters, `ItemList`.

## Impact

- `survey/vendors.py`, `survey/seo_landings.py`, `survey/templates/participatory_mapping_tools.html`,
  `survey/templates/partials/_landing_structured_data.html`, `survey/assets/css/landing.css`,
  new `survey/assets/js/market_guide_filters.js`.
- `/alternatives/` pages: their sources list now also names the backing page (they render
  `vendor.sources`); nothing else changes there.
- No model, migration or setting.
