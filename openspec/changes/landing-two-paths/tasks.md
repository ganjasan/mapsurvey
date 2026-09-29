## 1. Configuration

- [x] 1.1 Add `BOOK_A_CALL_URL` to `mapsurvey/settings.py` (env, default `https://cal.com/mapsurvey-artem/mapsurvey-call`); remove `DISCORD_INVITE_URL`
- [x] 1.2 Expose `BOOK_A_CALL_URL` in `survey/context_processors.contact`; drop `DISCORD_INVITE_URL`

## 2. Landing page

- [x] 2.1 Hero: Create + "Book a 30-min call" buttons, demo as a text link, "GDPR-Friendly" badge → "You own the data"
- [x] 2.2 Government use-case card: replace the infrastructure / subscription / GDPR copy
- [x] 2.3 Replace `.mid-cta` and `.final-cta` with the `.how-to-start` section (two cards, fallback to `/services/`)
- [x] 2.4 `landing.css`: `.how-to-start`, `.path*`, `.hero__demo-link`, dark button variant; delete `.mid-cta` / `.final-cta` rules if unused

## 3. Other pages

- [x] 3.1 `base_landing.html` footer: Discord → Book a call
- [x] 3.2 `for_educators.html`: Discord → Book a call
- [x] 3.3 `services.html`: both "Book a short call" buttons → `BOOK_A_CALL_URL`, `mailto:` fallback
- [x] 3.4 `book_call_clicked` PostHog listener on `[data-book-call]` in `base_landing.html`

## 4. i18n, static, tests

- [x] 4.1 i18n: no catalog change. The marketing pages are untranslated in every catalog (ru holds only fragments, and ru is not in `LANGUAGES`); a `makemessages -l ru` run rewrote ~8 000 unrelated lines, so it was reverted. Translating the landing is its own change.
- [x] 4.2 `collectstatic`
- [x] 4.3 Tests (GIVEN/WHEN/THEN): hero buttons, How-to-start cards, fallback when the setting is empty, no Discord on landing/educators/footer, services links to the booking URL and falls back to mailto, no "GDPR-Friendly"
- [x] 4.4 Run the landing-related test classes; check the page in a browser at desktop and 390 px
