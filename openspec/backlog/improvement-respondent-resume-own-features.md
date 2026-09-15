# A respondent who returns sees the features they already placed

**Type**: improvement
**Priority**: high
**Area**: backend
**Created**: 2026-08-23

## Description

Survey progress lives in the Django session cookie. Close the tab, run out of battery, or
come back the next day and the map is empty — the answers are safely in the database, but
the respondent cannot see, edit or continue from them, and typically starts a second
session that double-counts.

For a one-sitting opinion survey this is tolerable. For a field route it is a data
integrity problem: Olney's count runs three Saturdays, and a volunteer's phone dying
mid-route silently splits their tally.

## Notes

- Cleanest key is the volunteer token (FD-2); a signed resume link mailed/QR'd to the
  respondent covers the account-less case.
- Must decide what "resume" means for a submitted section — reopen for editing, or
  append-only. Append-only is safer and probably enough.
- Epic: field-data-collection (FD-3)
