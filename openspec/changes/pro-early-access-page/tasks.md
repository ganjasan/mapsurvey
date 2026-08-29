# Tasks — Pro early-access page

## Capability definition

- [x] `survey/pro_interest.py` with `CAPABILITY_GROUPS` — ordered groups of
      options, each option a stable machine key plus label and hint. Plus
      `CAPABILITY_KEYS` (flat frozenset), `SEGMENT_CHOICES`,
      `BUDGET_SHAPE_CHOICES`. Keys are strings and never reordered-by-index.

## Model

- [x] `ProInterest` in `survey/models.py`: `created_at`, `email`, `organisation`,
      `segment`, `capabilities` (JSONField list), `missing_text`,
      `budget_shape`, `user` (FK, null, `SET_NULL`), `consent_at`.
- [x] Migration `0065_pro_interest.py`, depending on `0064_creatorpreferences`.
      Numbered 0065 rather than the generated 0064 because three sibling
      worktrees already carried a `0064_creatorpreferences`; that branch landed
      on master while this one was in review, so the dependency was re-pointed
      at it during the rebase. Left on `0063` it would have given Django two
      leaf nodes.
- [x] `ProInterestAdmin` — read-only, renders the full capability list because
      "which boxes did public bodies tick" is the question being asked.

## Form and view

- [x] `ProInterestForm` (in `pro_interest.py`, beside the constants it
      validates against): rejects unknown capability keys, requires consent and
      email, allows an empty capability selection.
- [x] View `pro_early_access` (GET renders, POST validates and stores),
      pre-filling email and attaching `request.user` when authenticated. Calls
      `capture_signup_source` like the other landings.
- [x] URL `path('pro/', views.pro_early_access, name='pro_early_access')`.
- [x] Emit `pro_interest_submitted` after a successful save, wrapped so a
      failure cannot lose the submission.
- [x] Distinct id resolved for anonymous submitters too — PostHog cookie, then
      session key, then the row id. The first draft returned None when both
      were absent, which silently dropped the event for the anonymous majority.

## Template

- [x] `survey/templates/pro.html` extending `base_landing.html`: 4 steps,
      grouped checkboxes, free-text, budget shape, consent + privacy link,
      confirmation state.
- [x] CSS in `survey/assets/css/landing.css`; `collectstatic` run.
- [x] All copy through `{% trans %}`; `{% comment %}` used, never multi-line
      `{# #}`.

## Discoverability

- [x] `base_landing.html`: "Pro" and "Services" in the nav; "Pro — early access"
      and "Project service" in the footer Product column.
- [x] `robots_txt`: `Allow: /pro/`.
- [x] `sitemap_xml`: `/pro/` added (`/services/` was already listed — its
      problem was the absence of any internal link, not crawlability).

## Tests (`survey/tests.py`, GIVEN/WHEN/THEN docstrings)

- [x] `ProEarlyAccessPageTest`, 13 tests: renders every group and key; no price;
      free-stays-free; consent present and unticked; valid POST stored; empty
      selection stored; unknown key rejected; missing consent rejected;
      authenticated pre-fill and attribution; no `SurveyEvent` written;
      analytics failure does not lose the answer; one event with the right
      properties; nav/footer/robots/sitemap.

## Verification

- [x] `openspec validate pro-early-access-page --strict`.
- [x] `./run_tests.sh survey` — 1677 tests, OK.
- [x] Driven in a real browser (headless Chromium): empty submit is blocked by
      the browser before any request; consent is enforced client-side too;
      ticked options and the selected pill highlight; a complete submission
      stores the row and shows the confirmation; no horizontal scroll at 390px.
      The only console error is the pre-existing Tawk.to CORS failure on
      localhost, which every landing page has.
- [ ] Translations: `makemessages` / `compilemessages` for the ~40 new strings
      across EN+RU, ID, DE, ES, FR, PT, PL. Deferred deliberately — an
      untranslated msgid falls back to the English source, so the page works
      everywhere meanwhile, and a sweep over eight catalogs deserves its own
      diff rather than riding along in this one.

## Deferred (separate change)

- Contextual entry points in the editor: share screen, publish widget, Responses
  tab, dashboard banner.
- German version of the page, if the DE municipality outreach needs it.
