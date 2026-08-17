# Tasks

## 1. One queryset for "publicly visible survey"

- [x] 1.1 Add `publicly_visible_surveys()` to `survey/views.py`, holding the filter that
      `index` uses today (`visibility in (demo, public)`, `is_canonical`,
      `published_version__isnull`, `deleted_at__isnull`, `exclude(status='draft')`), with a
      docstring naming the drift it exists to prevent.
- [x] 1.2 Rewrite `index` (`survey/views.py:441`) to call it, keeping its ordering and
      `session_count` annotation. No behaviour change — the landing page is already correct.
- [x] 1.3 Rewrite `sitemap_xml` (`survey/views.py:1739`) to call it. `status='published'`
      lives in the helper, not at the call site — see design.md for why the planned fork
      turned out to have no second consumer.

## 2. Unpublished surveys carry `noindex`

- [x] 2.1 Set `X-Robots-Tag: noindex` on `/surveys/<slug>/` responses for any survey whose
      `status` is not `published`, in `survey/access_control.py` next to the decision that
      produces the response. Covers the survey itself, redirects, and the password gate.
- [x] 2.2 Confirm a `published` survey carries no such header.

## 3. The 404 gets a body

- [x] 3.1 Add `survey/templates/survey_unavailable.html` — extends the public base template,
      names neither the survey nor the reason, one sentence plus a link to `/`.
- [x] 3.2 Wire `survey_not_found` as `handler404` and render the page there for paths under
      `/surveys/`, keeping Django's default everywhere else. `check_survey_access` keeps its
      bare `raise Http404` — rendering the page at the draft branch instead would make a draft
      distinguishable from a UUID that names nothing, and `resolve_survey`'s own `Http404`
      would still fall through to Django's blank page.
- [x] 3.3 Run the template guard test immediately after writing the template — a multi-line
      `{# #}` renders as visible page text in Django. Use `{% comment %}` if a comment is
      needed at all.

## 4. Tests

- [x] 4.1 Sitemap: a `draft`, a `closed`, an `archived`, a non-canonical, and a
      superseded-by-`published_version` survey are each absent; a `published` one is present.
- [x] 4.2 The landing page renders no survey list at all — `landing.html` has no loop over
      `surveys`. Pins that restoring one has to face `publicly_visible_surveys`.
- [x] 4.3 Sitemap: every `/surveys/<uuid>/` entry in the generated sitemap returns non-404
      when requested. This is the test that would have caught the original defect.
- [x] 4.4 `noindex` present for `draft`/`testing`/`closed`/`archived`, absent for `published`,
      including a `visibility='private'` draft.
- [x] 4.5 A `draft` URL and a random-UUID URL return identical bodies and both `404`.
- [x] 4.6 Unchanged behaviour: `published` opens, password-gated redirects to the gate,
      `closed` and `archived` still render the closed page.
- [x] 4.7 Run each new test against the pre-fix source and confirm it fails. A test that
      passes before the fix is describing existing behaviour, not catching the defect.
- [x] 4.8 Full suite green. 1243 tests, OK (skipped=1).

## 5. After deploy

- [ ] 5.1 Fetch the live `https://mapsurvey.org/sitemap.xml`; assert the `/surveys/<uuid>/`
      count equals the `published` + `public`/`demo` + canonical count in the production
      database, and that no entry 404s.
- [ ] 5.2 A week after deploy, re-check PostHog error tracking: `Http404` from
      `access_control.py` should fall to the residual from external links, not sitemap crawls.
      A flat rate means the private-draft path dominates and `noindex` needs longer to land.
