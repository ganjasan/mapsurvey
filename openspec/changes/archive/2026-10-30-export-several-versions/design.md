## Context

`?version=` is parsed in one place, `versioning.resolve_version_scope`, which returns a
`VersionScope(value, headers)`. The export (`export.version_parts` → `collect`), the Responses
page (`analytics.SurveyAnalyticsService`), the REST export / export link and every MCP tool that
takes `version` (`response_scope.responses_scope` → `version_parts`) all read it. `version_parts`
already prefixes files `vN_` whenever the scope holds more than one header (`is_family`). So a
list only has to be understood by the resolver, and offered by the dialog.

## Goals / Non-Goals

**Goals:**
- `version=v10,v11` exports exactly those versions on every surface, with the `vN_` prefixes.
- Every value accepted today resolves exactly as before.
- The dialog lets a creator tick several versions and still hands out a copyable link.

**Non-Goals:**
- A multi-select on the Responses page's own version picker. The page accepts a list in the URL
  (same resolver), but its picker stays one value.
- Ranges (`v5-v11`). A list covers the request; a range syntax can come when someone asks.

## Decisions

- **Comma = list, parsed inside `resolve_version_scope`.** No new parameter (`versions=`), so REST,
  MCP and old scripts get it with no signature change, and "one resolution serves every surface"
  stays true. A value without a comma takes the existing path untouched — that is how old links are
  guaranteed unchanged.
- **Family order, not request order.** Headers come back in `family_headers` order (canonical
  first, archived newest-first), so the files inside the archive and the rows of the flat tables
  are ordered the same way `all` orders them. `value` is the normalised list in that order
  (`v11,v10`); a list that resolves to the whole family normalises to `all`, one entry to `vN`.
- **Fallbacks mirror the single value.** Unknown entries are dropped (as `v99` is ignored today);
  a list with nothing left is the whole family (as `bogus` is). `all` in a list widens to the
  family. `draft` in a list is ignored — the draft copy is preview traffic and only the lone
  `draft` value may report it.
- **Dialog: a collapsed multi-select with search, built from the same `data-versions` list.**
  Openers already pass `[{value,label}]`. Inline check-boxes were tried first and rejected in
  review: at 50 versions they fill the dialog. The field is one line naming what is ticked
  ("All versions (11)", "v11, v10", "v11, v10, v9 +5"); it opens a panel with a search box, an
  "All versions" master check-box and one scrolling check-box per version. The panel opens in the
  dialog's flow rather than as an absolute popup, so the scrolling modal body never clips it; the
  look follows the public-results question picker (`pr-custom-select`). Ticked values are joined with a literal comma (each value URI-encoded, the comma
  not, so the link reads `version=v11,v10`). All ticked → no `version` parameter, as today's "All".
  `draft` unticks the others and vice versa. Preselection reads `data-version` as a list, so a
  Responses page opened at `?version=v10,v11` opens the dialog with those two ticked; the card
  menu's `latest` entry stays a check-box whose value is `latest`.

## Risks / Trade-offs

- [The Responses page picker shows no matching option for a list URL] → only reachable by editing
  the URL by hand; the data shown is still the list's. Accepted.
- [Many versions] → the closed field is one line; the open list scrolls at 13rem and the search
  box narrows it (`1` finds v1, v10–v19, …).
