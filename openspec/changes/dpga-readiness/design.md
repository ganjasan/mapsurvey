## Context

The DPGA application (see proposal) needs live URLs. Most of the work is content, but four
places touch running code: a new public page, a redirect, the registration form, and the
respondent report flow. Source texts are the owner-approved drafts in the ops repo
(`Mapsurvey-ops/docs/marketing/engagement-networks/dpga/`: `ownership-statement.md`,
`do-no-harm-policy.md`, `functional-overview.md`). They are copied here, not linked: the ops
repo is private.

Current state:
- `/trust/` → `views.trust_page` renders `trust.html` (extends `base_landing.html`); it names
  "Artem Konuchov".
- Footer in `base_landing.html`: "Legal" column links only Trust & Security; bottom line is
  `© {% now "Y" %} Mapsurvey`.
- Registration: `RegistrationAbuseForm` (`survey/abuse.py`) extends django-registration's form,
  adds the honeypot; the template iterates over `form` fields generically.
- Reports: `content_screening.REPORT_REASONS` (3 untranslated labels), `ReportForm` in
  `abuse_review_views.py`, `report()` writes `"<reason>: <message>"` to `ContentReview.note`
  and mails once per open review; `notice_subject()` builds the subject.
- `sitemap_xml` lists static pages by hand (`/trust/` is there).

## Goals / Non-Goals

**Goals:**
- Every DPGA evidence link resolves: README ownership anchor, `docs/OVERVIEW.md`,
  `CODE_OF_CONDUCT.md`, `/terms/`, `/terms/#acceptable-use`, `/privacy/`, `/trust/`.
- What the policy promises is true in the product on the day it is published (16+ confirmation,
  report reasons including child abuse and harassment, urgent handling of child-abuse reports).

**Non-Goals:**
- Age verification beyond self-declaration; re-consent of existing accounts.
- Translating the Terms body (English only, same as `/trust/` today).
- Self-serve account deletion, a DPA page, publiccode.yml (separate items).
- Any change to screening scores, holds or the review page.

## Decisions

1. **Terms as a static template, not a CMS/Story.** `terms.html` extends `base_landing.html`
   like `trust.html`; view `terms_page` mirrors `trust_page`. Sections carry stable ids
   (`#terms`, `#acceptable-use`, `#prohibited`, `#moderation`, `#harassment`, `#children`,
   `#personal-data`, `#contact`) because the DPGA form deep-links them. A "Last updated" date
   is rendered from a constant in the view, not `now`, so the date only moves when the text does.

2. **`/privacy/` is a `RedirectView(permanent=True)` to `trust_page`.** One source of truth;
   no duplicate content for search engines. `/terms/` is added to `sitemap_xml`; `/privacy/` is not.

3. **Age/terms checkbox lives in `RegistrationAbuseForm`.** A `BooleanField(required=True)`
   named `accept_terms`, label with a link to `/terms/` ("I am 16 or older and accept the Terms
   of use"). The form already renders every field generically; the template needs one branch
   so the checkbox renders input-before-label. The honeypot runs before form validation and is
   unchanged, so a bot hitting the honeypot still gets the fake success. Nothing is stored:
   the timestamp of `date_joined` plus the required field is the record. Alternative — storing
   a consent row — rejected as unnecessary for self-declaration.

4. **Report reasons stay a code-level tuple, labels via `gettext_lazy`.** New values:
   `illegal`, `child_abuse`, `harassment`, `personal_data`, ordered by severity after
   `phishing`/`scam` and before `other`. No migration: the reason lives in the `note` prefix.
   `notice_context` already maps the prefix back to a label.

5. **Urgent handling of `child_abuse`.** `notice_subject()` prefixes `[URGENT]` when the review
   note starts with `child_abuse:`. Because later reports on an open review normally send no
   mail, a `child_abuse` report on an **already-open** review whose note does not start with
   `child_abuse:` SHALL rewrite the note prefix to `child_abuse` (keeping prior text after it)
   and send one urgent notice. Otherwise a CSAM report landing on a survey already reported for
   "scam" would be silent — breaking the same-day promise.

6. **Name change on `/trust/` is text-only.** "Who is behind" becomes Artem Koniukhov; a new
   "Ownership" block (copyright holder, sole proprietor in the Kyrgyz Republic, AGPLv3,
   data belongs to creators) is inserted before it.

7. **Footer.** Bottom line: `© 2021–{% now "Y" %} Artem Koniukhov · AGPLv3`. Legal column:
   Terms of use, Privacy & Trust. The landing-page spec forbids login/registration links in the
   footer — unaffected.

8. **Repo docs are plain Markdown.** README "License" section is replaced by
   "License & ownership" (GitHub anchor `#license--ownership`); the "Documentation" link in the
   header points to `docs/OVERVIEW.md`. `CODE_OF_CONDUCT.md` = Contributor Covenant 2.1 verbatim
   with contact `konuchovartem@mapsurvey.org` and an appended "Using the hosted service" section.

## Risks / Trade-offs

- **Checkbox adds sign-up friction** → one click, pre-labelled; the funnel event for
  registration is unchanged so any drop is visible in PostHog.
- **Policy text over-promises** → every sentence in `terms.html` maps to shipped behaviour;
  the tasks include a line-by-line check against specs before merge. The "educator templates
  collect no personal data" sentence from the draft is dropped unless verified.
- **Legal wording is not lawyer-reviewed** → stated as the operator's policy, not a compliance
  certificate; laws are named only on the DPGA form, not claimed on the page.
- **Name mismatch with git history ("Konuchov")** → README states the copyright holder
  explicitly; history is not rewritten.

## Migration Plan

Single deploy, no data migration. Rollback = revert the PR; no state depends on it.

## Open Questions

None — owner decisions recorded in the proposal.
