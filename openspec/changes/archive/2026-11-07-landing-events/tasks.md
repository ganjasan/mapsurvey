## 1. Data and domain

- [x] 1.1 `EventRegistration` model + `event` kind; migration
- [x] 1.2 `landings._clean_event`; `survey/landing_events.py`: times, `register`, `cancel`, `ics`, `purge`, CSV rows
- [x] 1.3 Screening: event text

## 2. Views, mail, task

- [x] 2.1 Public: register (honeypot, rate limit, consent, lock), cancel GET/POST; URLs
- [x] 2.2 Mail templates + Celery task with inline fallback; `.ics`
- [x] 2.3 Builder: event form, counts; attendee page, CSV, remove one / all
- [x] 2.4 Daily purge task + beat entry

## 3. Templates, policy, docs

- [x] 3.1 `landings/blocks/event.html`, form branch, summary, CSS
- [x] 3.2 `/terms/` personal data + `/trust/` Data Privacy; `TERMS_UPDATED`
- [x] 3.3 Help page section; translations

## 4. Verify

- [x] 4.1 Tests for every scenario
- [x] 4.2 Full suite, validate, dev check (register, mail in console, cancel, attendee list)
- [ ] 4.3 PR into `epic/landing-pages`, merge
