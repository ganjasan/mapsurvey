## 1. Repository documents

- [x] 1.1 Replace the README "License" section with "License & ownership" (text from the ops draft `ownership-statement.md`, owner Artem Koniukhov, contact konuchovartem@mapsurvey.org)
- [x] 1.2 Point the README header "Documentation" link to `docs/OVERVIEW.md`; add links to `CODE_OF_CONDUCT.md` in Contributing
- [x] 1.3 Add `docs/OVERVIEW.md` from the ops draft `functional-overview.md`; re-check every claim (question types, env vars, languages, k-anonymity default) against the code
- [x] 1.4 Add `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1 verbatim, contact konuchovartem@mapsurvey.org, plus the "Using the hosted service" section

## 2. Terms page and privacy redirect

- [x] 2.1 Add `terms_page` view (with a `TERMS_UPDATED` date constant) and `path('terms/', …, name='terms_page')`
- [x] 2.2 Write `survey/templates/terms.html` on `base_landing.html`, styled like `trust.html`, with section ids `terms`, `acceptable-use`, `prohibited`, `moderation`, `harassment`, `children`, `personal-data`, `contact`; body from the ops draft `do-no-harm-policy.md` sections 1–6, without the "(planned)" markers and without the unverified educator-templates sentence
- [x] 2.3 Add a short general-terms part (service as-is, creator owns and is responsible for their surveys, account termination for violations, governing contact) above Acceptable use
- [x] 2.4 Add `path('privacy/', RedirectView(pattern_name='trust_page', permanent=True))`
- [x] 2.5 Add `/terms/` to `sitemap_xml`
- [x] 2.6 Tests (GIVEN/WHEN/THEN): `/terms/` 200 with all anchor ids, CSAM first in `prohibited`, "2 business days" and "16" present; `/privacy/` 301 to `/trust/`; sitemap contains `/terms/` and not `/privacy/`

## 3. Trust page and footer

- [x] 3.1 Add the `#ownership` block to `trust.html` before "Who is behind Mapsurvey"; rename the owner to Artem Koniukhov; link `/terms/`
- [x] 3.2 Footer in `base_landing.html`: Legal column → "Terms of use" + "Privacy & Trust"; bottom line `© 2021–{% now "Y" %} Artem Koniukhov · AGPLv3`
- [x] 3.3 Tests: `/trust/` contains `id="ownership"` and "Artem Koniukhov", not "Artem Konuchov"; a landing page footer links `/terms/` and shows the new copyright line

## 4. Age and terms confirmation on sign-up

- [x] 4.1 Add required `accept_terms` BooleanField to `RegistrationAbuseForm` with a label linking `/terms/`
- [x] 4.2 Render it in `django_registration/registration_form.html` as checkbox-then-label (branch in the field loop)
- [x] 4.3 Tests: missing `accept_terms` → 200 with field error, no user; honeypot + missing `accept_terms` → fake-success redirect; page renders the checkbox and link; existing legitimate-registration tests send `accept_terms=on`

## 5. Report reasons and child-abuse escalation

- [x] 5.1 Extend `REPORT_REASONS` to `phishing, scam, illegal, child_abuse, harassment, personal_data, other` with `gettext_lazy` labels
- [x] 5.2 `notice_subject()`: prefix `[URGENT] ` when the review note starts with `child_abuse:`
- [x] 5.3 `report()`: on a `child_abuse` report against an open review whose note does not start with `child_abuse:`, rewrite the prefix to `child_abuse`, keep the earlier text, increment `report_count`, send one urgent notice
- [x] 5.4 Tests: seven reasons in order; first `child_abuse` report → urgent subject; `child_abuse` after `scam` → note rewritten, one extra urgent mail; repeat `child_abuse` → no mail; existing report tests still pass

## 6. Translations and verification

- [x] 6.1 `makemessages` for the new msgids (checkbox label, reasons, footer); add translations for the 11 interface languages
- [x] 6.2 Line-by-line check of `terms.html` against shipped behaviour (specs `survey-content-screening`, `abuse-review`, `respondent-abuse-report`, `file-upload-questions`, shared-map moderation, comment threads); delete any sentence that is not true in production
- [x] 6.3 Run the test suite once before and once after; summarise the delta
- [x] 6.4 ~~Check on the PR preview: `/terms/`, `/terms/#acceptable-use`, `/privacy/`, `/trust/#ownership`, sign-up checkbox, report form~~ — skipped by the owner on 2026-10-13: merged without a preview check
