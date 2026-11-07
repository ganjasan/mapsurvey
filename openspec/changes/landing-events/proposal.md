## Why

Step 4 of 4 of epic #348 (#579). Engagement is online and offline: open houses, walks,
workshops. The landing should announce them and let residents say "I am coming", so the
organiser knows the numbers and residents get the date in their calendar. Shipped last because
it is the first time Mapsurvey stores residents' names and email addresses.

## What Changes

- **Event block**: date, start and end time, time zone, place (+ optional map link), short
  description, seat limit (optional), registration on/off.
- **Registration form** on the public page: name, email, consent line. Honeypot + per-IP rate
  limit; the seat limit is enforced in a transaction; the same email registers once.
- **Confirmation email** with the event details, a calendar file (.ics) and a cancel link;
  cancelling is a POST from a confirmation page (mail scanners prefetch GETs).
- **Creator side**: attendee list per event (owner / admin / editor), CSV export, remove one,
  remove all; the count and seats left in the builder.
- **Retention**: registrations are deleted automatically 30 days after the event ends (daily
  task), and with the block or the landing; the form says so.
- **Policy text**: `/terms/` (personal-data section) and `/trust/` (Data Privacy) say what is
  stored, for whom, how long; `TERMS_UPDATED` bumped.

## Capabilities

### Modified Capabilities
- `survey-landings`: the block set grows by `event`; requirements for registration, the
  attendee list and retention.

## Impact

- Model + migration `EventRegistration`; `event` kind; `survey/landing_events.py` (registration,
  .ics, cancel, purge); views + URLs for register, cancel, attendee list, CSV, removal;
  mail templates `landings/mail/event_confirmation.{txt,html}`; Celery task + beat entry
  `purge_event_registrations`; templates, CSS, help, translations, terms and trust pages.
