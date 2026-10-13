## Context

The marketing pages (`base_landing.html` family) already have one lead-capture precedent: `/pro/` with `ProInterest` (`survey/pro_interest.py`). It stores a row, emits a server-side PostHog event with a distinct id resolved from the `ph_*_posthog` cookie, and is listed read-only in admin. Registration (`survey/abuse.py`) has the honeypot and the per-IP rate-limit helpers. Transactional mail goes through `survey/mail.py` (`send_templated_mail`) and Celery tasks in `survey/tasks.py`. The Russian homepage `/ru/` renders the same `landing.html` under a `translation.override`, so every new marketing string needs a `ru` entry.

## Goals / Non-Goals

**Goals**
- Lowest possible first step: one email field, no calendar, no consent checkbox, no CAPTCHA.
- A lead exists (row + email to us + analytics event) the moment step 1 is submitted.
- Conversion per surface measurable without any client-side tracking code.
- Nothing on the page that could turn into an open email relay.

**Non-Goals**
- An auto-reply to the visitor (would make the form an email relay for arbitrary addresses; the reply is written by hand).
- "Skip this page next time?" for signed-in users (separate change if ever).
- Changing `/pro/` or pricing.

## Decisions

### Two steps, two URLs, one row
- `GET /demo/` renders step 1 (email). `POST /demo/` validates, creates `DemoRequest(email, source, user)`, notifies, emits, and redirects (303) to `/demo/<key>/`.
- `GET /demo/<key>/` renders step 2 for that row; `POST /demo/<key>/` saves name, organisation, project, timeline, sets `details_at`, notifies again, emits again, and renders the "done" state. A "Skip for now" link renders the done state without saving.
- `key` is a `UUIDField(default=uuid4, unique=True)`. It is the only way to reach step 2, so a reload or a lost session cannot strand the visitor, and nobody can enumerate rows. A row whose `details_at` is set, or older than 7 days, answers step 2 URLs with the done state (no re-editing).
- Alternative considered: keeping the row id in the session. Rejected — Django has no session key for an anonymous visitor until something writes one, and the Safari/ITP cookie problems from the embed change apply.

### `DemoRequest` model
Fields: `created_at`, `key`, `email`, `source` (≤32 chars, from `?src=`, allow-listed to `hero | how_to_start | services | educators | footer | direct`), `name`, `organisation`, `project` (text), `timeline` (choices `asap | this_quarter | later | exploring`, blank allowed), `details_at` (null), `user` (nullable FK, SET_NULL). Read-only admin with `list_display = (created_at, email, organisation, source, timeline, details_at, user)`, `search_fields` on email/organisation/project.

### Notifications
- One Celery task `notify_demo_request(request_id, stage)` in `survey/tasks.py`, `max_retries=3`, rendering `demo_request/notify.{txt,html}` via `send_templated_mail` to `settings.CONTACT_EMAIL`, `fail_silently=False` so a retry happens.
- Subject: `Demo request: <email>` (stage email) / `Demo request details: <email> — <organisation>` (stage details). Body: every stored field plus the admin link via `absolute_url`.
- Enqueued with `transaction.on_commit`; if `.delay()` raises (no broker in a dev shell), the task runs inline (`apply`). The row is saved before either path, so a mail failure never loses the lead.

### Analytics
- Server-side `demo_requested` event, properties `stage` (`email` | `details`), `source`, `timeline` (details only), `authenticated`. Distinct id: user pk when signed in, otherwise `_anonymous_distinct_id` from `pro_interest.py` — moved to a shared `survey/analytics_ids.py` and imported by both callers rather than duplicated. Never raises.
- No client-side click event: the surface is in `?src=` and lands in both the `$pageview` of `/demo/` and the row. `book_call_clicked` and its listener in `base_landing.html` go away.

### Abuse
- Honeypot `website` (from `HONEYPOT_FIELD_NAME`) on both steps; a filled honeypot on step 1 redirects to `/demo/done/`, which renders the same done state a person sees — the bot sees success, nothing is stored. Logged as `AbuseEvent("honeypot")`.
- Rate limit on `POST /demo/` only: `DEMO_REQUEST_LIMIT_HOUR` (default 5) and `DEMO_REQUEST_LIMIT_DAY` (default 20) per IP. `survey/abuse.py` gains generic `check_limits(request, limits)` / `increment_limits(request, limits)`; the registration helpers become thin wrappers over them, behaviour unchanged. A limited POST gets the existing `registration/rate_limited.html` with status 429 and `Retry-After`. Fail-open on a cache outage, as for registration.
- Step 2 is keyed by an unguessable UUID and only ever updates one row, so it is not rate-limited.
- No Turnstile and no consent checkbox: the submitted email is the request to be contacted. The page states, next to the field, that we reply once by email and keep no mailing list, and links the trust page.

### Copy
- Hero: **Get Mapsurvey free** / **Request a demo**. Demo-survey text link under the buttons stays.
- "Build it with us" card: button **Request a demo** (dark), link "What's included →". Fine print: "You'll hear back from a person within one working day."
- `/services/`: both buttons **Request a demo**; the register fallback stays.
- `/for-educators/`: secondary **Request a demo**. Footer "Connect": **Request a demo** replaces "Book a call".
- Step 1 page: H1 "See Mapsurvey on your project"; one sentence: "Leave your email and we'll write back within one working day with a short walkthrough built around what you want to map. No calendar, no call unless you want one." Button "Request a demo".
- Step 2: H1 "Thanks — tell us a bit more"; fields "Your name", "Organisation", "What do you want to map?", "When?"; button "Send details"; link "Skip for now".
- Done: "Thanks, we have your request. Artem will reply from mapsurvey.org within one working day." plus a "Get Mapsurvey free" button.
- All of the above get `ru` translations in `survey/locale/ru/LC_MESSAGES/django.po`, compiled with `compilemessages -l ru`.

### Footer after Notion's
Layout (desktop, `max-width: var(--section-inner-max)`): a brand column on the left (~1.4fr) and five link columns. The brand column holds the Mapsurvey wordmark at the top and a quote pinned to its bottom, as Notion does with McLuhan:

> "Cities have the capability of providing something for everybody, only because, and only when, they are created by everybody." — Jane Jacobs

(*The Death and Life of Great American Cities*, 1961 — on-message for participatory planning, and verifiable.) Russian: «Города способны дать что-то каждому только потому и только тогда, когда их создают все.» — Джейн Джекобс.

Columns (titles in sentence case, muted, no uppercase; links in body colour, ~15px). Labels are kept short so each fits on one line at 1280px, as in Notion's footer; columns are sized to their content and spread across the row. Audience and use-case labels carry their own `{% trans … context %}` so the Russian footer can use the genitive after «Mapsurvey для» without touching the same English strings elsewhere:

| Product | Mapsurvey for | Use cases | Resources | Company |
|---|---|---|---|---|
| Features | Urban planners | Community engagement | Customer stories | Trust & security |
| Demo survey | Local government | Public consultation | Tools compared | Email |
| Pro | Researchers | Civic engagement | vs Maptionnaire | Telegram |
| Project service | Educators | Participatory budgeting | vs Social Pinpoint | GitHub |
| Request a demo | Consultants | | vs MetroQuest | |

Under *Product* an "Explore all features →" link to `#features`, in the muted style of Notion's "Explore more →".

Bottom row, separated by a hairline: language links (English · Русский, each in its own language), the AGPLv3 licence line, © year.

Look: page background (`--color-bg`, light) instead of the dark `--color-footer-bg`; a 1px top border; the quote in a serif (`Georgia, 'Times New Roman', serif`) so it reads as a quotation, attribution muted. Dark-mode: the landing has no dark theme today, so nothing to add.

Responsive: ≤1024px the brand block spans the full first row (quote beside the wordmark is dropped below it) and the five columns wrap 3 + 2; ≤768px two columns. No horizontal scroll at 360px.

Every `href` the current footer carries is kept (tests `test_shared_footer_links_to_both`, `test_footer_and_nav_link_wave2_pages`, `test_landing_footer_links_to_stories`, `test_category_pages_and_footer_link_down` assert them); the only removal is "Book a call" and the duplicate GitHub entry.

### Removal of `BOOK_A_CALL_URL`
Setting, context-processor key, every template branch, the click listener and its tests are deleted rather than left behind a flag. The services page `mailto:` fallback is dropped too — `/demo/` always exists.

## Risks / Trade-offs

- **Spam rows** reach the admin and the inbox. Mitigated by honeypot + per-IP limits; acceptable because a false positive here is a lost lead and a false negative is one email to delete.
- **Celery broker down in production** would delay notifications, not lose rows; the admin list is the backstop, and a `demo_requested` event in PostHog still fires.
- **Signed-in creators** see `/demo/` too (email pre-filled); the hero still shows "Go to Dashboard" as primary for them, so this only matters for the other surfaces.

## Migration Plan

1. Migration adds `survey_demorequest`. No data migration.
2. Deploy; `BOOK_A_CALL_URL` on Render becomes unused and can be removed from the service and from the `mapsurvey-shared` env group at leisure.
3. Rollback is a normal deploy of the previous commit; the table is harmless if left.

## Open Questions

None — the two-step flow, the labels and the removal of the calendar were decided in the conversation that opened issue #288.
