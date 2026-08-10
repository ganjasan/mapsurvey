# Analytics and export disagree on which version they show by default

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-09
**Status**: fixed 2026-08-10 — `openspec/changes/version-filter-parity/`. One resolver in
`survey/versioning.py` serves both surfaces; the default is the whole family on both, and `latest`
means the canonical version on both.

## Description

The two surfaces that report response counts resolve the `version` filter with separate,
incompatible functions: `resolve_version_scope` (`survey/analytics.py:16`) and
`_get_version_surveys` (`survey/views.py:1009`). They differ in two ways that a creator will notice.

**Different defaults.** With no `version` parameter, analytics defaults to `all`
(`request.GET.get('version', 'all')`, `analytics_views.py:87`) while the export defaults to the
latest version only. On the same survey that is 111 responses on screen and 2 rows in the downloaded
CSV.

**`latest` means the opposite in analytics.** The export handles `'latest'` explicitly as "canonical
only". `resolve_version_scope` cannot parse it — `int('latest'.lstrip('v'))` raises, `num` becomes
None, and it falls through to the whole family. So `?version=latest` narrows the export to the
current version and widens analytics to every version.

Measured on `Ameelia Mirt` (canonical v3, archived v2), local data:

| `?version=` | Analytics "Total Sessions" | Export CSV rows |
|---|---|---|
| *(none)* | 111 | 2 |
| `latest` | 111 | 2 |
| `all` | 111 | 111 |
| `v3` (current) | 2 | 2 |
| `v2` | 109 | 109 |
| `bogus` | 111 | 2 |

The two agree only when an explicit `vN` or `all` is passed.

## Notes

- Found 2026-08-09 during the pre-PR live check of `feature/public-survey-results-page`. Not
  introduced by that branch — the two resolvers were already separate; cross-version analytics made
  the divergence visible by giving analytics something to widen to.
- The numbers themselves are correct on both sides. Verified against the database: v3 has 2 sessions,
  v2 has 340 of which 109 survive the trashed/not-approved filter, so 111 clean across the family.
  Every figure above is a right answer to a different question.
- A creator seeing 111 in analytics and 2 rows in the export will conclude the export is broken.
  That is the same complaint shape as the export bugs fixed in #96/#97, and it costs the same
  support round-trip.
- Fix by making one resolver serve both, rather than aligning two. Whichever default is chosen has to
  be chosen once — and `latest` must mean the same thing in both, or be rejected rather than silently
  widened.
- Decide the default deliberately: "all versions" is the honest answer for a survey's lifetime total,
  "current version" is the honest answer for the questionnaire in front of you. Whatever is picked,
  the other surface has to say the same thing, and the UI should name which it is showing.
