## Context

The hub is the page assistants learn the market from, so every decision below keeps the server
HTML complete and the facts sourced; usability is added on top, never instead.

## Decisions

**Filters hide rows; they never remove them from the HTML.** GPTBot, PerplexityBot, ClaudeBot and
most crawlers fetch HTML without running JavaScript. The bar ships with `hidden`, the script
reveals it, and rows get `hidden` only in the browser. Alternative considered: server-side
filtering with `?category=` — rejected, because every combination would be a crawlable URL with
a thinner copy of the same page.

**State in the fragment (`#tools?category=ppgis&has=draws_shapes`), written with
`replaceState`.** Shareable, survives a reload, never reaches the server or the sitemap. A link
to a row the filter hides (`#row-decidim` from the verdict) clears the filter so it lands.

**Region is derived from country.** `COUNTRY_REGION` is the only mapping, so a row cannot be
"Europe" with a US maker. The United Kingdom is in Europe: a buyer filtering on Europe expects
UK vendors; UK procurement specifics (G-Cloud) stay in the hosting and pricing cells. A maker
that calls itself international and names no seat (Kobo) is "International". Country is the
maker's seat as its own pages state it (Consul Democracy: the Foundation's seat in Amsterdam,
not Madrid where the code began — the page read does not say Madrid).

**Backing is a `Fact`, like every cell.** "Who is behind it" is a claim about another vendor, so
it carries the page and the date. Its text starts with the kind ("Company: …", "Non-profit: …",
"Public administration: …"), so the column needs no second label. Open Point and MetroQuest
pages refuse automated fetches; their backing comes from the pages the earlier change read on
2026-10-06 and keeps that date.

**`ItemList` of plain `ListItem`s, not `SoftwareApplication`.** Google validates
`SoftwareApplication` for `offers` and ratings, which we do not publish for other vendors; a
list of names, URLs and summaries is what an assistant needs and raises no Search Console errors.

**Source on touch screens.** Every cell gets a `.guide-cell__src` line (host · date) shown only
under `(hover: none)`; desktop keeps the hover title. The text is in the HTML for crawlers too,
which is fine: it is the attribution.

**On a phone, rows become cards (the "stacked table" pattern), CSS only.** An 11-column table
behind a sticky first column makes a reader swipe across one tool and lose the row. Below 720 px
each `tr` is a card and each `td` a label/value grid row, the label from `data-label`. The
markup stays one `<table>` for crawlers; because `display:block` makes Chrome and Safari drop
table semantics, the cells carry explicit ARIA roles (Adrian Roselli's fix). Considered and
left for later: a "compare 2–3 tools side by side" mode, which suits "X vs Y" questions better
but is a feature of its own. The chip groups fold behind a "Filters (n)" button there, so the
first screen of the table is the table.

## Risks

- Twenty-two more outbound links from the table. They are what a roundup is expected to have and
  what makes it credible; they stay followed.
- The country of a commercial vendor is the maker's seat, which can differ from where the
  product is sold or hosted; the hosting column remains the residency answer and the verdict
  says so.
