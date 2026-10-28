## Why

The two surfaces that report a survey's responses — the analytics dashboard and the data export —
resolve `?version=` with two separate implementations, and the two disagree. A creator reads 111
responses on screen, downloads the data, and gets 2 rows.

`resolve_version_scope` (`survey/analytics.py:16`) returns header ids; `_get_version_surveys`
(`survey/views.py:1009`) returns `(survey, prefix)` tuples. They were written for different callers
and never reconciled:

- **Different defaults.** With no parameter, analytics defaults to `all`
  (`analytics_views.py:87`, `147`, `196`); the export defaults to the current version only
  (`views.py:1009-1011`).
- **`latest` means opposite things.** The export handles `'latest'` as canonical-only.
  `resolve_version_scope` cannot parse it — `int('latest'.lstrip('v'))` raises, `num` becomes `None`,
  and it falls through to the whole family. The same word narrows one surface and widens the other.
- **Unknown values fall in opposite directions** for the same reason: analytics widens to the
  family, the export narrows to the current version.

Measured on `Ameelia Mirt` (canonical v3, archived v2), local data:

| `?version=` | Analytics "Total Sessions" | Export CSV rows |
|---|---|---|
| *(none)* | 111 | 2 |
| `latest` | 111 | 2 |
| `all` | 111 | 111 |
| `v3` (current) | 2 | 2 |
| `v2` | 109 | 109 |
| `bogus` | 111 | 2 |

Every number there is correct — each is a right answer to a different question. The defect is that
one URL asks two questions.

The Download button on the analytics dashboard itself (`analytics_dashboard.html:379`) carries no
`version` at all, so the most direct path from "111 on screen" to "2 rows in the file" is a single
click inside the dashboard that is showing the 111.

## What Changes

- One resolver, in `survey/versioning.py`, serves both surfaces. Analytics and the export SHALL
  answer the same question for the same URL.
- **The default is `all`** — the whole version family — on both surfaces. Analytics already
  defaults there; the export follows. A survey with one version is unaffected: its family is itself.
- **`latest` means the canonical version** on both surfaces, identical to `vN` where N is the
  current version number.
- An unparseable value falls back to the default (`all`) on both surfaces, rather than to opposite
  ends as it does now.
- Export filenames are prefixed `vN_` only when the resolved scope actually spans more than one
  version, so a single-version survey's download keeps its current filenames under the new default.
- The Download button on the analytics dashboard carries the version scope currently on screen.

Not in scope: changing which sessions count as clean (the trashed / not-approved filter), the
`include_all=1` escape hatch, or the analytics numbers themselves. They are correct today.

## Capabilities

### New Capabilities

- `version-filter-scope`: how a `version` request parameter resolves to a set of survey versions,
  and the guarantee that every creator-facing surface resolves it the same way.

### Modified Capabilities

- `version-export-ui`: the plain "Download Data" link for a single-version survey is specified as
  "pointing to the latest version"; under the new default it points at the family. For a
  single-version survey those are the same set, but the requirement text has to say so.

## Impact

- `survey/versioning.py` — the shared resolver (it already owns `canonical_of` / `family_ids`).
- `survey/analytics.py` — `resolve_version_scope` becomes a re-export of the shared one.
- `survey/views.py` — `_get_version_surveys` and `download_data`'s default.
- `survey/templates/editor/analytics_dashboard.html` — Download button carries the version scope.
- No migration. No model changes.
- Backlog #114 closed. Same complaint shape as the export bugs #96/#97 — a creator concluding the
  export is broken — and it costs the same support round-trip.
