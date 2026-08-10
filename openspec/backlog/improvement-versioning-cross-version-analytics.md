# Versioning: cross-version analytics and response counts

**Type**: improvement
**Priority**: high
**Area**: backend
**Created**: 2026-04-16

## Description

When a survey is republished as a new version, the analytics page and editor dashboard show 0 responses for the new version — old responses are invisible. This is alarming for survey creators who expect continuity. Need a mechanism to aggregate responses across compatible versions (typo fixes, minor edits, question additions) while keeping truly incompatible versions (restructured sections, removed questions) separate.

## Notes

- Real-world trigger: bisqunours republished a 619-response survey to fix a single typo, and the new version shows 0 responses + 0 in the dashboard list
- Two categories of version changes:
  - **Compatible** (additive/cosmetic): typo fixes, text edits, new questions added, reordering — old responses remain valid and should be shown
  - **Incompatible** (breaking): questions removed or fundamentally changed — old responses may not map cleanly
- `check_draft_compatibility()` already exists in `survey/versioning.py` — can be extended to flag compatibility level at publish time
- Affected areas: analytics page (charts, geo layers, table), editor dashboard response count, data export (`?version=` parameter already exists)
- Dashboard survey list should show cumulative response count across all versions of a canonical survey
- **2026-08-10 — CLOSED** in PR #54. Analytics reads the whole version family by default (`survey/analytics.py:124`, `survey/versioning.py:126` `resolve_version_scope`), dashboard counts span it (`survey/views.py:509-533`), and a version picker narrows it (`survey/analytics.py:29`). A follow-up divergence between analytics and the export was found during that work, filed as #114 and fixed in PR #55.
