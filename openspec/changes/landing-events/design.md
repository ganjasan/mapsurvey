## Context

Landings (#576–#578) are workspace pages with blocks; the public page is read by our
customers' residents, carries no analytics, and the respondent pages store no name or email.
This change is where that last rule gets an explicit, narrow exception.

## Decisions

### D1. Event data in the block, registrations in a table
`data = {date 'YYYY-MM-DD', start 'HH:MM', end 'HH:MM'|'' , tz IANA (default UTC), place ≤200,
place_url http(s)|'', description ≤1000 plain, capacity int 1–10000 | null, open bool}`.
`EventRegistration(block FK CASCADE, name ≤120, email, token uuid unique, created_at,
cancelled_at null)`, unique `(block, email)` among active rows enforced in code (a cancelled
row may be followed by a new one). Times are computed from date + time + tz with `zoneinfo`.

### D2. Registering
`POST /p/<slug>/events/<block id>/register/` (published, not held landing; block of that
landing; `open` and the event not over). Order: honeypot `website` → silent success page;
rate limit 5/hour per IP (same key function as reports, fail-open) → 429; form: name required,
email valid, consent ticked. In one transaction with the block row locked (`select_for_update`):
an active registration with the same email → no new row, the confirmation is sent again;
active count ≥ capacity → "full" message; else create. Then the confirmation mail (Celery task,
inline fallback when the broker refuses, like the abuse notice) and a redirect to
`?registered=<block id>#b-<id>` which shows "Check your inbox".

### D3. Confirmation and cancel
Mail from `DEFAULT_FROM_EMAIL`: subject "You're registered: <event>", text + HTML, the event
details in the landing's language, an `.ics` attachment (`METHOD:PUBLISH`, UID
`<token>@<site host>`, DTSTART/DTEND in UTC, SUMMARY, LOCATION, DESCRIPTION with the landing
URL), and `/p/events/cancel/<token>/`. GET shows the event and a Cancel button; POST sets
`cancelled_at` (the seat frees). Unknown token → 404.

### D4. Creator side
Builder event form shows "N registered · M seats left" and a link to
`/editor/landings/<uuid>/events/<block id>/` (owner/admin/editor; viewers 403 — this is
personal data): table name, email, registered at, status; CSV (`name,email,registered_at,
status`, formula-guarded cells); "Remove" per row and "Remove all" (POST). Viewing and removing
do not need Pro (a lapsed workspace must still be able to delete people's data).

### D5. Retention
Daily beat task `survey.tasks.purge_event_registrations`: delete registrations of events that
ended more than 30 days ago (end = date + end time or start, in the event's zone). Deleting the
block or the landing deletes its registrations (CASCADE). The form states: "We use your name and
email only for this event and delete them 30 days after it."

### D6. Screening
Event title, place, description and place link are part of `collect_landing_text`.

## Risks / Trade-offs

- [Mail abuse: someone registers other people's addresses] → rate limit per IP, one mail per
  (event, email) registration action, the cancel link in every mail; no marketing content.
- [Overbooking under concurrency] → the count and insert happen with the block row locked.
- [Policy drift] → `/terms/` and `/trust/` change in the same PR; a test reads the sentences.
