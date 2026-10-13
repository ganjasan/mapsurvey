## Why

Mapsurvey is applying to the Digital Public Goods Alliance registry (DPG Standard v1.1.7). The
application form asks for **public links** as evidence for ownership (indicator 3),
documentation (5), privacy and terms (7) and the do-no-harm policies (9B content, 9C harassment
and minors). Today those links do not exist: there is no copyright holder named anywhere, no
Terms of Service, no code of conduct, no published content policy, and the README
"Documentation" link points to `mapsurvey.org/docs`, which returns 404. The safety mechanisms
themselves already ship (content screening, holds, report link, staff review); this change
publishes the policies around them and closes two small product gaps the policy commits to.

Drafts approved by the owner on 2026-10-13 live in the private ops repo
(`Mapsurvey-ops/docs/marketing/engagement-networks/dpga/`). Decisions: owner name
**Artem Koniukhov**, abuse contact **konuchovartem@mapsurvey.org**, first assessment of reports
within **2 business days** (same day for child sexual abuse material and imminent harm),
creator accounts **16+**.

## What Changes

- **Ownership statement.** README gets a "License & ownership" section (copyright 2021–2026
  Artem Koniukhov, AGPLv3, trademark-free use statement, data belongs to the creator). The
  landing footer copyright reads "© 2021–<year> Artem Koniukhov" and links Terms and
  Privacy & Trust. `/trust/` gets an "Ownership" block and its "Who is behind" text uses the
  name Artem Koniukhov.
- **Terms page.** New public page `/terms/` with terms of use and an **Acceptable use & safety**
  section (`#acceptable-use`): prohibited content (CSAM first), detection, moderation and
  removal, response times, appeals, harassment protection, children and young people (creator
  accounts 16+), personal-data summary linking to `/trust/`.
- **`/privacy/` redirects** permanently to `/trust/`.
- **Age confirmation on sign-up.** The registration form gains a required "I am 16 or older and
  accept the Terms" checkbox; registration without it fails validation.
- **More report reasons.** "Report this survey" adds `illegal`, `child_abuse`, `harassment` and
  `personal_data` to `phishing`, `scam`, `other`; labels become translatable. A `child_abuse`
  report is marked urgent in the moderator email subject.
- **Repository docs.** New `docs/OVERVIEW.md` (functional overview), new `CODE_OF_CONDUCT.md`
  (Contributor Covenant 2.1 + a section pointing to the platform policy), README links fixed to
  point at them.

No breaking changes. Existing accounts are not asked to re-confirm their age.

## Capabilities

### New Capabilities
- `legal-pages`: public Terms page with the Acceptable use & safety policy, `/privacy/` redirect,
  ownership block on `/trust/`, footer copyright and legal links.
- `project-governance-docs`: repository-level ownership, documentation and conduct files the
  DPG application links to (README section, `docs/OVERVIEW.md`, `CODE_OF_CONDUCT.md`).

### Modified Capabilities
- `respondent-abuse-report`: the report form's reason list grows from three to seven values;
  `child_abuse` reports are flagged urgent in the owner notice.
- `registration-abuse-defenses`: legitimate registration additionally requires an age and
  terms confirmation checkbox.
- `landing-page`: the footer copyright names the owner and the Legal column links Terms.

## Impact

- **Code:** `survey/urls.py` (terms, privacy redirect), `survey/views.py` (terms view),
  new `survey/templates/terms.html`, `survey/templates/trust.html`,
  `survey/templates/base_landing.html` (footer), `survey/abuse.py` (`RegistrationAbuseForm`),
  registration template, `survey/content_screening.py` (`REPORT_REASONS`, notice subject),
  `survey/templates/abuse/report.html` unchanged structurally.
- **Translations:** new msgids for the checkbox, report reasons and footer; Terms page body is
  English-only at first (like `/trust/`).
- **Docs:** `README.md`, `docs/OVERVIEW.md`, `CODE_OF_CONDUCT.md`.
- **SEO:** `/terms/` added to the sitemap; `/privacy/` is a 301.
- **No migrations:** report reason is stored in `ContentReview.note`, not a choice field.
- **Ops follow-up (not code):** submit the DPGA application once these links are live.
