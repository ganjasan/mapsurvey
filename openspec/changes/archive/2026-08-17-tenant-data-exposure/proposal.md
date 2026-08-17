## Why

Two independent gaps let anyone enumerate every survey on the platform, and let any
registered account export any survey's collected responses.

`/surveys/` is served by `survey_list` (`survey/views.py:555`), four lines with no
decorator and no filter beyond `deleted_at__isnull=True`. It renders **the entire
`SurveyHeader` table**: name plus a direct link, for every survey of every customer.
Verified against production on 2026-08-16 — `HTTP 200`, unauthenticated, **292 surveys
across 166 organizations**, of which 152 are `private` and 151 are `draft`.

That page is the load-bearing failure. `visibility='private'` is not an access control —
its `help_text` says it "Controls whether survey appears on the landing page", and a
private published survey is meant to be openable by anyone holding the link, the way a
creator runs a closed survey with their own audience. That model depends entirely on the
UUID being unguessable. `/surveys/` hands out all 292 of them.

`download_data` (`survey/views.py:1027`) then turns enumeration into extraction. It
carries `@login_required` and nothing else: no organization scope, no survey role check,
and `resolve_survey` resolves a UUID globally. Any registered account can therefore fetch
`/surveys/<uuid>/download` for **any** survey and receive the full export — GeoJSON per geo
question plus CSV, including respondent geometry and free-text answers. Registration is
open, so the bar is one signup.

Found while investigating a PostHog `Http404` issue and confirmed from the code, the
production database, and the live page. Cross-tenant export was not exercised against real
customer data.

## What Changes

- **BREAKING** Remove the public `/surveys/` listing entirely — route, view, and template.
  Nothing in the codebase references it: no `reverse('survey_list')`, no
  `{% url 'survey_list' %}`, no `href`, and no test exercises the route. The landing page
  (`index`, `survey/views.py:441`) already lists surveys with the correct filters
  (`visibility in (demo, public)`, `is_canonical`, `exclude(status='draft')`) and is the
  legitimate successor.
- Serve `301 → /` at the old path rather than letting it 404. The page has been in
  `sitemap.xml` and allowed in `robots.txt`, so it may be indexed.
- Drop the `/surveys/` entry from `sitemap_xml` (`survey/views.py:1795`), which would
  otherwise advertise a redirect. Keep `Allow: /surveys/` in `robots.txt`
  (`survey/views.py:1760`) — it is a prefix that also covers `/surveys/<uuid>/`, which must
  stay crawlable.
- Authorize `download_data` on the survey, not merely on being signed in: the caller must
  hold a role on the survey or its organization. Authentication alone is not authorization.
- Cover both with tests that assert cross-tenant denial, not just happy-path success.

Explicitly **not** changing: `check_survey_access` continues to ignore `visibility`. Once
the listing is gone, link-based access to an unlisted survey is the intended behaviour, and
gating it would break creators sharing a private survey with their respondents.

## Capabilities

### New Capabilities
- `survey-access-control`: who may open, list, and export a survey. Covers the removal of
  the public listing, the boundary between `visibility` (discovery) and access (link or
  role), and the authorization rule for the data export.

### Modified Capabilities
- `uuid-survey-identification`: the scenario "Survey list links use UUID"
  (`openspec/specs/uuid-survey-identification/spec.md:90`) describes a page that this change
  deletes. It is removed; the sibling "Landing page survey links use UUID" scenario is
  unaffected.

## Impact

Code:
- `survey/urls.py:106` — route replaced with a permanent redirect
- `survey/views.py:555-558` — `survey_list` view deleted
- `survey/templates/survey_list.html` — deleted
- `survey/views.py:1795` — sitemap entry removed
- `survey/views.py:1027` — `download_data` gains an authorization check
- `survey/tests.py` — new cross-tenant denial tests

Not affected, despite matching a grep:
- `survey/views.py:481-540`, `survey/tests.py:9136` — a local variable also named
  `survey_list`, inside the `editor` view
- `mapsurvey/settings.py:303,384` — `POSTHOG_EXCLUDED_PREFIXES` and
  `ACQUISITION_NON_MARKETING_PREFIXES` match the whole `/surveys/*` namespace

Operational: no migration. The redirect changes a public URL's behaviour, so it ships on
its own rather than bundled with unrelated work.

Out of scope, tracked separately: `sitemap_xml` also advertises draft, closed, and archived
surveys (61 of 140 entries are hard 404s), and `Http404` is reported to PostHog error
tracking as if it were a defect.
